import os
import re
import shutil
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from dotenv import load_dotenv, set_key

import rag
from database import get_db, DB_PATH, ChatSession, Document, ChatMessage
from helpers import UPLOAD_DIR, TEMP_ZIPS_DIR
import models

router = APIRouter(tags=["settings"])

def get_dir_size(path: str) -> int:
    """Calculates total recursive byte size of a folder."""
    total = 0
    if not os.path.exists(path):
        return 0
    for root, _, files in os.walk(path):
        for f in files:
            fp = os.path.join(root, f)
            try:
                if not os.path.islink(fp):
                    total += os.path.getsize(fp)
            except Exception:
                pass
    return total

@router.get("/settings/storage/summary", response_model=models.StorageSummaryResponse)
def get_storage_summary():
    """Returns disk usage breakdown across uploads, vector indices, and sqlite database."""
    uploads_size = get_dir_size(UPLOAD_DIR)
    uploads_count = 0
    if os.path.exists(UPLOAD_DIR):
        uploads_count = sum(1 for f in os.listdir(UPLOAD_DIR) if os.path.isfile(os.path.join(UPLOAD_DIR, f)))
        
    qdrant_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "qdrant_data"))
    qdrant_size = get_dir_size(qdrant_dir)
    
    db_size = os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0
    wal_path = f"{DB_PATH}-wal"
    if os.path.exists(wal_path):
        db_size += os.path.getsize(wal_path)
    shm_path = f"{DB_PATH}-shm"
    if os.path.exists(shm_path):
        db_size += os.path.getsize(shm_path)
        
    return models.StorageSummaryResponse(
        uploads_bytes=uploads_size,
        uploads_count=uploads_count,
        qdrant_bytes=qdrant_size,
        database_bytes=db_size,
        total_bytes=uploads_size + qdrant_size + db_size
    )

@router.post("/settings/storage/cleanup")
def cleanup_orphan_storage(db: Session = Depends(get_db)):
    """Scans and deletes orphan files on disk not associated with any active chat session."""
    from services.storage_service import cleanup_orphan_files_on_disk
    active_chats = set(c.id for c in db.query(ChatSession.id).all())
    deleted_files, freed_bytes = cleanup_orphan_files_on_disk(active_chats)
    return {
        "status": "success",
        "deleted_files_count": deleted_files,
        "freed_bytes": freed_bytes
    }

@router.post("/settings/storage/reset")
def factory_reset_storage(payload: dict, db: Session = Depends(get_db)):
    """Wipes all chats, documents, messages, and vector embeddings."""
    confirmation = payload.get("confirm_text", "").strip().lower()
    if confirmation != "reset-all-data":
        raise HTTPException(status_code=400, detail="Invalid confirmation phrase. Type 'reset-all-data' to proceed.")

    # 1. Clear database
    db.query(ChatMessage).delete(synchronize_session=False)
    db.query(Document).delete(synchronize_session=False)
    db.query(ChatSession).delete(synchronize_session=False)
    db.commit()

    # 2. Clear uploads folder
    if os.path.exists(UPLOAD_DIR):
        for fname in os.listdir(UPLOAD_DIR):
            fp = os.path.join(UPLOAD_DIR, fname)
            try:
                if os.path.isfile(fp):
                    os.remove(fp)
            except Exception:
                pass

    # 3. Purge Qdrant collections
    try:
        colls = ["not_notebooklm_bge", "not_notebooklm_gemini", "not_notebooklm"]
        for cname in colls:
            try:
                rag.qdrant_client.delete_collection(collection_name=cname)
            except Exception:
                pass
    except Exception:
        pass

    return {"status": "success", "message": "All application data and workspaces have been reset."}

from fastapi.responses import FileResponse

@router.get("/settings/storage/media/{filename}")
def get_storage_media(filename: str):
    """Serve media files directly to the frontend for attachment previews."""
    import os
    from helpers import CHAT_MEDIA_DIR
    fp = os.path.join(CHAT_MEDIA_DIR, os.path.basename(filename))
    if os.path.exists(fp):
        return FileResponse(fp)
    raise HTTPException(status_code=404, detail="Media not found")

@router.get("/settings/storage/library")
def get_storage_library(category: str = "all", search: str = "", sort: str = "date", db: Session = Depends(get_db)):
    """Returns a list of items for the storage library view (files, images, chats)."""
    items = []
    
    # Files & Images (from documents table)
    if category in ["all", "files", "images"]:
        docs = db.query(Document).all()
        for d in docs:
            is_image = d.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.gif'))
            if category == "files" and is_image:
                continue
            if category == "images" and not is_image:
                continue
                
            if search and search.lower() not in d.filename.lower():
                continue
                
            fp = os.path.join(UPLOAD_DIR, f"{d.chat_id}_{d.filename}")
            size = os.path.getsize(fp) if os.path.exists(fp) else 0
            
            items.append({
                "id": f"doc_{d.id}",
                "type": "image" if is_image else "file",
                "name": d.filename,
                "chat_id": d.chat_id,
                "size_bytes": size,
                "modified": d.created_at.isoformat() if hasattr(d, 'created_at') else "",
                "path": fp
            })
            
    # Chat Media (from chat_media upload folder)
    chat_media_dir = os.path.join(os.path.dirname(__file__), "..", "uploads", "chat_media")
    if os.path.exists(chat_media_dir) and category in ["all", "images"]:
        for fname in os.listdir(chat_media_dir):
            fp = os.path.join(chat_media_dir, fname)
            if not os.path.isfile(fp):
                continue
            
            is_image = fname.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.gif'))
            if category == "images" and not is_image:
                continue
                
            if search and search.lower() not in fname.lower():
                continue
                
            size = os.path.getsize(fp)
            items.append({
                "id": f"media_{fname}",
                "type": "image" if is_image else "file",
                "name": fname,
                "chat_id": None,
                "size_bytes": size,
                "modified": "", # We could get os.path.getmtime if needed
                "path": fp
            })

    # Sort logic
    if sort == "size":
        items.sort(key=lambda x: x["size_bytes"], reverse=True)
    elif sort == "name":
        items.sort(key=lambda x: x["name"].lower())
    else: # date (or default)
        items.sort(key=lambda x: x.get("modified", ""), reverse=True)

    return {"items": items}

