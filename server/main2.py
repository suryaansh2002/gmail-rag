#!/usr/bin/env python3
import os
import time
import base64
import hashlib
import torch
from io import BytesIO
import PyPDF2
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from sentence_transformers import SentenceTransformer
from pinecone import Pinecone, ServerlessSpec
import ollama
from dotenv import load_dotenv

load_dotenv()

# --- Configuration ---
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
CLIENT_SECRET_FILE = 'credentials.json'  # Your OAuth2 client secret file
TOKEN_FILE = 'token.json'  # File to store the user's access and refresh tokens

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
print(PINECONE_API_KEY)
PINECONE_INDEX_NAME = "gmail-knowledge-base"
CLOUD_ENV = "aws"         # e.g., 'aws'
REGION_ENV = "us-east-1"    # e.g., 'us-east-1'

EMBEDDING_MODEL_NAME = 'all-MiniLM-L6-v2'
OLLAMA_MODEL_NAME = 'llama3.2'  # Use the latest Llama model from Ollama

# --- Gmail API Authentication ---
def authenticate_gmail():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
        creds = flow.run_local_server(port=8000)
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
    service = build('gmail', 'v1', credentials=creds)
    return service

# --- Helper: Process Attachments ---
def process_attachments(attachments):
    processed_text = ""
    for attachment in attachments:
        filename = attachment.get("filename", "Unknown")
        content_type = attachment.get("content_type", "unknown")
        # Process CSV files
        if content_type == "text/csv" or filename.lower().endswith(".csv"):
            text = attachment.get("content", "")
            processed_text += f"\nAttachment CSV ({filename}): {text[:1000]}"
        # Process PDF files
        elif content_type == "application/pdf" or filename.lower().endswith(".pdf"):
            raw_content = attachment.get("raw_content", None)
            if raw_content:
                try:
                    reader = PyPDF2.PdfReader(BytesIO(raw_content))
                    pdf_text = ""
                    for page in reader.pages:
                        pdf_text += page.extract_text() or ""
                    processed_text += f"\nAttachment PDF ({filename}): {pdf_text[:1000]}"
                except Exception as e:
                    processed_text += f"\nAttachment PDF ({filename}): [Error extracting text: {e}]"
            else:
                processed_text += f"\nAttachment PDF ({filename}): [No raw content available]"
        # Process other text attachments
        elif content_type.startswith("text/"):
            text = attachment.get("content", "")
            processed_text += f"\nAttachment ({filename}): {text[:1000]}"
        else:
            processed_text += f"\nAttachment ({filename}): [binary content of type {content_type}]"
    return processed_text

# --- Helper: Extract email content from payload ---
def get_email_content(service, message_id, payload, include_attachments=True):
    body = ""
    html_body = ""
    attachments = []

    if 'parts' in payload:
        for part in payload['parts']:
            mimeType = part.get('mimeType', '')
            filename = part.get('filename', '')
            body_data = part.get('body', {})
            
            # If attachments are to be included and this part has a filename, process it as an attachment.
            if include_attachments and filename:
                att = {"filename": filename, "content_type": mimeType}
                # For PDF files, store raw bytes for extraction
                if mimeType == "application/pdf" or filename.lower().endswith(".pdf"):
                    if 'data' in body_data:
                        att['raw_content'] = base64.urlsafe_b64decode(body_data['data'])
                    elif 'attachmentId' in body_data:
                        attachment = service.users().messages().attachments().get(
                            userId='me', messageId=message_id, id=body_data['attachmentId']).execute()
                        data = attachment.get('data', '')
                        att['raw_content'] = base64.urlsafe_b64decode(data)
                # For text-based attachments (including CSV)
                elif mimeType.startswith("text/") or mimeType == "text/csv" or filename.lower().endswith(".csv"):
                    if 'data' in body_data:
                        try:
                            att['content'] = base64.urlsafe_b64decode(body_data['data']).decode('utf-8', errors='replace')
                        except Exception:
                            att['content'] = base64.urlsafe_b64decode(body_data['data']).decode('latin-1', errors='replace')
                    elif 'attachmentId' in body_data:
                        attachment = service.users().messages().attachments().get(
                            userId='me', messageId=message_id, id=body_data['attachmentId']).execute()
                        data = attachment.get('data', '')
                        try:
                            att['content'] = base64.urlsafe_b64decode(data).decode('utf-8', errors='replace')
                        except Exception:
                            att['content'] = base64.urlsafe_b64decode(data).decode('latin-1', errors='replace')
                else:
                    # Fallback for other attachments: attempt to decode as text
                    if 'data' in body_data:
                        try:
                            att['content'] = base64.urlsafe_b64decode(body_data['data']).decode('utf-8', errors='replace')
                        except Exception:
                            att['content'] = base64.urlsafe_b64decode(body_data['data']).decode('latin-1', errors='replace')
                attachments.append(att)
            else:
                # Process non-attachment parts (body parts)
                if mimeType == "text/plain":
                    if 'data' in body_data:
                        try:
                            text = base64.urlsafe_b64decode(body_data['data']).decode('utf-8', errors='replace')
                        except Exception:
                            text = base64.urlsafe_b64decode(body_data['data']).decode('latin-1', errors='replace')
                        body += text
                elif mimeType == "text/html":
                    if 'data' in body_data:
                        try:
                            text = base64.urlsafe_b64decode(body_data['data']).decode('utf-8', errors='replace')
                        except Exception:
                            text = base64.urlsafe_b64decode(body_data['data']).decode('latin-1', errors='replace')
                        html_body += text
                # Check for nested parts
                if 'parts' in part:
                    sub_body, sub_html, sub_attachments = get_email_content(service, message_id, part, include_attachments)
                    body += sub_body
                    html_body += sub_html
                    attachments.extend(sub_attachments)
    else:
        # Single part message
        mimeType = payload.get('mimeType', '')
        body_data = payload.get('body', {})
        if mimeType == "text/plain":
            if 'data' in body_data:
                try:
                    body = base64.urlsafe_b64decode(body_data['data']).decode('utf-8', errors='replace')
                except Exception:
                    body = base64.urlsafe_b64decode(body_data['data']).decode('latin-1', errors='replace')
        elif mimeType == "text/html":
            if 'data' in body_data:
                try:
                    html_body = base64.urlsafe_b64decode(body_data['data']).decode('utf-8', errors='replace')
                except Exception:
                    html_body = base64.urlsafe_b64decode(body_data['data']).decode('latin-1', errors='replace')
    return body, html_body, attachments

