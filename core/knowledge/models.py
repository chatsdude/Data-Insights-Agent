from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel


class KnowledgeSpaceCreate(BaseModel):
    name: str


class KnowledgeSpaceInfo(BaseModel):
    id: str
    name: str
    created_at: str


class DocumentInfo(BaseModel):
    id: str
    space_id: str
    filename: str
    content_type: Optional[str] = None
    status: Literal["uploaded", "processing", "completed", "failed"] = "uploaded"
    created_at: str


class IngestionJobInfo(BaseModel):
    id: str
    space_id: str
    document_id: str
    status: Literal["queued", "processing", "completed", "failed"] = "queued"
    stage: str = "queued"
    progress: int = 0
    error: Optional[str] = None
    created_at: str
    updated_at: str

