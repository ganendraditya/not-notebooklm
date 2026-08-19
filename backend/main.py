import os
import re
import uuid
import shutil
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, StreamingResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List
import zipfile
import io
import urllib.request

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

UPLOAD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "uploads"))
os.makedirs(UPLOAD_DIR, exist_ok=True)

def get_doc_file_path(chat_id: str, filename: str) -> str:
    """Returns absolute file path for a chat document across working directories."""
    p1 = os.path.join(UPLOAD_DIR, f"{chat_id}_{filename}")
    if os.path.exists(p1):
        return p1
    p2 = os.path.abspath(os.path.join(os.getcwd(), "uploads", f"{chat_id}_{filename}"))
    if os.path.exists(p2):
        return p2
    return p1

@app.post("/chats", response_model=models.ChatSessionResponse)
def create_chat(chat: models.ChatSessionCreate, db: Session = Depends(get_db)):
    chat_id = str(uuid.uuid4())
    now = datetime.utcnow()
    db_chat = ChatSession(id=chat_id, title=chat.title, created_at=now, updated_at=now)
    db.add(db_chat)
    db.commit()
    db.refresh(db_chat)
    return db_chat

@app.get("/chats", response_model=List[models.ChatSessionResponse])
def get_chats(db: Session = Depends(get_db)):
    return db.query(ChatSession).order_by(ChatSession.updated_at.desc(), ChatSession.created_at.desc()).all()

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
    chat.updated_at = datetime.utcnow()
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
        
    file_path = os.path.join(UPLOAD_DIR, f"{chat_id}_{file.filename}")
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
    file_path = get_doc_file_path(chat_id, doc.filename)
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
        file_path = get_doc_file_path(chat_id, doc.filename)
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
        
    file_path = get_doc_file_path(chat_id, doc.filename)
    if not os.path.exists(file_path):
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(f"# {doc.filename}\n\nDokumen referensi terdaftar.")
            
    return FileResponse(
        path=file_path,
        filename=doc.filename,
        media_type="application/octet-stream"
    )

