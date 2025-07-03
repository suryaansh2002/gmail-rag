#!/usr/bin/env python3
import os
import time
import base64
import hashlib
import secrets
from io import BytesIO

import torch
import PyPDF2
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import RedirectResponse, JSONResponse
from pydantic import BaseModel
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from sentence_transformers import SentenceTransformer
from pinecone import Pinecone, ServerlessSpec
import ollama
from dotenv import load_dotenv
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
load_dotenv()

# --- Configuration ---
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
CLIENT_SECRET_FILE = "credentials.json"  # Your OAuth2 client secret file
TOKEN_FILE = "token.json"  # File to store the user's access and refresh tokens

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = "gmail-knowledge-base"
CLOUD_ENV = "aws"  # e.g., 'aws'
REGION_ENV = "us-east-1"  # e.g., 'us-east-1'

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
OLLAMA_MODEL_NAME = "gemma3"

# Global in-memory state for OAuth (maps state tokens to the client-supplied redirect_uri)
oauth_states = {}

# Global variables for embedding model and Pinecone index.
embedding_model = None
pinecone_index = None

# --- FastAPI app ---
app = FastAPI(
    title="Gmail Chat API",
    description="API for Gmail Chat with email data ingestion and query answering using Pinecone and LLM.",
    version="1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or your specific domain like ["http://localhost:3000"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Request Models ---
class AuthRequest(BaseModel):
    redirect_uri: str


class FetchEmailsRequest(BaseModel):
    number_of_emails: int
    include_attachments: int  # 0 or 1


class QueryRequest(BaseModel):
    query: str


# --- Gmail API Authentication helper ---
def authenticate_gmail():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        raise HTTPException(
            status_code=401, detail="User not authenticated. Please authenticate first."
        )
    service = build("gmail", "v1", credentials=creds)
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
                    processed_text += (
                        f"\nAttachment PDF ({filename}): {pdf_text[:1000]}"
                    )
                except Exception as e:
                    processed_text += (
                        f"\nAttachment PDF ({filename}): [Error extracting text: {e}]"
                    )
            else:
                processed_text += (
                    f"\nAttachment PDF ({filename}): [No raw content available]"
                )
        # Process other text attachments
        elif content_type.startswith("text/"):
            text = attachment.get("content", "")
            processed_text += f"\nAttachment ({filename}): {text[:1000]}"
        else:
            processed_text += (
                f"\nAttachment ({filename}): [binary content of type {content_type}]"
            )
    return processed_text


# --- Helper: Extract email content from payload ---
def get_email_content(service, message_id, payload, include_attachments=True):
    body = ""
    html_body = ""
    attachments = []

    if "parts" in payload:
        for part in payload["parts"]:
            mimeType = part.get("mimeType", "")
            filename = part.get("filename", "")
            body_data = part.get("body", {})

            # If attachments are to be included and this part has a filename, process it as an attachment.
            if include_attachments and filename:
                att = {"filename": filename, "content_type": mimeType}
                # For PDF files, store raw bytes for extraction
                if mimeType == "application/pdf" or filename.lower().endswith(".pdf"):
                    if "data" in body_data:
                        att["raw_content"] = base64.urlsafe_b64decode(body_data["data"])
                    elif "attachmentId" in body_data:
                        attachment = (
                            service.users()
                            .messages()
                            .attachments()
                            .get(
                                userId="me",
                                messageId=message_id,
                                id=body_data["attachmentId"],
                            )
                            .execute()
                        )
                        data = attachment.get("data", "")
                        att["raw_content"] = base64.urlsafe_b64decode(data)
                # For text-based attachments (including CSV)
                elif (
                    mimeType.startswith("text/")
                    or mimeType == "text/csv"
                    or filename.lower().endswith(".csv")
                ):
                    if "data" in body_data:
                        try:
                            att["content"] = base64.urlsafe_b64decode(
                                body_data["data"]
                            ).decode("utf-8", errors="replace")
                        except Exception:
                            att["content"] = base64.urlsafe_b64decode(
                                body_data["data"]
                            ).decode("latin-1", errors="replace")
                    elif "attachmentId" in body_data:
                        attachment = (
                            service.users()
                            .messages()
                            .attachments()
                            .get(
                                userId="me",
                                messageId=message_id,
                                id=body_data["attachmentId"],
                            )
                            .execute()
                        )
                        data = attachment.get("data", "")
                        try:
                            att["content"] = base64.urlsafe_b64decode(data).decode(
                                "utf-8", errors="replace"
                            )
                        except Exception:
                            att["content"] = base64.urlsafe_b64decode(data).decode(
                                "latin-1", errors="replace"
                            )
                else:
                    # Fallback for other attachments: attempt to decode as text
                    if "data" in body_data:
                        try:
                            att["content"] = base64.urlsafe_b64decode(
                                body_data["data"]
                            ).decode("utf-8", errors="replace")
                        except Exception:
                            att["content"] = base64.urlsafe_b64decode(
                                body_data["data"]
                            ).decode("latin-1", errors="replace")
                attachments.append(att)
            else:
                # Process non-attachment parts (body parts)
                if mimeType == "text/plain":
                    if "data" in body_data:
                        try:
                            text = base64.urlsafe_b64decode(body_data["data"]).decode(
                                "utf-8", errors="replace"
                            )
                        except Exception:
                            text = base64.urlsafe_b64decode(body_data["data"]).decode(
                                "latin-1", errors="replace"
                            )
                        body += text
                elif mimeType == "text/html":
                    if "data" in body_data:
                        try:
                            text = base64.urlsafe_b64decode(body_data["data"]).decode(
                                "utf-8", errors="replace"
                            )
                        except Exception:
                            text = base64.urlsafe_b64decode(body_data["data"]).decode(
                                "latin-1", errors="replace"
                            )
                        html_body += text
                # Check for nested parts
                if "parts" in part:
                    sub_body, sub_html, sub_attachments = get_email_content(
                        service, message_id, part, include_attachments
                    )
                    body += sub_body
                    html_body += sub_html
                    attachments.extend(sub_attachments)
    else:
        # Single part message
        mimeType = payload.get("mimeType", "")
        body_data = payload.get("body", {})
        if mimeType == "text/plain":
            if "data" in body_data:
                try:
                    body = base64.urlsafe_b64decode(body_data["data"]).decode(
                        "utf-8", errors="replace"
                    )
                except Exception:
                    body = base64.urlsafe_b64decode(body_data["data"]).decode(
                        "latin-1", errors="replace"
                    )
        elif mimeType == "text/html":
            if "data" in body_data:
                try:
                    html_body = base64.urlsafe_b64decode(body_data["data"]).decode(
                        "utf-8", errors="replace"
                    )
                except Exception:
                    html_body = base64.urlsafe_b64decode(body_data["data"]).decode(
                        "latin-1", errors="replace"
                    )
    return body, html_body, attachments


# --- Parse Gmail Message ---
def parse_email_message(service, msg_data, include_attachments=True):
    payload = msg_data.get("payload", {})
    headers = payload.get("headers", [])
    email_dict = {}
    for header in headers:
        name = header.get("name", "").lower()
        value = header.get("value", "")
        if name == "subject":
            email_dict["subject"] = value
        elif name == "from":
            email_dict["from"] = value
        elif name == "date":
            email_dict["date"] = value
    body, html_body, attachments = get_email_content(
        service, msg_data.get("id", ""), payload, include_attachments
    )
    email_dict["body"] = body if body else html_body
    email_dict["attachments"] = attachments

    # Create a unique ID based on date, sender, and subject
    unique_content = f"{email_dict.get('date', '')}-{email_dict.get('from', '')}-{email_dict.get('subject', '')}"
    email_dict["id"] = hashlib.sha256(unique_content.encode()).hexdigest()
    return email_dict


# --- Fetch Emails using Gmail API ---
def fetch_emails(service, max_emails=100, include_attachments=True):
    emails_data = []
    try:
        results = (
            service.users()
            .messages()
            .list(userId="me", maxResults=max_emails)
            .execute()
        )
        messages = results.get("messages", [])
        print(f"Found {len(messages)} emails.")
        for msg in messages:
            msg_id = msg["id"]
            msg_data = (
                service.users()
                .messages()
                .get(userId="me", id=msg_id, format="full")
                .execute()
            )
            try:
                email_dict = parse_email_message(service, msg_data, include_attachments)
                emails_data.append(email_dict)
            except Exception as e:
                print(f"Error parsing message {msg_id}: {e}")
        print(f"Successfully fetched and parsed {len(emails_data)} emails.")
    except Exception as e:
        print(f"Error fetching emails: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching emails: {e}")
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
def initialize_pinecone(api_key, index_name, dimension, metric="cosine"):
    print("Initializing Pinecone...")
    pc = Pinecone(api_key=api_key)
    spec = ServerlessSpec(cloud=CLOUD_ENV, region=REGION_ENV)
    existing_indexes = pc.list_indexes().names()
    if index_name in existing_indexes:
        desc = pc.describe_index(index_name)
        if desc.dimension != dimension:
            print(
                f"Existing index '{index_name}' dimension mismatch. Deleting and recreating."
            )
            pc.delete_index(index_name)
            time.sleep(10)
    if index_name not in pc.list_indexes().names():
        print(f"Creating index '{index_name}' with dimension {dimension}...")
        pc.create_index(name=index_name, dimension=dimension, metric=metric, spec=spec)
        print("Waiting for index to be ready...")
        while True:
            index_description = pc.describe_index(index_name)
            if index_description.status.get("ready", False):
                break
            print("Waiting for index...")
            time.sleep(5)
        print(f"Index '{index_name}' created.")
    index = pc.Index(index_name)
    print("Pinecone index initialized.")
    return index

def build_email_prompt(query_results, query_text: str) -> str:
    """
    Constructs a structured, instruction-following prompt for an LLM to answer
    a user query based strictly on email content retrieved from vector search.

    Parameters
    ----------
    query_results : object
        The result object from the vector search. Expected to have a `.matches` list,
        where each match includes `.metadata` and `.score` attributes.
    query_text : str
        The user's natural-language question.

    Returns
    -------
    str
        A fully formatted prompt ready to be passed to an LLM.
    """
    if not query_results.matches:
        return "No relevant emails found."

    # 1) Build CONTEXT block --------------------------------------
    MAX_SNIPPET_LEN = 1500
    context_lines = ["You are given a set of email records relevant to the user's query:\n"]
    for idx, match in enumerate(query_results.matches, 1):
        md = match.metadata
        snippet = md.get("text", "N/A")
        if snippet and len(snippet) > MAX_SNIPPET_LEN:
            snippet = snippet[:MAX_SNIPPET_LEN - 3] + "..."

        context_lines.extend([
            f"--- Email {idx} (Relevance Score: {match.score:.4f}) ---",
            f"From: {md.get('from', 'N/A')}",
            f"To: {md.get('to', 'N/A')}",
            f"Subject: {md.get('subject', 'N/A')}",
            f"Date: {md.get('date', 'N/A')}",
            f"Attachments: {md.get('attachments', 'None')}",
            f"Content Snippet:\n{snippet}\n"
        ])
    context_block = "\n".join(context_lines)

    # 2) SYSTEM instructions --------------------------------------
    system_block = (
        "### SYSTEM INSTRUCTIONS\n"
        "You are a precise and trustworthy email analysis assistant.\n"
        "You must answer the user's question using only the email content provided below.\n\n"
        "Follow these rules:\n"
        "1. If the answer is explicitly or logically present, extract it and explain clearly.\n"
        "2. If the answer is not present and cannot be reasonably inferred, say:\n"
        "   → Information not found in the provided emails.\n"
        "3. If sensitive personal information (e.g., phone number, ID) is requested:\n"
        "   - Only return it if it appears verbatim in the context.\n"
        "   - Do not guess or generate missing details.\n"
        "4. Always reference the email’s Subject, Date, and From fields in your answer.\n"
        "5. Keep your answer accurate, complete, and easy to understand.\n"
    )

    # 3) Output format instruction ---------------------------------
    output_format_block = (
        "### OUTPUT FORMAT\n"
        "Respond with a natural language answer.\n"
        "Include references like:\n"
        "• Subject: <email subject>\n"
        "• Date: <email date>\n"
        "• From: <email sender>\n"
    )

    # 4) Full prompt ----------------------------------------------
    prompt = (
        f"{system_block}\n"
        f"### CONTEXT\n{context_block}\n"
        f"### USER QUESTION\n{query_text}\n\n"
        f"{output_format_block}"
    )
    return prompt


# --- Embed and Upsert Emails ---
def embed_and_upsert(emails, index, model, batch_size=100):
    print(f"Embedding {len(emails)} emails...")
    all_ids = []
    all_embeddings = []
    all_metadata = []

    for i, email_data in enumerate(emails):
        if not email_data.get("body") and not email_data.get("subject"):
            print(f"Skipping email {email_data.get('id', 'N/A')} due to empty content.")
            continue

        # Create embedding text that includes email body and attachments text
        text_to_embed = format_email_for_embedding(email_data)
        embedding = model.encode(text_to_embed).tolist()

        # Process attachments separately to include in metadata
        attachments_processed = process_attachments(email_data.get("attachments", []))
        metadata = {
            "subject": email_data.get("subject", ""),
            "from": email_data.get("from", ""),
            "date": email_data.get("date", ""),
            "text": text_to_embed,
            "attachments": attachments_processed,
        }

        all_ids.append(email_data["id"])
        all_embeddings.append(embedding)
        all_metadata.append(metadata)

        if (i + 1) % 50 == 0 or (i + 1) == len(emails):
            print(f"Processed {i + 1}/{len(emails)} emails.")

    print(f"Upserting {len(all_ids)} vectors to Pinecone...")
    for i in range(0, len(all_ids), batch_size):
        batch_ids = all_ids[i : i + batch_size]
        batch_embeddings = all_embeddings[i : i + batch_size]
        batch_metadata = all_metadata[i : i + batch_size]
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
def query_emails(query_text, index, model, llm_model, top_k=3):
    print(f"\nProcessing query: '{query_text}'")
    query_embedding = model.encode(query_text).tolist()
    try:
        query_results = index.query(
            vector=query_embedding, top_k=top_k, include_metadata=True
        )
    except Exception as e:
        print(f"Error querying Pinecone: {e}")
        return "Error querying email data."


    prompt = build_email_prompt(query_results, query_text)
    print("Prompt sent to LLM:")
    print(prompt)
    try:
        response = ollama.chat(
            model=llm_model, messages=[{"role": "user", "content": prompt}],
        )
        answer = response["message"]["content"]
        return answer
    except Exception as e:
        print(f"Error communicating with Ollama: {e}")
        return "Error generating answer with LLM."


@app.post("/authenticate", summary="Authenticate with Gmail OAuth")
def start_auth(auth_req: AuthRequest):
    print(auth_req.redirect_uri)
    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
    state = secrets.token_urlsafe(16)
    oauth_states[state] = auth_req.redirect_uri

    flow.redirect_uri = auth_req.redirect_uri
    auth_url, _ = flow.authorization_url(
        prompt="consent", state=state, include_granted_scopes="true"
    )

    # Instead of returning RedirectResponse(auth_url), return JSON with the URL
    return JSONResponse({"auth_url": auth_url, "state": state})


@app.post("/oauth/callback", summary="OAuth Callback")
def oauth_callback(state: str, code: str):
    # Allow insecure transport for local development
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

    if state is None or code is None:
        raise HTTPException(
            status_code=400, detail="Missing state or code in callback."
        )
    if state not in oauth_states:
        raise HTTPException(status_code=400, detail="Invalid state.")

    # Recreate the OAuth flow with the same state
    flow = InstalledAppFlow.from_client_secrets_file(
        CLIENT_SECRET_FILE, SCOPES, state=state
    )
    # Set the redirect_uri to the exact value registered (no extra query parameters)
    flow.redirect_uri = "http://localhost:3000/authenticate?success=true"

    try:
        # Use the code directly instead of constructing an authorization_response URL
        flow.fetch_token(code=code)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error fetching token: {e}")

    creds = flow.credentials

    # Save credentials to token.json on the backend
    with open(TOKEN_FILE, "w") as token_file:
        token_file.write(creds.to_json())

    # Remove the used state
    oauth_states.pop(state, None)
    return {"success": "true"}


# --- Email Data Endpoint ---
@app.post(
    "/fetch_emails",
    summary="Fetch and Index Emails",
    description="Fetches a given number of emails from Gmail and upserts them into Pinecone. Parameters include number_of_emails (integer) and include_attachments (0 or 1).",
)
def fetch_and_index_emails(fetch_req: FetchEmailsRequest):
    # Authenticate using the stored token (user must have authenticated already)
    service = authenticate_gmail()
    include_atts = bool(fetch_req.include_attachments)
    emails = fetch_emails(
        service, max_emails=fetch_req.number_of_emails, include_attachments=include_atts
    )
    if not emails:
        raise HTTPException(status_code=404, detail="No emails fetched.")
    embed_and_upsert(emails, pinecone_index, embedding_model)
    return {"status": "success", "num_emails_fetched": len(emails)}


# --- Query Endpoint ---
@app.post(
    "/ask_query",
    summary="Ask Query",
    description="Takes a 'query' string in the request body and returns the answer generated by the LLM based on indexed email data.",
)
def ask_query(query_req: QueryRequest):
    answer = query_emails(
        query_req.query, pinecone_index, embedding_model, OLLAMA_MODEL_NAME
    )
    return {"answer": answer}


# --- Startup Event ---
@app.on_event("startup")
def startup_event():
    global embedding_model, pinecone_index
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Loading embedding model {EMBEDDING_MODEL_NAME} on {device}...")
    embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME, device=device)
    vector_dim = embedding_model.get_sentence_embedding_dimension()
    print(f"Embedding dimension: {vector_dim}")
    pinecone_index = initialize_pinecone(
        PINECONE_API_KEY, PINECONE_INDEX_NAME, vector_dim
    )
    print("Startup complete.")


# --- Health Check Endpoint ---
@app.get("/health", summary="Health Check")
def health():
    return {"status": "ok"}
