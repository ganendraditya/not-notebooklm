import os
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import rag
from database import get_db, ChatSession, Document, ChatMessage
from utils.file_utils import UPLOAD_DIR

router = APIRouter(tags=["settings"])

class ResetStoragePayload(BaseModel):
    confirm_text: str = ""

@router.post("/settings/storage/cleanup")
def cleanup_orphan_storage(db: Session = Depends(get_db)):
    """Scans and deletes orphan files on disk not associated with any active chat session."""
    from services.storage_service import cleanup_orphan_files_on_disk
    active_chats = set(row[0] for row in db.query(ChatSession.id).all())
    deleted_files, freed_bytes = cleanup_orphan_files_on_disk(active_chats)
    return {
        "status": "success",
        "deleted_files_count": deleted_files,
        "freed_bytes": freed_bytes
    }

@router.post("/settings/storage/reset")
def factory_reset_storage(payload: ResetStoragePayload, db: Session = Depends(get_db)):
    """Wipes all chats, documents, messages, and vector embeddings."""
    confirmation = payload.confirm_text.strip().lower()
    if confirmation != "reset-all-data":
        raise HTTPException(status_code=400, detail="Invalid confirmation phrase. Type 'reset-all-data' to proceed.")

    # 1. Clear database with clean transaction rollback safety
    try:
        db.query(ChatMessage).delete(synchronize_session=False)
        db.query(Document).delete(synchronize_session=False)
        db.query(ChatSession).delete(synchronize_session=False)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database reset failed: {e}")

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
    fallback_colls = ["not_notebooklm_e5", "not_notebooklm_bge", "not_notebooklm_gemini", "not_notebooklm"]
    try:
        remote_colls = [c.name for c in rag.qdrant_client.get_collections().collections]
        colls = list(set(remote_colls + fallback_colls))
    except Exception:
        colls = fallback_colls

    for cname in colls:
        try:
            rag.qdrant_client.delete_collection(collection_name=cname)
        except Exception:
            pass

    return {"status": "success", "message": "All application data and workspaces have been reset."}

@router.get("/llm/models")
def get_llm_models():
    """Returns active LLM configuration info dynamically, including enabled models for the workspace."""
    from rag.llm_factory import get_main_llm, get_fast_llm, get_fallback_llm
    from services.admin_service import get_gateway_profiles
    
    main_instance = get_main_llm()
    fast_instance = get_fast_llm()
    fallback_instance = get_fallback_llm()
    
    main_model = getattr(main_instance, "model", None) or os.getenv("LLM_MODEL", "gpt-4o")
    fast_model = getattr(fast_instance, "model", None) or os.getenv("LLM_FAST_MODEL", main_model)
    fallback_model = getattr(fallback_instance, "model", None) or os.getenv("LLM_FALLBACK_MODEL", "")
    primary_pid = os.getenv("LLM_PRIMARY_PROFILE_ID", "default").strip() or "default"

    # Collect enabled models across all configured gateway profiles for workspace selection
    profiles = get_gateway_profiles()
    workspace_models = []
    seen_keys = set()

    for p in profiles:
        p_id = p.get("id", "default")
        p_name = p.get("name", "Gateway")
        p_proto = p.get("protocol", "openai")
        models_list = p.get("models", [])

        if not models_list and p_id == primary_pid:
            models_list = [{"id": main_model, "name": main_model, "enabled": True}]

        for m in models_list:
            if m.get("enabled", True):
                m_id = m.get("id")
                if not m_id:
                    continue
                key = (p_id, m_id)
                if key not in seen_keys:
                    seen_keys.add(key)
                    is_def = (p_id == primary_pid and m_id == main_model)
                    workspace_models.append({
                        "id": m_id,
                        "name": m.get("name") or m_id,
                        "profile_id": p_id,
                        "profile_name": p_name,
                        "protocol": p_proto,
                        "is_default": is_def,
                    })

    if not workspace_models:
        workspace_models.append({
            "id": main_model,
            "name": main_model,
            "profile_id": primary_pid,
            "profile_name": "Default Gateway",
            "protocol": "openai",
            "is_default": True,
        })
    elif not any(m.get("is_default") for m in workspace_models):
        workspace_models[0]["is_default"] = True

    return {
        "status": "success",
        "tiered_architecture": True,
        "main_model": main_model,
        "fast_model": fast_model,
        "fallback_model": fallback_model or None,
        "primary_profile_id": primary_pid,
        "workspace_models": workspace_models,
        "description": f"Two-Tier Engine: Heavy Synthesis powered by {main_model}, Rapid Triage & Auditing powered by {fast_model}." + (f" Fallback cascade: {fallback_model}." if fallback_model else "")
    }
