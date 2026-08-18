import os
import uuid
import shutil
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List

from database import engine, Base, get_db, ChatSession, Document, ChatMessage
import models
import rag

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Not-NotebookLM API")

# Setup CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict this to frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("uploads", exist_ok=True)

@app.post("/chats", response_model=models.ChatSessionResponse)
def create_chat(chat: models.ChatSessionCreate, db: Session = Depends(get_db)):
    chat_id = str(uuid.uuid4())
    db_chat = ChatSession(id=chat_id, title=chat.title)
    db.add(db_chat)
    db.commit()
    db.refresh(db_chat)
    return db_chat

@app.get("/chats", response_model=List[models.ChatSessionResponse])
def get_chats(db: Session = Depends(get_db)):
    return db.query(ChatSession).order_by(ChatSession.created_at.desc()).all()

@app.get("/chats/{chat_id}", response_model=models.ChatSessionDetailResponse)
def get_chat(chat_id: str, db: Session = Depends(get_db)):
    db_chat = db.query(ChatSession).filter(ChatSession.id == chat_id).first()
    if not db_chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    return db_chat

@app.post("/chats/{chat_id}/upload", response_model=models.DocumentResponse)
def upload_document(chat_id: str, file: UploadFile = File(...), db: Session = Depends(get_db)):
    db_chat = db.query(ChatSession).filter(ChatSession.id == chat_id).first()
    if not db_chat:
        raise HTTPException(status_code=404, detail="Chat not found")
        
    file_path = f"uploads/{chat_id}_{file.filename}"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # Ingest document into Qdrant via LlamaIndex
    try:
        rag.ingest_document(file_path, chat_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse document: {str(e)}")
        
    # Save to database
    db_doc = Document(chat_id=chat_id, filename=file.filename)
    db.add(db_doc)
    db.commit()
    db.refresh(db_doc)
    
    return db_doc

@app.post("/chats/{chat_id}/message", response_model=models.ChatMessageResponse)
def send_message(chat_id: str, query: models.ChatQuery, db: Session = Depends(get_db)):
    db_chat = db.query(ChatSession).filter(ChatSession.id == chat_id).first()
    if not db_chat:
        raise HTTPException(status_code=404, detail="Chat not found")
        
    # Save User Message
    user_msg = ChatMessage(chat_id=chat_id, role="user", content=query.message)
    db.add(user_msg)
    db.commit()
    
    # Query RAG
    try:
        response_text = rag.query_chat(chat_id, query.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to query RAG: {str(e)}")
        
    # Save Assistant Message
    assistant_msg = ChatMessage(chat_id=chat_id, role="assistant", content=response_text)
    db.add(assistant_msg)
    db.commit()
    db.refresh(assistant_msg)
    
    return assistant_msg
