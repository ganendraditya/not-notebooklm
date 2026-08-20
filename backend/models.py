from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class ChatSessionCreate(BaseModel):
    title: str = "New Chat"

class ChatSessionUpdate(BaseModel):
    title: str

class ChatSessionResponse(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class DocumentResponse(BaseModel):
    id: int
    filename: str
    title: Optional[str] = None
    created_at: datetime
    index: Optional[int] = None
    has_full_pdf: Optional[bool] = True
    is_oa: Optional[bool] = True
    
    class Config:
        from_attributes = True

class ChatMessageResponse(BaseModel):
    role: str
    content: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class ChatQuery(BaseModel):
    message: str

class ChatSessionDetailResponse(ChatSessionResponse):
    documents: List[DocumentResponse] = []
    messages: List[ChatMessageResponse] = []

    class Config:
        from_attributes = True

class PaperCandidate(BaseModel):
    title: str
    year: Optional[str] = "N/A"
    doi: Optional[str] = ""
    url: Optional[str] = ""
    snippet: Optional[str] = ""
    authors: Optional[List[str]] = []
    venue: Optional[str] = ""
    pdf_url: Optional[str] = ""
    is_oa: Optional[bool] = True
    journal_metric: Optional[str] = ""
    citations: Optional[int] = 0

class ImportDoiRequest(BaseModel):
    doi: str

class ImportSourcesRequest(BaseModel):
    sources: List[PaperCandidate]

class EditMessageRequest(BaseModel):
    message_index: int
    message: str

class BulkDeleteRequest(BaseModel):
    doc_ids: List[int]

class RenameDocumentRequest(BaseModel):
    title: str


