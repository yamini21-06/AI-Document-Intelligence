# AI-Powered Document Intelligence & RAG Platform

An AI-powered application that lets you **upload documents and ask questions about them in normal language**.

Instead of manually searching through a long document, you can upload it and simply ask:

> "What is the company's leave policy?"

The application finds the relevant information from the document and uses an AI model to generate an answer based on that information.

## What does it do?

* 📄 Upload PDF, DOCX, and TXT documents
* 🔎 Search the content based on the meaning of your question
* 🤖 Ask questions using natural language
* 🧠 Generate answers using an AI model
* 📚 Show the document sections used to generate the answer
* 📷 Read scanned PDFs using OCR
* 🗂️ Manage multiple uploaded documents
* 🎯 Ask questions about specific documents

## How does it work?

The basic idea is:

**Upload Document → Read Document → Break it into smaller sections → Store the sections → Ask a Question → Find the relevant sections → AI generates the answer**

The project uses **RAG (Retrieval-Augmented Generation)** so the AI first looks for relevant information in the uploaded documents before answering.

For example:

**Document:** Company Handbook

**Question:**

> How many days of annual leave do employees receive?

**System:**
Finds the relevant section from the handbook.

**AI:**

> Employees receive 18 days of paid annual leave per year.

The application also shows the source information used for the answer, making it easier to verify the response.

## Technology Used

**Frontend:** React, Vite

**Backend:** Python, FastAPI

**AI:** Ollama, Llama 3.2

**Embeddings:** nomic-embed-text

**Database:** PostgreSQL, pgvector

**Document Processing:** PyMuPDF, python-docx

**OCR:** Tesseract

**Containerization:** Docker

## Why I Built It

I built this project to understand how a real-world **Retrieval-Augmented Generation (RAG)** application works from beginning to end.

It helped me work with document processing, embeddings, vector search, LLMs, APIs, databases, OCR, and frontend-backend integration in one complete application.

## Project Flow

```text
User uploads a document
        ↓
Document is processed
        ↓
Content is divided into smaller sections
        ↓
Sections are converted into embeddings
        ↓
Stored in PostgreSQL + pgvector
        ↓
User asks a question
        ↓
Relevant sections are retrieved
        ↓
AI generates an answer
        ↓
Answer + sources are displayed
```

## Run Locally

Make sure you have:

* Python 3.11+
* Node.js
* Docker Desktop
* Ollama
* Tesseract OCR

Then run:

```powershell
.\start.ps1
```

Open:

**http://localhost:5173**

---

### Project

**AI-Powered Document Intelligence & RAG Platform**

Built by **Yamini Sailaja Lakshmi**
