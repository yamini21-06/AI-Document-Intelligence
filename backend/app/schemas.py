from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    filename: str
    content_type: str
    status: str
    error: str | None = None
    created_at: datetime
    chunks: int = 0

class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    document_ids: list[int] | None = None

class Source(BaseModel):
    document_id: int
    filename: str
    chunk_id: int
    page: int | None
    score: float
    excerpt: str

class ChatResponse(BaseModel):
    answer: str
    sources: list[Source]
