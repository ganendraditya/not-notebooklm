"""Admin Control Dashboard Router (Port 2027 / Admin Plane).

Provides dedicated REST endpoints to inspect, test, and persist system settings
for LLMs, S3 Storage, Secret Providers, FastEmbed ONNX, and System Health.
"""

import json
import logging
import os
import shutil
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db, ChatSession, Document, ChatMessage
from services.admin_service import (
    get_system_admin_config,
    update_multiple_env_variables,
    test_llm_connection,
    test_s3_storage_connection,
)
from rag.llm_factory import clear_llm_cache

logger = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/admin", tags=["admin"])


# ---------------------------------------------------------------------------
# Request Payload Schemas (Strict Pydantic Contracts)
# ---------------------------------------------------------------------------

class GatewayProfilePayload(BaseModel):
    id: str = Field(..., description="Unique profile identifier, e.g. 'deepseek' or 'ollama'")
    name: str = Field(..., description="Human-readable profile name")
    base_url: str = Field(..., description="OpenAI-compatible base URL")
    api_key: Optional[str] = Field(None, description="Secret API key (omit to keep unchanged if masked)")


class LLMConfigRequest(BaseModel):
    base_url: str = Field(..., description="OpenAI-compatible gateway URL (default gateway)")
    api_key: Optional[str] = Field(None, description="Secret API key (omit or null to preserve existing)")
    model: str = Field(..., description="Primary heavy synthesis model name")
    fast_model: Optional[str] = Field(None, description="Fast triage model name (defaults to model)")
    fallback_model: Optional[str] = Field(None, description="Optional fallback model")
    temperature: float = Field(0.1, ge=0.0, le=2.0, description="Sampling temperature")
    profiles: Optional[List[GatewayProfilePayload]] = Field(None, description="List of registered gateway profiles")
    primary_profile_id: Optional[str] = Field("default", description="Profile ID bound to Primary tier")
    fast_profile_id: Optional[str] = Field("default", description="Profile ID bound to Fast tier")
    fallback_profile_id: Optional[str] = Field("default", description="Profile ID bound to Fallback tier")


class LLMTestRequest(BaseModel):
    base_url: str
    api_key: Optional[str] = None
    model: str
    profile_id: Optional[str] = Field(None, description="Optional profile ID to explicitly resolve stored credentials")


class StorageConfigRequest(BaseModel):
    storage_type: str = Field(..., pattern="^(local|s3)$", description="Storage backend type")
    s3_endpoint: Optional[str] = Field("", description="S3 endpoint URL")
    s3_access_key: Optional[str] = Field(None, description="S3 Access Key ID")
    s3_secret_key: Optional[str] = Field(None, description="S3 Secret Access Key")
    s3_bucket: Optional[str] = Field("not-notebooklm", description="S3 Bucket Name")
    s3_region: Optional[str] = Field("auto", description="S3 Region")


class StorageTestRequest(BaseModel):
    s3_endpoint: str
    s3_access_key: Optional[str] = None
    s3_secret_key: Optional[str] = None
    s3_bucket: str = "not-notebooklm"
    s3_region: str = "auto"


class SecretProviderConfigRequest(BaseModel):
    provider: str = Field(..., pattern="^(local|infisical|doppler)$", description="Active secret provider")
    infisical_project_id: Optional[str] = ""
    infisical_env: Optional[str] = "dev"
    doppler_project: Optional[str] = ""
    doppler_config: Optional[str] = "dev"


class EmbeddingConfigRequest(BaseModel):
    provider: str = Field(..., pattern="^(local|gemini)$", description="Embedding provider: local or gemini")
    gemini_key: Optional[str] = Field(None, description="Google Gemini API key if using gemini provider")
    gemini_model: Optional[str] = Field("models/gemini-embedding-001", description="Gemini embedding model name")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/config")
def get_admin_config():
    """Returns full system configuration with masked secrets for the Control Dashboard."""
    return get_system_admin_config()


