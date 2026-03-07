from pydantic import BaseModel
from datetime import datetime

class KnowledgeSpace(BaseModel):
    id: str
    name: str
    created_at: datetime

class DocumentInfo(BaseModel):
    id: str
    space_id: str
    filename: str
    status: str  # pending | processing | done | failed

class IngestionJob(BaseModel):
    id: str
    space_id: str
    document_id: str
    status: str
