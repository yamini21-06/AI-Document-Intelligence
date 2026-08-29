# AI-Powered Document Intelligence & RAG Platform

A complete local, end-to-end RAG application for uploading PDF/DOCX/TXT files and asking grounded questions about them.

## What is included

- React + Vite frontend
- FastAPI backend
- PostgreSQL + pgvector
- Ollama for local embeddings and LLM generation
- PDF, DOCX and TXT extraction
- Page-aware chunking
- Vector similarity retrieval
- Source citations and similarity scores
- Document-scoped chat
- Document deletion
- Health checks
- Windows PowerShell setup/start scripts
- Docker Compose for PostgreSQL

## Prerequisites (Windows)

Install these once:

1. Python 3.11 or 3.12
2. Node.js 20+
3. Docker Desktop
4. Ollama

Ollama must be running before you upload/chat. Install these models:

```powershell
ollama pull nomic-embed-text
ollama pull llama3.2:3b
```

If `llama3.2:3b` is unavailable on your machine, change `OLLAMA_LLM_MODEL` in `backend/.env` to any chat-capable model you have pulled.

## Fastest setup

Open the project folder in VS Code, then open PowerShell in the project root.

### First time only

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\setup.ps1
```

### Every time you want to run it

```powershell
.\start.ps1
```

The script starts PostgreSQL, checks Ollama, starts FastAPI, waits for the API, and starts the React dev server.

Open http://localhost:5173

API docs: http://localhost:8000/docs

## Manual start

### 1. Database

```powershell
docker compose up -d db
```

### 2. Backend

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

### 3. Frontend

In another terminal:

```powershell
cd frontend
npm install
npm run dev
```

## How the application works

```text
Upload document
      |
      v
FastAPI validates file
      |
      v
PDF/DOCX/TXT text extraction
      |
      v
Page-aware chunking
      |
      v
Ollama embedding model
      |
      v
PostgreSQL + pgvector
      |
      v
User question
      |
      v
Question embedding
      |
      v
Cosine similarity search
      |
      v
Top relevant chunks
      |
      v
Ollama LLM + grounded prompt
      |
      v
Answer + source citations
```

## Supported files

- `.pdf`
- `.docx`
- `.txt`

Maximum upload size defaults to 20 MB. Change `MAX_UPLOAD_MB` in `backend/.env` if needed.

## Troubleshooting

### Docker is not running

Start Docker Desktop and run:

```powershell
docker compose up -d db
```

### Ollama is not running

Start Ollama, then check:

```powershell
ollama list
```

Pull models if necessary:

```powershell
ollama pull nomic-embed-text
ollama pull llama3.2:3b
```

### Port already in use

- Backend: 8000
- Frontend: 5173
- PostgreSQL: 5433 on the host, 5432 inside Docker

Change `BACKEND_PORT` or `FRONTEND_PORT` in `start.ps1` if required.

### Rebuild database from scratch

```powershell
docker compose down -v
docker compose up -d db
```

This deletes all indexed documents.

## Project structure

```text
ai-doc-rag/
├── backend/
│   ├── app/
│   │   ├── config.py
│   │   ├── db.py
│   │   ├── ingest.py
│   │   ├── main.py
│   │   ├── models.py
│   │   ├── ollama.py
│   │   └── schemas.py
│   ├── .env.example
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── main.jsx
│   │   └── style.css
│   ├── index.html
│   └── package.json
├── storage/
├── docker-compose.yml
├── setup.ps1
├── start.ps1
├── stop.ps1
└── README.md
```
