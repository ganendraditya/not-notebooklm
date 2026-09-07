from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class ChatSessionCreate(BaseModel):
    title: str = "New Chat"

class ChatSessionUpdate(BaseModel):
    title: str

class ChatSessionResponse(BaseModel):
    model_config = {"from_attributes": True}
    id: str
    title: str
    is_pinned: Optional[bool] = False
    created_at: datetime
    updated_at: Optional[datetime] = None

class PinChatRequest(BaseModel):
    is_pinned: bool

class DocumentResponse(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    filename: str
    title: Optional[str] = None
    created_at: datetime
    index: Optional[int] = None
    has_full_pdf: Optional[bool] = True
    is_oa: Optional[bool] = True

class AttachmentModel(BaseModel):
    type: str
    filename: str
    url: str

class ChatMessageResponse(BaseModel):
    model_config = {"from_attributes": True}
    role: str
    content: str
    created_at: datetime
    attachments: Optional[List[AttachmentModel]] = None
    variants: Optional[List[str]] = None
    active_variant_index: Optional[int] = 0

class ChatQuery(BaseModel):
    message: str
    attachments: Optional[List[AttachmentModel]] = None

class ChatSessionDetailResponse(ChatSessionResponse):
    model_config = {"from_attributes": True}
    documents: List[DocumentResponse] = []
    messages: List[ChatMessageResponse] = []

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

class RegenerateMessageRequest(BaseModel):
    message_index: int # index of the assistant message to regenerate

class SelectVariantRequest(BaseModel):
    message_index: int
    variant_index: int

class BulkDeleteRequest(BaseModel):
    doc_ids: List[int]

class BulkDownloadRequest(BaseModel):
    doc_ids: List[int]

class BulkDeleteChatsRequest(BaseModel):
    chat_ids: List[str]

class RenameDocumentRequest(BaseModel):
    title: str