@router.post("/settings/storage/library/delete")
def delete_storage_library_items(payload: dict, db: Session = Depends(get_db)):
    """Deletes selected items from disk and DB."""
    item_ids = payload.get("item_ids", [])
    if not item_ids:
        return {"status": "error", "message": "No items selected."}
        
    deleted = 0
    for iid in item_ids:
        if iid.startswith("doc_"):
            doc_id = int(iid.split("_")[1])
            doc = db.query(Document).filter(Document.id == doc_id).first()
            if doc:
                fp = os.path.join(UPLOAD_DIR, f"{doc.chat_id}_{doc.filename}")
                if os.path.exists(fp):
                    os.remove(fp)
                db.delete(doc)
                deleted += 1
        elif iid.startswith("media_"):
            fname = iid.split("media_", 1)[1]
            chat_media_dir = os.path.join(os.path.dirname(__file__), "..", "uploads", "chat_media")
            fp = os.path.join(chat_media_dir, fname)
            if os.path.exists(fp):
                os.remove(fp)
                deleted += 1
                
    db.commit()
    return {"status": "success", "deleted_count": deleted}

@router.get("/llm/models")
def get_llm_models():
    """Returns available LLM providers and models configured in .env."""
    load_dotenv(override=True)
    current_provider = os.getenv("LLM_PROVIDER", "freellmapi").lower()
    current_model = os.getenv("NINEROUTER_MODEL", "ag/gemini-3.7-flash-high") if current_provider == "9router" else os.getenv("FREELLMAPI_MODEL", "gpt-oss-120b")
    
    models_list = [
        {
            "id": "freellmapi",
            "name": "Local LLM Proxy (100% Free / Unlimited)",
            "provider": "freellmapi",
            "model_name": os.getenv("FREELLMAPI_MODEL", "gpt-oss-120b"),
            "description": "Fast local proxy gateway (gpt-oss-120b, claude-sonnet-4-6, qwen-2.5-coder)",
            "active": current_provider == "freellmapi"
        },
        {
            "id": "9router",
            "name": "9Router High-End AI (Fast & Stable)",
            "provider": "9router",
            "model_name": os.getenv("NINEROUTER_MODEL", "ag/claude-sonnet-4-6"),
            "description": "Premium multi-model router via 9Router proxy gateway",
            "active": current_provider == "9router"
        },
        {
            "id": "gemini",
            "name": "Google Gemini 2.5 Flash",
            "provider": "gemini",
            "model_name": "gemini-flash-latest",
            "description": "Fast official Gemini Flash API",
            "active": current_provider == "gemini"
        },
        {
            "id": "groq",
            "name": "Groq Qwen 2.5 32B (Ultra Fast)",
            "provider": "groq",
            "model_name": "qwen/qwen-2.5-32b",
            "description": "High-speed Groq LPUs for rapid response generation",
            "active": current_provider == "groq"
        }
    ]
    
    return {
        "current_provider": current_provider,
        "current_model": current_model,
        "models": models_list
    }

ALLOWED_PROVIDERS = {"9router", "freellmapi", "gemini", "groq", "openai", "local"}

@router.post("/llm/select")
@router.post("/llm/models/select")
def select_llm_model(payload: models.SelectLLMRequest):
    """Dynamically switches active LLM provider and model across the application with validated inputs."""
    provider = payload.provider
    model_name = payload.model_name or payload.model_id
    
    # If model_id passed directly from ModelSelector like "ag/gemini-3.7-flash-high"
    if not provider and model_name:
        if model_name.startswith("ag/") or model_name.startswith("gemini/") or "claude" in model_name:
            provider = "9router"
        elif "gpt-oss" in model_name or "qwen" in model_name:
            provider = "freellmapi"
        else:
            provider = os.getenv("LLM_PROVIDER", "9router")

    if not provider:
        raise HTTPException(status_code=400, detail="Provider is required")
        
    provider = provider.strip().lower()
    if provider not in ALLOWED_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Invalid provider '{provider}'. Allowed: {sorted(list(ALLOWED_PROVIDERS))}")
        
    if model_name:
        # Sanitize model_name: alphanumeric, slash, colon, hyphen, period, underscore
        if not re.match(r'^[a-zA-Z0-9_.\-/:@]+$', model_name):
            raise HTTPException(status_code=400, detail="Invalid characters in model_name")
        
    env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
    
    try:
        set_key(env_path, "LLM_PROVIDER", provider)
        if provider == "freellmapi" and model_name:
            set_key(env_path, "FREELLMAPI_MODEL", model_name)
        elif provider == "9router" and model_name:
            set_key(env_path, "NINEROUTER_MODEL", model_name)
            
        load_dotenv(env_path, override=True)
        rag.clear_llm_cache()
        rag.ninerouter_llm, rag.freellm_llm, rag.gemini_llm, rag.groq_llm = rag.create_llm_instances(force_refresh=True)
        
        return {
            "status": "success",
            "message": f"Successfully switched to {provider} ({model_name or 'default'})",
            "current_provider": provider,
            "current_model": model_name or "",
            "model_name": model_name
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