@app.get("/chats/{chat_id}/documents/{doc_id}/raw")
def view_document_raw(chat_id: str, doc_id: int, db: Session = Depends(get_db)):
    """Serves file inline with proper MIME type for embedded PDF and text viewer."""
    doc = db.query(Document).filter(Document.id == doc_id, Document.chat_id == chat_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    file_path = get_doc_file_path(chat_id, doc.filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found on disk")
        
    ext = os.path.splitext(doc.filename)[1].lower()
    media_type = "application/pdf" if ext == ".pdf" else "text/plain; charset=utf-8"
    
    return FileResponse(
        path=file_path,
        media_type=media_type,
        headers={"Content-Disposition": f'inline; filename="{doc.filename}"'}
    )

@app.get("/chats/{chat_id}/documents/{doc_id}/pdf_stream")
def stream_document_pdf(chat_id: str, doc_id: int, db: Session = Depends(get_db)):
    """Serves raw PDF bytes for local uploaded PDFs or proxies open-access PDF streams for canvas rendering."""
    doc = db.query(Document).filter(Document.id == doc_id, Document.chat_id == chat_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    file_path = get_doc_file_path(chat_id, doc.filename)
    ext = os.path.splitext(doc.filename)[1].lower()
    
    # 1. Local real binary PDF uploaded by user
    if os.path.exists(file_path) and ext == ".pdf":
        try:
            with open(file_path, "rb") as f:
                header = f.read(5)
                if header.startswith(b"%PDF"):
                    return FileResponse(path=file_path, media_type="application/pdf")
        except Exception:
            pass
            
    # 2. Check if paper has an Open Access PDF URL resolved via DOI / OpenAlex
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read(2000)
                doi_match = re.search(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+", content)
                clean_title = os.path.splitext(doc.filename)[0].replace("_", " ").strip()
                if doi_match or clean_title:
                    meta = rag.resolve_paper_metadata_by_doi(doi_match.group(0) if doi_match else "", clean_title)
                    if meta and meta.get("pdf_url"):
                        pdf_url = meta["pdf_url"]
                        req = urllib.request.Request(pdf_url, headers={
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                        })
                        with urllib.request.urlopen(req, timeout=10) as resp:
                            pdf_bytes = resp.read()
                            if pdf_bytes.startswith(b"%PDF"):
                                return Response(content=pdf_bytes, media_type="application/pdf")
        except Exception:
            pass
            
    raise HTTPException(status_code=404, detail="No PDF available for this document")

@app.get("/chats/{chat_id}/documents/{doc_id}/content")
def get_document_content(chat_id: str, doc_id: int, db: Session = Depends(get_db)):
    """Extracts and returns rich Consensus.app-style structured metadata & authentic abstract for paper view."""
    doc = db.query(Document).filter(Document.id == doc_id, Document.chat_id == chat_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    file_path = get_doc_file_path(chat_id, doc.filename)
    clean_filename_title = os.path.splitext(doc.filename)[0].replace("_", " ").strip()
    
    # Base Consensus-style model payload
    res_data = {
        "id": doc.id,
        "filename": doc.filename,
        "created_at": doc.created_at,
        "type": os.path.splitext(doc.filename)[1].lower().replace(".", "") or "pdf",
        "title": clean_filename_title,
        "authors": [],
        "publication_date": "",
        "year": "",
        "journal": "",
        "journal_metric": "Peer-Reviewed",
        "citations": 0,
        "doi": "",
        "url": "",
        "pdf_url": "",
        "abstract": "",
        "content": ""
    }
    
    if not os.path.exists(file_path):
        res_data["content"] = f"# {doc.filename}\n\n*Document file is registered as a reference source.*"
        res_data["abstract"] = "Document content is registered in the source index."
        return res_data
        
    ext = os.path.splitext(doc.filename)[1].lower()
    raw_content = ""
    try:
        if ext == ".pdf":
            with open(file_path, "rb") as f:
                header = f.read(5)
            if header.startswith(b"%PDF"):
                import pymupdf4llm
                raw_content = pymupdf4llm.to_markdown(file_path)
            else:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    raw_content = f.read()
        elif ext in (".docx", ".doc"):
            raw_content = rag.parse_docx_file(file_path)
        elif ext in (".bib", ".bibtex"):
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                raw_content = rag.parse_bibtex_text(f.read())
        elif ext == ".ris":
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                raw_content = rag.parse_ris_text(f.read())
        elif ext in (".csv", ".tsv"):
            raw_content = rag.parse_csv_file(file_path)
        else:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                raw_content = f.read()
    except Exception as e:
        raw_content = f"Error reading document: {str(e)}"
        
    res_data["content"] = raw_content
    
    # Extract structured fields from raw_content first (Instant Sub-Millisecond Path)
    title_match = re.search(r"#+\s*\**([^\n\*]+)\**", raw_content)
    if title_match:
        extracted_title = title_match.group(1).strip()
        # Remove trailing year e.g. " (2024)"
        year_in_title = re.search(r"\((\d{4})\)$", extracted_title)
        if year_in_title:
            res_data["year"] = year_in_title.group(1)
            res_data["title"] = extracted_title[:year_in_title.start()].strip()
        else:
            res_data["title"] = extracted_title
            
    doi_match = re.search(r"DOI:\*?\*?\s*([^\s\n\*\)]+)", raw_content)
    extracted_doi = doi_match.group(1).strip() if doi_match else ""
    if not extracted_doi:
        doi_regex_match = re.search(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+", raw_content)
        if doi_regex_match:
            extracted_doi = doi_regex_match.group(0).strip()
    res_data["doi"] = extracted_doi
    
    url_match = re.search(r"URL:\*?\*?\s*([^\s\n\*\)]+)", raw_content)
    if url_match:
        res_data["url"] = url_match.group(1).strip()
    elif extracted_doi:
        res_data["url"] = f"https://doi.org/{extracted_doi}"
        
    abs_match = re.search(r"##\s*Abstract[^\n]*\n+([\s\S]+)", raw_content)
    local_abstract = abs_match.group(1).strip() if abs_match else ""
    if local_abstract and rag.is_valid_abstract_content(local_abstract):
        res_data["abstract"] = rag.clean_academic_abstract(local_abstract)
        res_data["abstract_type"] = "official"
        
    # Resolve metadata (authors, journal, citations, pub date) from cache / fast engine
    if extracted_doi or res_data["title"]:
        meta = rag.resolve_paper_metadata_by_doi(extracted_doi, title_fallback=res_data["title"] or clean_filename_title)
        if meta:
            res_data["title"] = meta.get("title") or res_data["title"] or clean_filename_title
            res_data["authors"] = meta.get("authors", []) or res_data["authors"]
            res_data["publication_date"] = meta.get("publication_date", "") or res_data["publication_date"]
            res_data["year"] = meta.get("year", res_data["year"]) or res_data["year"]
            res_data["journal"] = meta.get("journal", "") or res_data["journal"]
            res_data["journal_metric"] = meta.get("journal_metric", "Peer-Reviewed")
            res_data["citations"] = meta.get("citations", 0)
            res_data["doi"] = meta.get("doi", extracted_doi)
            res_data["url"] = meta.get("url", res_data["url"])
            res_data["pdf_url"] = meta.get("pdf_url", "")
            if not res_data["abstract"] and meta.get("abstract"):
                res_data["abstract"] = meta.get("abstract")
                res_data["abstract_type"] = meta.get("abstract_type", "official")
                
            # Heal file on disk with clean metadata & authentic abstract if it was previously invalid or minimal
            if meta.get("abstract") and (not rag.is_valid_abstract_content(local_abstract) or len(raw_content) < 350):
                new_saved_content = f"# {res_data['title']} ({res_data['year']})\n\n**DOI:** {res_data['doi']}  \n**URL:** {res_data['url']}  \n\n## Abstract & Overview\n\n{res_data['abstract']}\n"
                try:
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(new_saved_content)
                except Exception:
                    pass
                    
    if not res_data["abstract"]:
        # Fallback AI Executive Summary
        res_data["abstract_type"] = "ai_summary"
        res_data["abstract"] = rag.clean_academic_abstract(
            f"This scholarly article investigates '{res_data['title']}' ({res_data['year'] or 'Recent publication'}). "
            f"The research presents methodology, computational framework, and empirical analysis in this domain. "
            f"Indexed in international academic indexing services (DOI: {extracted_doi or 'N/A'})."
        )
            
    return res_data

@app.post("/chats/{chat_id}/documents/bulk_download")
def bulk_download_documents(chat_id: str, req: models.BulkDeleteRequest, db: Session = Depends(get_db)):
    """Bundles multiple documents into a single ZIP archive or serves single file directly."""
    docs = db.query(Document).filter(Document.id.in_(req.doc_ids), Document.chat_id == chat_id).all()
    if not docs:
        raise HTTPException(status_code=404, detail="No documents found")
        
    # If 1 file selected: return direct file
    if len(docs) == 1:
        doc = docs[0]
        file_path = get_doc_file_path(chat_id, doc.filename)
        if not os.path.exists(file_path):
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(f"# {doc.filename}\n\nDokumen referensi NotbookLM.")
        return FileResponse(
            path=file_path,
            filename=doc.filename,
            media_type="application/pdf"
        )
        
    # Multiple files: Create ZIP stream in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for doc in docs:
            file_path = get_doc_file_path(chat_id, doc.filename)
            if os.path.exists(file_path):
                zip_file.write(file_path, arcname=doc.filename)
            else:
                zip_file.writestr(doc.filename, f"# {doc.filename}\n\nDokumen referensi NotbookLM.")
                
    zip_buffer.seek(0)
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=notbooklm_sources_{chat_id[:8]}.zip"}
    )

@app.get("/search_papers", response_model=List[models.PaperCandidate])
@app.get("/papers/search", response_model=List[models.PaperCandidate])
async def search_papers(query: str, limit: int = 10):
    if not query.strip():
        return []
        
    ninerouter_llm, freellm_llm, gemini_llm, groq_llm = rag.create_llm_instances()
    active_llm = ninerouter_llm or freellm_llm or gemini_llm or groq_llm
    
    plan = await rag.plan_academic_search(query.strip(), None, active_llm)
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
    chat = db.query(ChatSession).filter(ChatSession.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
        
    # Check limit: Maximum 50 documents per chat
    current_doc_count = db.query(Document).filter(Document.chat_id == chat_id).count()
    remaining_slots = max(0, 50 - current_doc_count)
    if remaining_slots <= 0:
        raise HTTPException(status_code=400, detail="Document limit reached (Max 50 documents per chat). Please delete some sources before importing new ones.")
        
    allowed_sources = req.sources[:remaining_slots]
    
    created_docs = []
    for paper in allowed_sources:
        # Clean filename
        clean_title = re.sub(r'[^a-zA-Z0-9_\-\. ]', '', paper.title).strip()
        if len(clean_title) > 60:
            clean_title = clean_title[:60]
        filename = f"{clean_title}.pdf"
        
        abstract_text = paper.snippet.strip()
        if not rag.is_valid_abstract_content(abstract_text) and paper.doi:
            fetched_abs = rag.fetch_full_abstract_by_doi(paper.doi)
            if fetched_abs and rag.is_valid_abstract_content(fetched_abs):
                abstract_text = fetched_abs
        
        # Prepare structured text content
        doc_text = f"# {paper.title} ({paper.year})\n\n"
        if paper.doi:
            doc_text += f"**DOI:** {paper.doi}  \n"
        if paper.url:
            doc_text += f"**URL:** {paper.url}  \n\n"
        doc_text += f"## Abstract & Overview\n\n{abstract_text}\n"
        
        # Ingest into vector store
        try:
            rag.ingest_document_text(doc_text, filename, chat_id)
            save_path = os.path.join(UPLOAD_DIR, f"{chat_id}_{filename}")
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(doc_text)
        except Exception as e:
            print(f"[Import Source Error]: {e}")
            
        # Save to database
        db_doc = Document(chat_id=chat_id, filename=filename)
        db.add(db_doc)
        db.commit()
        db.refresh(db_doc)
        created_docs.append(db_doc)
        
    db_chat.updated_at = datetime.utcnow()
    db.commit()
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
    db_chat.updated_at = datetime.utcnow()
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
    db_chat.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(assistant_msg)
    
    return assistant_msg

@app.post("/chats/{chat_id}/edit_message", response_model=models.ChatMessageResponse)
async def edit_message(chat_id: str, req: models.EditMessageRequest, db: Session = Depends(get_db)):
    """Edits a previous user message, revokes all subsequent messages, and regenerates a new assistant response."""
    db_chat = db.query(ChatSession).filter(ChatSession.id == chat_id).first()
    if not db_chat:
        raise HTTPException(status_code=404, detail="Chat not found")
        
    # Delete from message_index onwards in SQLite
    all_msgs = db.query(ChatMessage).filter(ChatMessage.chat_id == chat_id).order_by(ChatMessage.id.asc()).all()
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
    db_chat.updated_at = datetime.utcnow()
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
    db_chat.updated_at = datetime.utcnow()
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

