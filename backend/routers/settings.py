import os
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

import rag
from database import get_db, ChatSession, Document, ChatMessage
from helpers import UPLOAD_DIR, CHAT_MEDIA_DIR

router = APIRouter(tags=["settings"])

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
        for root, _, files in os.walk(UPLOAD_DIR):
            for fname in files:
                fp = os.path.join(root, fname)
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

@router.get("/settings/storage/media/{filename}")
def get_storage_media(filename: str):
    """Serve media files directly to the frontend for attachment previews."""
    fp = os.path.join(CHAT_MEDIA_DIR, os.path.basename(filename))
    if os.path.exists(fp):
        return FileResponse(fp)
    raise HTTPException(status_code=404, detail="Media not found")

@router.get("/llm/models")
def get_llm_models():
    """Returns active LLM configuration info."""
    main_model = os.getenv("NINEROUTER_MODEL", "ag/gemini-3.7-flash-high")
    fast_model = os.getenv("NINEROUTER_FAST_MODEL", "ag/gemini-2.5-flash")
    
    return {
        "status": "success",
        "tiered_architecture": True,
        "main_model": main_model,
        "fast_model": fast_model,
        "description": "Two-Tier Engine: Heavy Synthesis powered by Gemini 3.7 Flash, Rapid Triase & Auditing powered by Flash Lite."
    }