# --- Parse Gmail Message ---
def parse_email_message(service, msg_data, include_attachments=True):
    payload = msg_data.get('payload', {})
    headers = payload.get('headers', [])
    email_dict = {}
    for header in headers:
        name = header.get('name', '').lower()
        value = header.get('value', '')
        if name == 'subject':
            email_dict['subject'] = value
        elif name == 'from':
            email_dict['from'] = value
        elif name == 'date':
            email_dict['date'] = value
    body, html_body, attachments = get_email_content(service, msg_data.get('id', ''), payload, include_attachments)
    email_dict['body'] = body if body else html_body
    email_dict['attachments'] = attachments

    # Create a unique ID based on date, sender, and subject
    unique_content = f"{email_dict.get('date', '')}-{email_dict.get('from', '')}-{email_dict.get('subject', '')}"
    email_dict['id'] = hashlib.sha256(unique_content.encode()).hexdigest()
    return email_dict

# --- Fetch Emails using Gmail API ---
def fetch_emails(service, max_emails=10, include_attachments=True):
    emails_data = []
    try:
        results = service.users().messages().list(userId='me', maxResults=max_emails).execute()
        messages = results.get('messages', [])
        print(f"Found {len(messages)} emails.")
        for msg in messages:
            msg_id = msg['id']
            msg_data = service.users().messages().get(userId='me', id=msg_id, format='full').execute()
            try:
                email_dict = parse_email_message(service, msg_data, include_attachments)
                emails_data.append(email_dict)
            except Exception as e:
                print(f"Error parsing message {msg_id}: {e}")
        print(f"Successfully fetched and parsed {len(emails_data)} emails.")
    except Exception as e:
        print(f"Error fetching emails: {e}")
    return emails_data

# --- Format Email for Embedding ---
def format_email_for_embedding(email_data):
    attachments_text = process_attachments(email_data.get("attachments", []))
    embedding_text = (
        f"Subject: {email_data.get('subject', '')}\n"
        f"From: {email_data.get('from', '')}\n"
        f"Date: {email_data.get('date', '')}\n"
        f"Body: {email_data.get('body', '')[:2000]}\n"
        f"Attachments: {attachments_text}"
    )
    return embedding_text

# --- Initialize Pinecone ---
def initialize_pinecone(api_key, index_name, dimension, metric='cosine'):
    print("Initializing Pinecone...")
    pc = Pinecone(api_key=api_key)
    spec = ServerlessSpec(cloud=CLOUD_ENV, region=REGION_ENV)
    existing_indexes = pc.list_indexes().names()
    if index_name in existing_indexes:
        desc = pc.describe_index(index_name)
        if desc.dimension != dimension:
            print(f"Existing index '{index_name}' dimension mismatch. Deleting and recreating.")
            pc.delete_index(index_name)
            time.sleep(10)
    if index_name not in pc.list_indexes().names():
        print(f"Creating index '{index_name}' with dimension {dimension}...")
        pc.create_index(name=index_name, dimension=dimension, metric=metric, spec=spec)
        print("Waiting for index to be ready...")
        while True:
            index_description = pc.describe_index(index_name)
            if index_description.status.get('ready', False):
                break
            print("Waiting for index...")
            time.sleep(5)
        print(f"Index '{index_name}' created.")
    index = pc.Index(index_name)
    print("Pinecone index initialized.")
    return index

