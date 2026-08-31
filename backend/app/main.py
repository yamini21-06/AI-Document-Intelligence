from pathlib import Path

from fastapi import (
    Depends,
    FastAPI,
    File,
    HTTPException,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db, init_db
from .ingest import SUPPORTED, chunk_pages, extract_pages
from .models import (
    EMBEDDING_DIM,
    Chunk,
    Document,
)
from .ollama import (
    OllamaError,
    check_ollama,
    embed,
    generate,
)
from .schemas import (
    ChatRequest,
    ChatResponse,
    DocumentOut,
    Source,
)


app = FastAPI(
    title="AI Document Intelligence & RAG API",
    version="2.0.0",
)


# =========================================================
# CORS
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# STARTUP
# =========================================================

@app.on_event("startup")
def startup():
    init_db()


# =========================================================
# HEALTH
# =========================================================

@app.get("/api/health")
def health():
    return {
        "status": "ok"
    }


@app.get("/api/health/ollama")
async def ollama_health():
    return await check_ollama()


# =========================================================
# DOCUMENT RESPONSE HELPER
# =========================================================

def doc_out(
    db: Session,
    doc: Document,
) -> DocumentOut:
    """
    Convert a SQLAlchemy Document object into
    the DocumentOut response model.

    Document.chunks is a list of Chunk objects,
    while DocumentOut.chunks is an integer.

    Therefore we calculate the count explicitly.
    """

    count = (
        db.scalar(
            select(
                func.count(Chunk.id)
            ).where(
                Chunk.document_id == doc.id
            )
        )
        or 0
    )

    return DocumentOut(
        id=doc.id,
        filename=doc.filename,
        content_type=doc.content_type,
        status=doc.status,
        error=doc.error,
        created_at=doc.created_at,
        chunks=count,
    )


# =========================================================
# LIST DOCUMENTS
# =========================================================

@app.get(
    "/api/documents",
    response_model=list[DocumentOut],
)
def list_documents(
    db: Session = Depends(get_db),
):
    documents = db.scalars(
        select(Document).order_by(
            Document.created_at.desc()
        )
    ).all()

    return [
        doc_out(db, document)
        for document in documents
    ]


# =========================================================
# UPLOAD DOCUMENT
# =========================================================

@app.post(
    "/api/documents/upload",
    response_model=DocumentOut,
)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    # -----------------------------------------------------
    # 1. Validate filename
    # -----------------------------------------------------

    filename = Path(
        file.filename or ""
    ).name

    extension = Path(
        filename
    ).suffix.lower()

    if extension not in SUPPORTED:
        raise HTTPException(
            status_code=400,
            detail=(
                "Only PDF, DOCX, and TXT "
                "files are supported."
            ),
        )

    # -----------------------------------------------------
    # 2. Read file
    # -----------------------------------------------------

    data = await file.read()

    # -----------------------------------------------------
    # 3. Check file size
    # -----------------------------------------------------

    maximum_size = (
        settings.max_upload_mb
        * 1024
        * 1024
    )

    if len(data) > maximum_size:
        raise HTTPException(
            status_code=413,
            detail=(
                f"File exceeds "
                f"{settings.max_upload_mb} MB."
            ),
        )

    # -----------------------------------------------------
    # 4. Create document record
    # -----------------------------------------------------

    document = Document(
        filename=filename,
        content_type=(
            file.content_type
            or "application/octet-stream"
        ),
        status="processing",
    )

    db.add(document)
    db.commit()
    db.refresh(document)

    try:

        # -------------------------------------------------
        # 5. Extract text
        # -------------------------------------------------

        pages = extract_pages(
            filename,
            data,
        )

        # -------------------------------------------------
        # 6. Split into chunks
        # -------------------------------------------------

        pieces = chunk_pages(
            pages,
            settings.chunk_size,
            settings.chunk_overlap,
        )

        if not pieces:
            raise ValueError(
                "No readable text was found "
                "in the document."
            )

        # -------------------------------------------------
        # 7. Generate embeddings
        # -------------------------------------------------

        for index, (page, text) in enumerate(
            pieces
        ):

            vector = await embed(text)

            if len(vector) != EMBEDDING_DIM:
                raise ValueError(
                    f"Embedding dimension is "
                    f"{len(vector)}; expected "
                    f"{EMBEDDING_DIM}. "
                    "Check the embedding model."
                )

            chunk = Chunk(
                document_id=document.id,
                chunk_index=index,
                page=page,
                text=text,
                embedding=vector,
            )

            db.add(chunk)

        # -------------------------------------------------
        # 8. Mark document ready
        # -------------------------------------------------

        document.status = "ready"
        document.error = None

        db.commit()
        db.refresh(document)

        return doc_out(
            db,
            document,
        )

    except Exception as exc:

        db.rollback()

        failed_document = db.get(
            Document,
            document.id,
        )

        if failed_document:
            failed_document.status = "error"
            failed_document.error = str(exc)[:2000]
            db.commit()

        if isinstance(
            exc,
            OllamaError,
        ):
            raise HTTPException(
                status_code=503,
                detail=str(exc),
            )

        raise HTTPException(
            status_code=500,
            detail=(
                f"Document processing failed: "
                f"{exc}"
            ),
        )


# =========================================================
# DELETE DOCUMENT
# =========================================================

@app.delete(
    "/api/documents/{document_id}"
)
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
):
    document = db.get(
        Document,
        document_id,
    )

    if not document:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    db.delete(document)
    db.commit()

    return {
        "deleted": True
    }


