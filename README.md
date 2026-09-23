# Gmail RAG (Retrieval-Augmented Generation) System

A full-stack application that allows you to chat with your Gmail data using AI. The system fetches emails, processes them with embeddings, stores them in Pinecone vector database, and provides intelligent answers to queries about your email content.

> **No public demo.** This app requires each user's own Gmail OAuth credentials to run, so there's no hosted instance to click through. Run it locally against your own Gmail account by following the setup steps below.

## Features

- 🔐 Secure Gmail OAuth authentication
- 📧 Email fetching with attachment processing (PDF, CSV, text files)
- 🧠 AI-powered email content analysis using sentence transformers
- 🔍 Vector search with Pinecone for relevant email retrieval
- 💬 Natural language querying with Ollama LLM integration
- 🌐 Modern Next.js frontend with Tailwind CSS
- ⚡ FastAPI backend with async processing

## Architecture

- **Frontend**: Next.js with React, Tailwind CSS, and shadcn/ui components
- **Backend**: FastAPI with Python
- **Vector Database**: Pinecone for email embeddings storage
- **LLM**: Ollama for natural language processing
- **Authentication**: Google OAuth 2.0 for Gmail access
- **Embeddings**: Sentence Transformers (all-MiniLM-L6-v2)

## Prerequisites

- Python 3.8+
- Node.js 16+
- Ollama installed locally
- Google Cloud Project with Gmail API enabled
- Pinecone account and API key

## Setup Instructions

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd gmail-rag
```

### 2. Backend Setup

#### Install Python Dependencies

```bash
cd server
pip install -r requirements.txt
```

#### Configure Environment Variables

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and fill in your credentials:
   ```env
   GMAIL_ADDRESS="your_gmail_address@gmail.com"
   GMAIL_APP_PASSWORD="your_gmail_app_password"
   PINECONE_API_KEY="your_pinecone_api_key"
   ```

#### Setup Google OAuth Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Gmail API
4. Create OAuth 2.0 credentials (Desktop application type)
5. Download the credentials JSON file
6. Copy the example credentials file:
   ```bash
   cp credentials.json.example credentials.json
   ```
7. Replace the content with your downloaded credentials

#### Setup Ollama

1. Install Ollama from [ollama.ai](https://ollama.ai/)
2. Pull the required model:
   ```bash
   ollama pull gemma3
   # or for the standalone script:
   ollama pull llama3.2
   ```

### 3. Frontend Setup

```bash
cd client
npm install
# or
pnpm install
```

### 4. Running the Application

#### Start the Backend Server

```bash
cd server
python main.py
```

The API will be available at `http://localhost:8000`

#### Start the Frontend Development Server

```bash
cd client
npm run dev
# or
pnpm dev
```

The frontend will be available at `http://localhost:3000`

## Usage

1. **Authentication**: Visit the frontend and click "Authenticate with Gmail" to authorize the application
2. **Fetch Emails**: Use the "Fetch Emails" page to import your emails into the system
3. **Chat**: Go to the "Chat" page to ask questions about your email content

## API Endpoints

- `POST /authenticate` - Start Gmail OAuth flow
- `POST /oauth/callback` - Handle OAuth callback
- `POST /fetch_emails` - Fetch and index emails
- `POST /ask_query` - Query the email database
- `GET /health` - Health check

## Security Notes

⚠️ **Important Security Information**:

- Never commit `.env`, `credentials.json`, or `token.json` files to version control
- These files contain sensitive credentials and are automatically ignored by `.gitignore`
- Use the provided `.example` files as templates
- Regularly rotate your API keys and OAuth credentials
- Consider using environment-specific configurations for production deployments

## File Structure

```
gmail-rag/
├── client/                 # Next.js frontend
│   ├── app/               # App router pages
│   ├── components/        # React components
│   └── lib/              # Utility functions
├── server/                # FastAPI backend
│   ├── main.py           # Main FastAPI application
│   ├── main2.py          # Standalone script version
│   ├── requirements.txt  # Python dependencies
│   ├── .env.example      # Environment variables template
│   └── credentials.json.example  # OAuth credentials template
└── README.md
```

## Development

### Running Tests

```bash
# Backend tests (if implemented)
cd server
python -m pytest

# Frontend tests
cd client
npm test
```

### Code Style

- Python: Follow PEP 8 guidelines
- JavaScript/TypeScript: ESLint and Prettier configured

## Troubleshooting

### Common Issues

1. **OAuth Errors**: Ensure your redirect URIs match exactly in Google Cloud Console
2. **Pinecone Connection**: Verify your API key and region settings
3. **Ollama Model**: Make sure the specified model is pulled and available
4. **Port Conflicts**: Check that ports 3000 and 8000 are available

### Logs

- Backend logs are printed to console
- Check browser developer tools for frontend issues
- Ollama logs: `ollama logs`

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

MIT — see [LICENSE](LICENSE).

## Acknowledgments

- [Sentence Transformers](https://www.sbert.net/) for embeddings
- [Pinecone](https://www.pinecone.io/) for vector database
- [Ollama](https://ollama.ai/) for local LLM inference
- [FastAPI](https://fastapi.tiangolo.com/) for the backend framework
- [Next.js](https://nextjs.org/) for the frontend framework