# --- Embed and Upsert Emails ---
def embed_and_upsert(emails, index, model, batch_size=10):
    print(f"Embedding {len(emails)} emails...")
    all_ids = []
    all_embeddings = []
    all_metadata = []

    for i, email_data in enumerate(emails):
        if not email_data.get('body') and not email_data.get('subject'):
            print(f"Skipping email {email_data.get('id', 'N/A')} due to empty content.")
            continue

        # Create embedding text that includes email body and attachments text
        text_to_embed = format_email_for_embedding(email_data)
        embedding = model.encode(text_to_embed).tolist()

        # Process attachments separately to include in metadata
        attachments_processed = process_attachments(email_data.get("attachments", []))
        metadata = {
            "subject": email_data.get('subject', ''),
            "from": email_data.get('from', ''),
            "date": email_data.get('date', ''),
            "text": text_to_embed,
            "attachments": attachments_processed
        }

        all_ids.append(email_data['id'])
        all_embeddings.append(embedding)
        all_metadata.append(metadata)

        if (i + 1) % 50 == 0 or (i + 1) == len(emails):
            print(f"Processed {i + 1}/{len(emails)} emails.")

    print(f"Upserting {len(all_ids)} vectors to Pinecone...")
    for i in range(0, len(all_ids), batch_size):
        batch_ids = all_ids[i:i+batch_size]
        batch_embeddings = all_embeddings[i:i+batch_size]
        batch_metadata = all_metadata[i:i+batch_size]
        vectors_to_upsert = [
            {"id": id_val, "values": emb, "metadata": meta}
            for id_val, emb, meta in zip(batch_ids, batch_embeddings, batch_metadata)
        ]
        if vectors_to_upsert:
            try:
                index.upsert(vectors=vectors_to_upsert)
                print(f"Upserted batch {i // batch_size + 1}")
            except Exception as e:
                print(f"Error upserting batch {i // batch_size + 1}: {e}")
    print("Upsert complete.")

# --- Query Emails ---
def query_emails(query_text, index, model, llm_model, top_k=5):
    print(f"\nProcessing query: '{query_text}'")
    query_embedding = model.encode(query_text).tolist()
    try:
        query_results = index.query(vector=query_embedding, top_k=top_k, include_metadata=True)
    except Exception as e:
        print(f"Error querying Pinecone: {e}")
        return "Error querying email data."

    context = ""
    if query_results.matches:
        context += "Based on the following email information:\n\n"
        for i, match in enumerate(query_results.matches):
            metadata = match.metadata
            context += f"--- Email {i+1} (Score: {match.score:.4f}) ---\n"
            context += f"From: {metadata.get('from', 'N/A')}\n"
            context += f"Subject: {metadata.get('subject', 'N/A')}\n"
            context += f"Date: {metadata.get('date', 'N/A')}\n"
            text_snippet = metadata.get('text', 'N/A')
            context += f"Attachments: {metadata.get('attachments', 'N/A')}\n"
            context += f"Content Snippet: {text_snippet[:500]}...\n\n"
    else:
        print("No matching emails found.")
        return "No relevant emails found."

    prompt = (
        f"{context}\n\nPlease answer the following question based *only* on the above email information, do not include email number in your reply. You can include Email From, Date, and Subject in your reply to help the user understand the context. Reply in well formatted markdown. \n"
        f"Question: {query_text}"
    )

    try:
        response = ollama.chat(
            model=llm_model,
            messages=[{'role': 'user', 'content': prompt}]
        )
        answer = response['message']['content']
        return answer
    except Exception as e:
        print(f"Error communicating with Ollama: {e}")
        return "Error generating answer with LLM."

# --- Main Pipeline ---
if __name__ == "__main__":
    print("Starting Gmail Chat with Email Data")

    # Step 1: Gmail Authentication and Email Fetching
    print("Authenticating with Gmail API...")
    gmail_service = authenticate_gmail()
    print("Fetching emails...")
    # The third parameter controls whether to include attachments (True by default)
    emails_list = fetch_emails(gmail_service, max_emails=10, include_attachments=True)
    if not emails_list:
        print("No emails fetched. Exiting.")
        exit()

    # Step 2: Load Embedding Model
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Loading embedding model {EMBEDDING_MODEL_NAME} on {device}...")
    embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME, device=device)
    vector_dim = embedding_model.get_sentence_embedding_dimension()
    print(f"Embedding dimension: {vector_dim}")

    # Step 3: Initialize Pinecone
    pinecone_index = initialize_pinecone(PINECONE_API_KEY, PINECONE_INDEX_NAME, vector_dim)

    # Step 4: Embed and Upsert Emails into Pinecone
    embed_and_upsert(emails_list, pinecone_index, embedding_model)

    # Step 5: Query Interface
    print("\n--- Email Query Interface ---")
    print("Type your question about the emails (type 'quit' to exit).")
    while True:
        user_query = input("Your question: ")
        if user_query.lower() == 'quit':
            break
        if not user_query.strip():
            continue
        answer = query_emails(user_query, pinecone_index, embedding_model, OLLAMA_MODEL_NAME)
        print("\nAnswer:")
        print(answer)
        print("-" * 40)
    
    print("Exiting Gmail Chat.")