# =========================================================
# FAST DOCUMENT SUMMARIZATION
# =========================================================

# Number of chunks used for a broad document overview.
#
# Keep this relatively small because the LLM is running
# locally through Ollama.

SUMMARY_CHUNK_LIMIT = 8


def build_chunk_context(
    chunks: list[tuple[Chunk, Document]],
) -> str:
    """
    Convert chunks into structured LLM context.
    """

    parts = []

    for chunk, document in chunks:

        parts.append(
            f"[Source {chunk.id}]\n"
            f"Document: {document.filename}\n"
            f"Page: {chunk.page or 'N/A'}\n"
            f"Content:\n{chunk.text}"
        )

    return "\n\n".join(parts)


def select_representative_chunks(
    chunks: list[tuple[Chunk, Document]],
    limit: int = SUMMARY_CHUNK_LIMIT,
) -> list[tuple[Chunk, Document]]:
    """
    Select representative chunks from across the
    document rather than sending every chunk to Ollama.

    This makes broad document questions much faster.
    """

    if len(chunks) <= limit:
        return chunks

    step = len(chunks) / limit

    selected = []

    for index in range(limit):

        position = min(
            int(index * step),
            len(chunks) - 1,
        )

        selected.append(
            chunks[position]
        )

    return selected


async def summarize_document(
    chunks: list[tuple[Chunk, Document]],
    question: str,
) -> str:
    """
    Generate a fast overview of a document.

    For small documents:
        use all chunks.

    For large documents:
        use representative chunks from
        different parts of the document.

    Only ONE LLM call is made.
    """

    if not chunks:
        return (
            "I could not find enough information "
            "in the provided documents."
        )

    # -----------------------------------------------------
    # Select chunks
    # -----------------------------------------------------

    selected_chunks = (
        select_representative_chunks(
            chunks
        )
    )

    # -----------------------------------------------------
    # Build context
    # -----------------------------------------------------

    context = build_chunk_context(
        selected_chunks
    )

    # -----------------------------------------------------
    # Build prompt
    # -----------------------------------------------------

    prompt = f"""
You are an AI document analysis assistant.

The user wants to understand what the
document contains.

The supplied context contains either the
complete document or representative sections
from different parts of the document.

Use ONLY the supplied document content.

Answer the user's question directly.

If the user asks what is inside the document,
provide a useful overview containing:

- what the document is about
- its main purpose
- major topics
- important requirements
- important features
- important user roles
- important technical details
- other significant information

IMPORTANT RULES:

1. Do NOT use outside knowledge.

2. Do NOT invent facts.

3. Only state information supported by
   the supplied document context.

4. You may combine information from different
   sections.

5. Do not mention that only representative
   sections were provided.

6. Keep the response concise but informative.

7. Cite relevant evidence using:
   [Source X]

DOCUMENT CONTEXT:

{context}

USER QUESTION:

{question}

ANSWER:
"""

    return await generate(
        prompt
    )


# =========================================================
# RAG CHAT
# =========================================================

