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
    is_pinned: Optional[bool] = False
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class PinChatRequest(BaseModel):
    is_pinned: bool

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

class AttachmentModel(BaseModel):
    type: str
    filename: str
    url: str

class ChatMessageResponse(BaseModel):
    role: str
    content: str
    created_at: datetime
    attachments: Optional[List[AttachmentModel]] = None
    
    class Config:
        from_attributes = True

class ChatQuery(BaseModel):
    message: str
    attachments: Optional[List[AttachmentModel]] = None

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

class BulkDeleteChatsRequest(BaseModel):
    chat_ids: List[str]

class StorageSummaryResponse(BaseModel):
    uploads_bytes: int
    uploads_count: int
    qdrant_bytes: int
    database_bytes: int
    total_bytes: int

class RenameDocumentRequest(BaseModel):
    title: str


