import os
import re
import uuid
import shutil
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List
import zipfile
import io

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
    chat = db.query(ChatSession).filter(ChatSession.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    return chat

@app.patch("/chats/{chat_id}", response_model=models.ChatSessionResponse)
def update_chat(chat_id: str, update: models.ChatSessionUpdate, db: Session = Depends(get_db)):
    chat = db.query(ChatSession).filter(ChatSession.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    chat.title = update.title
    db.commit()
    db.refresh(chat)
    return chat

@app.delete("/chats/{chat_id}")
def delete_chat(chat_id: str, db: Session = Depends(get_db)):
    db_chat = db.query(ChatSession).filter(ChatSession.id == chat_id).first()
    if not db_chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    # Delete related messages and documents
    db.query(ChatMessage).filter(ChatMessage.chat_id == chat_id).delete()
    db.query(Document).filter(Document.chat_id == chat_id).delete()
    db.delete(db_chat)
    db.commit()
    return {"status": "success", "message": "Chat deleted"}

MAX_SOURCES_PER_CHAT = 250

@app.post("/chats/{chat_id}/upload", response_model=models.DocumentResponse)
def upload_document(chat_id: str, file: UploadFile = File(...), db: Session = Depends(get_db)):
    db_chat = db.query(ChatSession).filter(ChatSession.id == chat_id).first()
    if not db_chat:
        raise HTTPException(status_code=404, detail="Chat not found")
        
    existing_count = db.query(Document).filter(Document.chat_id == chat_id).count()
    if existing_count >= MAX_SOURCES_PER_CHAT:
        raise HTTPException(status_code=400, detail=f"Batas maksimal tercapai! Percakapan ini sudah memiliki {existing_count}/250 sumber.")
        
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

@app.delete("/chats/{chat_id}/documents/{doc_id}")
def delete_document(chat_id: str, doc_id: int, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == doc_id, Document.chat_id == chat_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    file_path = f"uploads/{chat_id}_{doc.filename}"
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception:
            pass
    db.delete(doc)
    db.commit()
    return {"status": "success"}

@app.post("/chats/{chat_id}/documents/bulk_delete")
def bulk_delete_documents(chat_id: str, req: models.BulkDeleteRequest, db: Session = Depends(get_db)):
    """Deletes multiple documents in a single bulk operation."""
    docs = db.query(Document).filter(Document.id.in_(req.doc_ids), Document.chat_id == chat_id).all()
    for doc in docs:
        file_path = f"uploads/{chat_id}_{doc.filename}"
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass
        db.delete(doc)
    db.commit()
    return {"status": "success", "deleted_count": len(docs)}

@app.get("/chats/{chat_id}/documents/{doc_id}/download")
def download_document(chat_id: str, doc_id: int, db: Session = Depends(get_db)):
    """Serves file download for a single imported or uploaded document."""
    doc = db.query(Document).filter(Document.id == doc_id, Document.chat_id == chat_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    file_path = f"uploads/{chat_id}_{doc.filename}"
    if not os.path.exists(file_path):
        os.makedirs("uploads", exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(f"# {doc.filename}\n\nDokumen referensi terdaftar.")
            
    return FileResponse(
        path=file_path,
        filename=doc.filename,
        media_type="application/octet-stream"
    )

@app.post("/chats/{chat_id}/documents/bulk_download")
def bulk_download_documents(chat_id: str, req: models.BulkDeleteRequest, db: Session = Depends(get_db)):
    """Bundles multiple documents into a single ZIP archive or serves single file directly."""
    docs = db.query(Document).filter(Document.id.in_(req.doc_ids), Document.chat_id == chat_id).all()
    if not docs:
        raise HTTPException(status_code=404, detail="No documents found")
        
    # If 1 file selected: return direct file
    if len(docs) == 1:
        doc = docs[0]
        file_path = f"uploads/{chat_id}_{doc.filename}"
        if not os.path.exists(file_path):
            os.makedirs("uploads", exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(f"# {doc.filename}\n\nDokumen referensi NotbookLM.")
        return FileResponse(
            path=file_path,
            filename=doc.filename,
            media_type="application/octet-stream"
        )
        
    # If > 1 files: bundle into ZIP archive stream
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for doc in docs:
            file_path = f"uploads/{chat_id}_{doc.filename}"
            if os.path.exists(file_path):
                zip_file.write(file_path, arcname=doc.filename)
            else:
                zip_file.writestr(doc.filename, f"# {doc.filename}\n\nDokumen referensi NotbookLM.")
                
    zip_buffer.seek(0)
    zip_filename = f"NotbookLM_Sources_{len(docs)}_files.zip"
    
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{zip_filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition"
        }
    )

@app.get("/search_papers", response_model=List[models.PaperCandidate])
async def search_papers(query: str, limit: int = 10):
    """Searches OpenAlex & Crossref with Consensus-style AI Query Planner & balanced bilingual retriever."""
    if not query.strip():
        return []
        
    # 1. Use the LLM-Powered Academic Query Planner
    ninerouter_llm, freellm_llm, gemini_llm, groq_llm = rag.create_llm_instances()
    active_llm = ninerouter_llm or freellm_llm or gemini_llm or groq_llm
    
    plan = await rag.plan_academic_search(query.strip(), None, active_llm)
    
    # If limit was explicitly passed (e.g., from UI selector), respect if higher than default
    if limit and limit != 10:
        plan["target_count"] = max(limit, plan.get("target_count", 10))
        
    papers = rag.search_academic_papers_planned(plan)
    return [
        models.PaperCandidate(
            title=p.get("title", "Untitled"),
            year=str(p.get("year", "N/A")),
            doi=p.get("doi", ""),
            url=p.get("url", ""),
            snippet=p.get("snippet", "")
        )
        for p in papers
    ]

@app.post("/chats/{chat_id}/import_sources", response_model=List[models.DocumentResponse])
def import_sources(chat_id: str, req: models.ImportSourcesRequest, db: Session = Depends(get_db)):
    """Imports selected paper candidates as RAG sources/documents into the chat session."""
    db_chat = db.query(ChatSession).filter(ChatSession.id == chat_id).first()
    if not db_chat:
        raise HTTPException(status_code=404, detail="Chat not found")
        
    existing_count = db.query(Document).filter(Document.chat_id == chat_id).count()
    if existing_count >= MAX_SOURCES_PER_CHAT:
        raise HTTPException(status_code=400, detail="Batas maksimal tercapai! Percakapan ini sudah memiliki 250 sumber.")
        
    allowed_sources = req.sources[:max(0, MAX_SOURCES_PER_CHAT - existing_count)]
    created_docs = []
    for paper in allowed_sources:
        # Clean filename
        clean_title = re.sub(r'[^a-zA-Z0-9_\-\. ]', '', paper.title).strip()
        if len(clean_title) > 60:
            clean_title = clean_title[:60]
        filename = f"{clean_title}.pdf"
        
        # Prepare structured text content
        doc_text = f"# {paper.title} ({paper.year})\n"
        if paper.doi:
            doc_text += f"**DOI:** {paper.doi}\n"
        if paper.url:
            doc_text += f"**URL:** {paper.url}\n\n"
        doc_text += f"## Abstract & Overview\n{paper.snippet}\n"
        
        # Ingest into vector store
        try:
            rag.ingest_document_text(doc_text, filename, chat_id)
            with open(f"uploads/{chat_id}_{filename}", "w", encoding="utf-8") as f:
                f.write(doc_text)
        except Exception as e:
            print(f"[Import Source Error]: {e}")
            
        # Save to database
        db_doc = Document(chat_id=chat_id, filename=filename)
        db.add(db_doc)
        db.commit()
        db.refresh(db_doc)
        created_docs.append(db_doc)
        
    return created_docs

@app.post("/chats/{chat_id}/message", response_model=models.ChatMessageResponse)
async def send_message(chat_id: str, query: models.ChatQuery, db: Session = Depends(get_db)):
    db_chat = db.query(ChatSession).filter(ChatSession.id == chat_id).first()
    if not db_chat:
        raise HTTPException(status_code=404, detail="Chat not found")
        
    # Retrieve previous conversation history (token-compact, up to last 6 messages)
    history_records = db.query(ChatMessage).filter(ChatMessage.chat_id == chat_id).order_by(ChatMessage.id.asc()).all()
    chat_history = []
    for h in history_records[-6:]:
        content = h.content.strip()
        if not content.startswith("⚠️") and len(content) > 0:
            if h.role == "assistant" and len(content) > 250:
                content = content[:250] + "..."
            chat_history.append({"role": h.role, "content": content})
    
    # Save User Message
    user_msg = ChatMessage(chat_id=chat_id, role="user", content=query.message)
    db.add(user_msg)
    db.commit()
    
    # Query RAG with conversation history
    try:
        response_text = await rag.query_chat(chat_id, query.message, chat_history=chat_history)
    except Exception as e:
        import traceback
        traceback.print_exc()
        response_text = f"⚠️ Maaf, terjadi kesalahan saat menghubungi server AI: {str(e)}"
        
    # Save Assistant Message (persisted in database even on error)
    assistant_msg = ChatMessage(chat_id=chat_id, role="assistant", content=response_text)
    db.add(assistant_msg)
    db.commit()
    db.refresh(assistant_msg)
    
    return assistant_msg

@app.post("/chats/{chat_id}/edit_message", response_model=models.ChatMessageResponse)
async def edit_message(chat_id: str, req: models.EditMessageRequest, db: Session = Depends(get_db)):
    """Edits a previous user message, revokes all subsequent messages, and regenerates a new assistant response."""
    db_chat = db.query(ChatSession).filter(ChatSession.id == chat_id).first()
    if not db_chat:
        raise HTTPException(status_code=404, detail="Chat not found")
        
    # Get all existing messages in order
    all_msgs = db.query(ChatMessage).filter(ChatMessage.chat_id == chat_id).order_by(ChatMessage.id.asc()).all()
    
    # Delete from message_index onwards in SQLite
    if 0 <= req.message_index < len(all_msgs):
        msgs_to_delete = all_msgs[req.message_index:]
        for m in msgs_to_delete:
            db.delete(m)
        db.commit()
        
    # Retrieve conversation history strictly before the edited index
    remaining_msgs = db.query(ChatMessage).filter(ChatMessage.chat_id == chat_id).order_by(ChatMessage.id.asc()).all()
    chat_history = []
    for h in remaining_msgs[-6:]:
        content = h.content.strip()
        if not content.startswith("⚠️") and len(content) > 0:
            if h.role == "assistant" and len(content) > 250:
                content = content[:250] + "..."
            chat_history.append({"role": h.role, "content": content})
            
    # Save User's Edited Message
    user_msg = ChatMessage(chat_id=chat_id, role="user", content=req.message)
    db.add(user_msg)
    db.commit()
    
    # Query RAG with updated conversation history
    try:
        response_text = await rag.query_chat(chat_id, req.message, chat_history=chat_history)
    except Exception as e:
        import traceback
        traceback.print_exc()
        response_text = f"⚠️ Maaf, terjadi kesalahan saat menghubungi server AI: {str(e)}"
        
    # Save Assistant Response
    assistant_msg = ChatMessage(chat_id=chat_id, role="assistant", content=response_text)
    db.add(assistant_msg)
    db.commit()
    db.refresh(assistant_msg)
    
    return assistant_msg

@app.get("/llm/models")
def get_llm_models():
    """Returns the list of available frontier & local models, along with the active one."""
    current_model = os.getenv("NINEROUTER_MODEL", "ag/gemini-3.7-flash-high")
    current_provider = os.getenv("LLM_PROVIDER", "ninerouter")
    
    available = [
        {"id": "ag/gemini-3.7-flash-high", "name": "Gemini 3.7 Flash High", "provider": "Google DeepMind (9Router)", "badge": "⚡ Fast & Smart"},
        {"id": "ag/claude-sonnet-4-6", "name": "Claude 3.7 Sonnet", "provider": "Anthropic (9Router)", "badge": "🧠 Frontier Reasoning"},
        {"id": "ag/gemini-3.6-flash-high", "name": "Gemini 3.6 Flash", "provider": "Google (9Router)", "badge": "🚀 High Speed"},
        {"id": "ag/claude-opus-4-6-thinking", "name": "Claude 3.7 Opus (Thinking)", "provider": "Anthropic (9Router)", "badge": "💭 Deep Thinking"},
        {"id": "ag/gpt-oss-120b-medium", "name": "GPT-OSS 120B", "provider": "OpenAI-OSS (9Router)", "badge": "🌐 Open Source"},
        {"id": "gemini/gemini-3-flash-preview", "name": "Gemini 3 Flash Preview", "provider": "Google Direct (9Router)", "badge": "🔬 Preview"}
    ]
    return {
        "current_model": current_model,
        "current_provider": current_provider,
        "models": available
    }

@app.post("/llm/models/select")
def select_llm_model(payload: dict):
    """Updates the active model in memory and persists to .env file."""
    model_id = payload.get("model_id", "").strip()
    if not model_id:
        raise HTTPException(status_code=400, detail="model_id is required")
        
    os.environ["NINEROUTER_MODEL"] = model_id
    os.environ["LLM_PROVIDER"] = "ninerouter"
    
    # Persist to .env
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                content = f.read()
            if "NINEROUTER_MODEL=" in content:
                content = re.sub(r'NINEROUTER_MODEL=.*', f'NINEROUTER_MODEL={model_id}', content)
            else:
                content += f"\nNINEROUTER_MODEL={model_id}\n"
            with open(env_path, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            print(f"[Model Switch Error]: {e}")
            
    # Reload in rag.py
    rag.ninerouter_llm, rag.freellm_llm, rag.gemini_llm, rag.groq_llm = rag.create_llm_instances()
    
    return {"status": "ok", "active_model": model_id}