@app.post(
    "/api/chat",
    response_model=ChatResponse,
)
async def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
):
    try:

        # =====================================================
        # 1. Detect broad document questions
        # =====================================================

        question_lower = (
            request.question
            .lower()
            .strip()
        )

        broad_question_patterns = [
            "what's inside",
            "what is inside",
            "what's in this document",
            "what is in this document",
            "what does this document contain",
            "what is this document about",
            "what's this document about",
            "give me an introduction",
            "give me a brief introduction",
            "brief introduction",
            "summarize this document",
            "summarise this document",
            "summary of this document",
            "give me a summary",
            "what are the main points",
            "what are the main topics",
            "overview of this document",
            "give me an overview",
            "tell me about this document",
            "explain this document",
            "describe this document",
        ]

        is_broad_question = any(
            pattern in question_lower
            for pattern in broad_question_patterns
        )

        # =====================================================
        # 2. BROAD QUESTION
        # =====================================================

        if is_broad_question:

            statement = (
                select(
                    Chunk,
                    Document,
                )
                .join(
                    Document,
                    Chunk.document_id
                    == Document.id,
                )
                .where(
                    Document.status
                    == "ready"
                )
            )

            # -------------------------------------------------
            # Respect document selection
            # -------------------------------------------------

            if request.document_ids:

                statement = statement.where(
                    Chunk.document_id.in_(
                        request.document_ids
                    )
                )

            # -------------------------------------------------
            # Get chunks in document order
            # -------------------------------------------------

            rows = (
                db.execute(
                    statement.order_by(
                        Chunk.document_id,
                        Chunk.chunk_index,
                    )
                )
                .all()
            )

            if not rows:

                return ChatResponse(
                    answer=(
                        "I could not find any indexed "
                        "document content to summarize."
                    ),
                    sources=[],
                )

            # -------------------------------------------------
            # Fast document summary
            # -------------------------------------------------

            answer = await summarize_document(
                rows,
                request.question,
            )

            # -------------------------------------------------
            # Return only the sources that were actually
            # supplied to the summarization model.
            # -------------------------------------------------

            selected_chunks = (
                select_representative_chunks(
                    rows
                )
            )

            sources = []

            for chunk, document in selected_chunks:

                sources.append(
                    Source(
                        document_id=document.id,
                        filename=document.filename,
                        chunk_id=chunk.id,
                        page=chunk.page,
                        score=1.0,
                        excerpt=chunk.text[:400],
                    )
                )

            return ChatResponse(
                answer=answer,
                sources=sources,
            )

        # =====================================================
        # 3. SPECIFIC QUESTION — VECTOR RAG
        # =====================================================

        question_vector = await embed(
            request.question
        )

        # -----------------------------------------------------
        # Calculate cosine distance
        # -----------------------------------------------------

        distance = (
            Chunk.embedding.cosine_distance(
                question_vector
            )
        )

        statement = (
            select(
                Chunk,
                Document,
                distance.label(
                    "distance"
                ),
            )
            .join(
                Document,
                Chunk.document_id
                == Document.id,
            )
            .where(
                Document.status
                == "ready"
            )
        )

        # -----------------------------------------------------
        # Restrict retrieval to selected documents
        # -----------------------------------------------------

        if request.document_ids:

            statement = statement.where(
                Chunk.document_id.in_(
                    request.document_ids
                )
            )

        # -----------------------------------------------------
        # Retrieve most similar chunks
        # -----------------------------------------------------

        rows = (
            db.execute(
                statement
                .order_by(distance)
                .limit(settings.top_k)
            )
            .all()
        )

        if not rows:

            return ChatResponse(
                answer=(
                    "I could not find any indexed "
                    "document content to answer from."
                ),
                sources=[],
            )

        # =====================================================
        # 4. BUILD RAG CONTEXT
        # =====================================================

        context_parts = []
        sources = []

        for (
            chunk,
            document,
            distance_value,
        ) in rows:

            context_parts.append(
                f"[Source {chunk.id}]\n"
                f"Document: {document.filename}\n"
                f"Page: {chunk.page or 'N/A'}\n"
                f"Content:\n{chunk.text}"
            )

            score = max(
                0.0,
                1.0 - float(
                    distance_value
                ),
            )

            sources.append(
                Source(
                    document_id=document.id,
                    filename=document.filename,
                    chunk_id=chunk.id,
                    page=chunk.page,
                    score=score,
                    excerpt=chunk.text[:400],
                )
            )

        context = "\n\n".join(
            context_parts
        )

        # =====================================================
        # 5. GROUNDED QUESTION-ANSWERING PROMPT
        # =====================================================

        prompt = f"""
You are an AI assistant that answers questions
about uploaded documents.

IMPORTANT RULES:

1. Use ONLY the supplied document context.

2. Do NOT use outside knowledge.

3. Do NOT invent facts.

4. If the requested information exists in
   the context, answer the question directly.

5. You may combine information from multiple
   retrieved sources.

6. If the context genuinely does not contain
   enough information, say:

"I could not find enough information in the provided documents."

7. Cite relevant evidence using [Source X].

8. Keep the answer clear and easy to understand.

DOCUMENT CONTEXT:

{context}

END DOCUMENT CONTEXT.

USER QUESTION:

{request.question}

END USER QUESTION.

Now answer the question using only the
document context.
"""

        # =====================================================
        # 6. GENERATE ANSWER
        # =====================================================

        answer = await generate(
            prompt
        )

        # =====================================================
        # 7. RETURN ANSWER + SOURCES
        # =====================================================

        return ChatResponse(
            answer=answer,
            sources=sources,
        )

    except OllamaError as exc:

        raise HTTPException(
            status_code=503,
            detail=str(exc),
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=f"Chat failed: {exc}",
        )