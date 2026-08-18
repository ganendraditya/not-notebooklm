from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class ChatSessionCreate(BaseModel):
    title: str = "New Chat"

class ChatSessionResponse(BaseModel):
    id: str
    title: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class DocumentResponse(BaseModel):
    id: int
    filename: str
    created_at: datetime
    
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