@router.post("/config/llm")
def update_llm_config(payload: LLMConfigRequest):
    """Updates and persists LLM gateway settings, clearing cached model clients."""
    updates: Dict[str, str] = {
        "LLM_BASE_URL": payload.base_url.strip(),
        "LLM_MODEL": payload.model.strip(),
        "LLM_FAST_MODEL": (payload.fast_model.strip() if payload.fast_model else payload.model.strip()),
        "LLM_FALLBACK_MODEL": (payload.fallback_model.strip() if payload.fallback_model else ""),
        "LLM_TEMPERATURE": str(payload.temperature),
        "LLM_PRIMARY_PROFILE_ID": payload.primary_profile_id.strip() if payload.primary_profile_id else "default",
        "LLM_FAST_PROFILE_ID": payload.fast_profile_id.strip() if payload.fast_profile_id else "default",
        "LLM_FALLBACK_PROFILE_ID": payload.fallback_profile_id.strip() if payload.fallback_profile_id else "default",
    }
    if payload.api_key and payload.api_key.strip():
        updates["LLM_API_KEY"] = payload.api_key.strip()

    if payload.profiles is not None:
        from services.admin_service import get_gateway_profiles
        existing_profiles_map = {p["id"]: p for p in get_gateway_profiles()}

        sanitized_profiles: List[Dict[str, Any]] = []
        for p in payload.profiles:
            existing = existing_profiles_map.get(p.id, {})
            # If new api_key is supplied and non-empty, use it; otherwise retain existing unmasked secret
            final_key = p.api_key.strip() if (p.api_key and p.api_key.strip()) else existing.get("api_key", "")
            sanitized_profiles.append({
                "id": p.id.strip(),
                "name": p.name.strip(),
                "base_url": p.base_url.strip(),
                "api_key": final_key,
            })
        updates["LLM_PROFILES_JSON"] = json.dumps(sanitized_profiles)

        # Synchronize default/primary key if omitted in top-level payload but present in selected profile
        if not (payload.api_key and payload.api_key.strip()):
            selected_pid = payload.primary_profile_id.strip() if payload.primary_profile_id else "default"
            matched_prof = next((sp for sp in sanitized_profiles if sp["id"] == selected_pid), None)
            if matched_prof and matched_prof.get("api_key"):
                updates["LLM_API_KEY"] = matched_prof["api_key"]

    update_multiple_env_variables(updates)
    clear_llm_cache()

    return {
        "status": "success",
        "message": "LLM configuration saved and cached clients cleared.",
        "config": get_system_admin_config()["llm"],
    }


@router.post("/test/llm")
async def test_llm_endpoint(payload: LLMTestRequest):
    """Executes a live test call against the configured LLM endpoint."""
    target_base = payload.base_url.strip()

    from services.admin_service import get_gateway_profiles
    profiles = get_gateway_profiles()
    known_base_urls = {
        (os.getenv("LLM_BASE_URL", "").strip() or os.getenv("NINEROUTER_BASE_URL", "").strip() or "http://localhost:20128/v1")
    }
    for p in profiles:
        if p.get("base_url"):
            known_base_urls.add(p["base_url"].strip())

    if payload.api_key and payload.api_key.strip():
        key = payload.api_key.strip()
    elif payload.profile_id:
        # Explicit profile ID match takes strict precedence over arbitrary URL matching
        matching = next((p for p in profiles if p.get("id") == payload.profile_id), None)
        key = matching.get("api_key", "").strip() if matching else ""
        if not key:
            key = os.getenv("LLM_API_KEY", "").strip() or os.getenv("NINEROUTER_API_KEY", "").strip()
    elif target_base in known_base_urls:
        # Fall back to URL matching when profile_id is not supplied
        matching = next((p for p in profiles if p.get("base_url", "").strip() == target_base and p.get("api_key")), None)
        key = matching.get("api_key", "").strip() if matching else (os.getenv("LLM_API_KEY", "").strip() or os.getenv("NINEROUTER_API_KEY", "").strip())
    else:
        return {
            "success": False,
            "message": "Explicit API key is required when testing a custom/external gateway URL to prevent credential exfiltration.",
            "latency_ms": 0.0,
        }

    if not key:
        return {
            "success": False,
            "message": "No API key provided or currently configured in environment.",
            "latency_ms": 0.0,
        }

    success, message, latency_ms = await test_llm_connection(
        base_url=target_base,
        api_key=key,
        model=payload.model.strip(),
    )
    return {
        "success": success,
        "message": message,
        "latency_ms": latency_ms,
    }


@router.post("/config/storage")
def update_storage_config(payload: StorageConfigRequest):
    """Updates and persists object storage configuration (Local Disk vs S3/R2/MinIO)."""
    updates: Dict[str, str] = {
        "STORAGE_TYPE": payload.storage_type.lower(),
    }
    if payload.storage_type.lower() == "s3":
        if payload.s3_endpoint:
            updates["S3_ENDPOINT_URL"] = payload.s3_endpoint.strip()
        if payload.s3_bucket:
            updates["S3_BUCKET_NAME"] = payload.s3_bucket.strip()
        if payload.s3_region:
            updates["S3_REGION"] = payload.s3_region.strip()
        if payload.s3_access_key and payload.s3_access_key.strip():
            updates["S3_ACCESS_KEY_ID"] = payload.s3_access_key.strip()
        if payload.s3_secret_key and payload.s3_secret_key.strip():
            updates["S3_SECRET_ACCESS_KEY"] = payload.s3_secret_key.strip()

    update_multiple_env_variables(updates)

    # Force storage adapter client refresh via public interface
    try:
        from services.storage_adapter import reset_s3_client
        reset_s3_client()
    except Exception as e:
        logger.warning(f"[Admin] Failed to reset S3 client adapter: {e}")

    return {
        "status": "success",
        "message": "Storage configuration updated successfully.",
        "config": get_system_admin_config()["storage"],
    }


