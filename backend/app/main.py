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

            # -------------------------------------------------
            # Verify embedding dimension
            # -------------------------------------------------

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

        # -------------------------------------------------
        # 9. Return document
        # -------------------------------------------------

        return doc_out(
            db,
            document,
        )

    except Exception as exc:
        # -------------------------------------------------
        # Roll back failed transaction
        # -------------------------------------------------

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
        # -------------------------------------------------
        # 1. Embed the user's question
        # -------------------------------------------------

        question_vector = await embed(
            request.question
        )

        # -------------------------------------------------
        # 2. Calculate cosine distance
        # -------------------------------------------------

        distance = (
            Chunk.embedding.cosine_distance(
                question_vector
            )
        )

        # -------------------------------------------------
        # 3. Build vector search query
        # -------------------------------------------------

        statement = (
            select(
                Chunk,
                Document,
                distance.label("distance"),
            )
            .join(
                Document,
                Chunk.document_id
                == Document.id,
            )
            .where(
                Document.status == "ready"
            )
        )

        # -------------------------------------------------
        # 4. Search only selected documents if specified
        # -------------------------------------------------

        if request.document_ids:
            statement = statement.where(
                Chunk.document_id.in_(
                    request.document_ids
                )
            )

        # -------------------------------------------------
        # 5. Retrieve most similar chunks
        # -------------------------------------------------

        rows = (
            db.execute(
                statement
                .order_by(distance)
                .limit(settings.top_k)
            )
            .all()
        )

        # -------------------------------------------------
        # 6. No chunks found
        # -------------------------------------------------

        if not rows:
            return ChatResponse(
                answer=(
                    "I could not find any indexed "
                    "document content to answer from."
                ),
                sources=[],
            )

        # -------------------------------------------------
        # 7. Build context and source metadata
        # -------------------------------------------------

        context_parts = []
        sources = []

        for chunk, document, dist in rows:

            source_text = (
                f"[Source {chunk.id}]\n"
                f"Document: {document.filename}\n"
                f"Page: {chunk.page or 'N/A'}\n"
                f"Content:\n{chunk.text}"
            )

            context_parts.append(
                source_text
            )

            # Convert cosine distance to a simple
            # similarity-like score.
            score = max(
                0.0,
                1.0 - float(dist),
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

        # -------------------------------------------------
        # 8. Combine retrieved chunks
        # -------------------------------------------------

        context = "\n\n".join(
            context_parts
        )

        # -------------------------------------------------
        # 9. Create RAG prompt
        # -------------------------------------------------

        prompt = f"""
You are a document question-answering assistant.

Your job is to answer the user's question using ONLY
the information contained in DOCUMENT CONTEXT.

Do NOT use your general knowledge.

Do NOT guess.

Do NOT invent information.

If the answer is clearly present in the document context,
answer the question directly.

If the answer is not present in the document context,
respond exactly:

I could not find enough information in the provided documents.

When you use information from a source, cite the source ID,
for example:

[Source 14]

================ DOCUMENT CONTEXT ================

{context}

================ END DOCUMENT CONTEXT ================

================ USER QUESTION ================

{request.question}

================ END USER QUESTION ================

Answer the user's question using only the document context.
"""

        # -------------------------------------------------
        # 10. Generate answer
        # -------------------------------------------------

        answer = await generate(
            prompt
        )

        # -------------------------------------------------
        # 11. Return answer and sources
        # -------------------------------------------------

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