@router.post("/test/storage")
def test_storage_endpoint(payload: StorageTestRequest):
    """Tests authentication and accessibility of an S3-compatible bucket."""
    target_endpoint = payload.s3_endpoint.strip()
    configured_endpoint = os.getenv("S3_ENDPOINT_URL", "").strip()

    if payload.s3_access_key and payload.s3_access_key.strip():
        acc_key = payload.s3_access_key.strip()
    elif target_endpoint == configured_endpoint:
        acc_key = os.getenv("S3_ACCESS_KEY_ID", "").strip()
    else:
        acc_key = ""

    if payload.s3_secret_key and payload.s3_secret_key.strip():
        sec_key = payload.s3_secret_key.strip()
    elif target_endpoint == configured_endpoint:
        sec_key = os.getenv("S3_SECRET_ACCESS_KEY", "").strip()
    else:
        sec_key = ""

    if not acc_key or not sec_key:
        return {
            "success": False,
            "message": "S3 Access Key and Secret Key are required when testing a custom endpoint.",
        }

    success, message = test_s3_storage_connection(
        endpoint=target_endpoint,
        access_key=acc_key,
        secret_key=sec_key,
        bucket=payload.s3_bucket.strip(),
        region=payload.s3_region.strip() or "auto",
    )
    return {
        "success": success,
        "message": message,
    }


@router.post("/config/secrets")
def update_secret_provider_config(payload: SecretProviderConfigRequest):
    """Configures active Secret Manager provider (Local .env, Infisical, or Doppler)."""
    updates: Dict[str, str] = {}
    if payload.provider == "infisical":
        if payload.infisical_project_id:
            updates["INFISICAL_PROJECT_ID"] = payload.infisical_project_id.strip()
        if payload.infisical_env:
            updates["INFISICAL_ENV"] = payload.infisical_env.strip()
    elif payload.provider == "doppler":
        if payload.doppler_project:
            updates["DOPPLER_PROJECT"] = payload.doppler_project.strip()
        if payload.doppler_config:
            updates["DOPPLER_CONFIG"] = payload.doppler_config.strip()

    if updates:
        update_multiple_env_variables(updates)

    return {
        "status": "success",
        "message": f"Secret management configured for provider: {payload.provider}",
        "config": get_system_admin_config()["secrets"],
    }


@router.post("/config/embeddings")
def update_embedding_config(payload: EmbeddingConfigRequest):
    """Switches embedding engine between FastEmbed ONNX local and Google Gemini cloud."""
    updates: Dict[str, str] = {
        "EMBEDDING_PROVIDER": payload.provider.lower(),
    }
    if payload.provider == "gemini":
        if payload.gemini_key and payload.gemini_key.strip():
            updates["GEMINI_API_KEY"] = payload.gemini_key.strip()
        if payload.gemini_model:
            updates["GEMINI_EMBEDDING_MODEL"] = payload.gemini_model.strip()

    update_multiple_env_variables(updates)

    # Re-initialize vector store embedding reference if needed
    try:
        import rag
        from rag.vector_store import init_embedding_and_vector_store
        embed_model, vstore = init_embedding_and_vector_store()
        rag.embed_model = embed_model
        rag.vector_store = vstore
    except Exception as e:
        logger.warning(f"[Admin] Vector store re-init on embedding switch noted: {e}")

    return {
        "status": "success",
        "message": f"Embedding provider switched to: {payload.provider}",
        "config": get_system_admin_config()["embedding"],
    }


@router.get("/system/health")
def get_system_health(db: Session = Depends(get_db)):
    """Provides authoritative system metrics: SQLite records, Qdrant vectors, and disk statistics."""
    # 1. Database counts
    total_chats = db.query(ChatSession).count()
    total_docs = db.query(Document).count()
    total_messages = db.query(ChatMessage).count()

    # 2. Qdrant status
    qdrant_status = {"status": "unknown", "collections": []}
    try:
        from rag.vector_store import qdrant_client
        cols = qdrant_client.get_collections().collections
        col_list = []
        for c in cols:
            info = qdrant_client.get_collection(c.name)
            col_list.append({
                "name": c.name,
                "points_count": getattr(info, "points_count", 0),
                "status": getattr(info, "status", "ready"),
            })
        qdrant_status = {
            "status": "healthy",
            "collections": col_list,
        }
    except Exception as e:
        qdrant_status = {
            "status": "error",
            "error": str(e),
            "collections": [],
        }

    # 3. Disk space
    disk_info = {"total_gb": 0.0, "free_gb": 0.0, "used_gb": 0.0}
    try:
        total, used, free = shutil.disk_usage(".")
        disk_info = {
            "total_gb": round(total / (1024**3), 2),
            "used_gb": round(used / (1024**3), 2),
            "free_gb": round(free / (1024**3), 2),
        }
    except Exception:
        pass

    return {
        "status": "ok",
        "database": {
            "engine": "SQLite WAL",
            "chat_sessions": total_chats,
            "documents": total_docs,
            "messages": total_messages,
        },
        "vector_store": qdrant_status,
        "disk": disk_info,
    }
