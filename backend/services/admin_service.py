"""Admin Control Plane and Configuration Service for NotbookLM.

Manages BYOK LLM credentials, S3 storage providers, secret manager adapters,
and vector database health diagnostics without modifying repository source files.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("uvicorn.error")

CONFIG_FILE_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", ".env")
)


def mask_secret(secret: Optional[str]) -> str:
    """Masks secret values, showing only first 3 and last 4 characters for security."""
    if not secret:
        return ""
    clean = str(secret).strip()
    if len(clean) <= 8:
        return "********"
    return f"{clean[:3]}...{clean[-4:]}"


def _sanitize_env_value(val: Any) -> str:
    """Sanitizes environment variable value to prevent injection via carriage returns or newlines."""
    raw = str(val) if val is not None else ""
    # Strip dangerous newlines and control characters that break .env format
    cleaned = raw.replace("\r", "").replace("\n", " ").strip()
    return cleaned


def _normalize_profile_models(profile: Dict[str, Any], default_model: str) -> List[Dict[str, Any]]:
    """Ensures each profile possesses a valid list of models with enabled toggles."""
    raw_models = profile.get("models")
    if isinstance(raw_models, list):
        cleaned = []
        for m in raw_models:
            if isinstance(m, dict) and m.get("id"):
                cleaned.append({
                    "id": str(m["id"]).strip(),
                    "name": str(m.get("name") or m["id"]).strip(),
                    "enabled": bool(m.get("enabled", True)),
                })
            elif isinstance(m, str) and m.strip():
                cleaned.append({
                    "id": m.strip(),
                    "name": m.strip(),
                    "enabled": True,
                })
        return cleaned

    # Fallback default models based on profile properties
    pid = profile.get("id", "")
    proto = profile.get("protocol", "openai")
    base_url = profile.get("base_url", "").lower()

    if pid == "default" or "20128" in base_url or "9router" in base_url:
        return [{"id": default_model, "name": default_model, "enabled": True}]
    elif proto == "anthropic" or "anthropic.com" in base_url:
        return [
            {"id": "claude-3-7-sonnet-20250219", "name": "Claude 3.7 Sonnet", "enabled": True},
            {"id": "claude-3-5-haiku-20241022", "name": "Claude 3.5 Haiku", "enabled": True},
        ]
    elif "deepseek.com" in base_url:
        return [
            {"id": "deepseek-chat", "name": "DeepSeek V3", "enabled": True},
            {"id": "deepseek-reasoner", "name": "DeepSeek R1", "enabled": True},
        ]
    elif "api.x.ai" in base_url:
        return [{"id": "grok-2-latest", "name": "Grok 2", "enabled": True}]
    elif "groq.com" in base_url:
        return [{"id": "llama-3.3-70b-versatile", "name": "LLaMA 3.3 70B", "enabled": True}]
    elif "api.openai.com" in base_url:
        return [
            {"id": "gpt-4o", "name": "GPT-4o", "enabled": True},
            {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "enabled": True},
        ]
    elif "11434" in base_url:
        return [{"id": "llama3.2", "name": "Llama 3.2", "enabled": True}]
    else:
        return [{"id": default_model, "name": default_model, "enabled": True}]


def get_gateway_profiles() -> List[Dict[str, Any]]:
    """
    Parses and returns registered OpenAI-compatible gateway profiles.
    Falls back gracefully to synthesizing a 'default' profile from LLM_BASE_URL and LLM_API_KEY.
    """
    raw_json = os.getenv("LLM_PROFILES_JSON", "").strip()
    profiles: List[Dict[str, Any]] = []
    if raw_json:
        try:
            parsed = json.loads(raw_json)
            if isinstance(parsed, list):
                profiles = parsed
        except Exception as e:
            logger.warning(f"[AdminService] Failed to parse LLM_PROFILES_JSON: {e}")

    # Ensure there is always at least one default profile matching base credentials
    default_base_url = (
        os.getenv("LLM_BASE_URL", "").strip()
        or os.getenv("NINEROUTER_BASE_URL", "").strip()
        or "http://localhost:20128/v1"
    )
    default_api_key = os.getenv("LLM_API_KEY", "").strip() or os.getenv("NINEROUTER_API_KEY", "").strip()
    default_model = os.getenv("LLM_MODEL", "gpt-4o").strip() or "gpt-4o"

    has_default = any(p.get("id") == "default" for p in profiles)
    if not profiles or not has_default:
        profiles.insert(0, {
            "id": "default",
            "name": "Default Gateway",
            "base_url": default_base_url,
            "api_key": default_api_key,
        })

    # Ensure each profile has normalized models list
    for p in profiles:
        p["models"] = _normalize_profile_models(p, default_model=default_model)

    return profiles


def get_config_file_path() -> str:
    """Returns active config file path, prioritizing TEST_ENV_PATH if set during test runs."""
    return os.getenv("TEST_ENV_PATH", "").strip() or CONFIG_FILE_PATH


def update_env_variable(key: str, value: str, env_path: Optional[str] = None) -> bool:
    """Safely updates or appends a key-value pair in the local .env file and os.environ."""
    return update_multiple_env_variables({key: value}, env_path=env_path)


def update_multiple_env_variables(updates: Dict[str, str], env_path: Optional[str] = None) -> bool:
    """Updates multiple environment variables in a single atomic file write with sanitization."""
    target_path = env_path or get_config_file_path()
    sanitized_updates = {
        _sanitize_env_value(k): _sanitize_env_value(v)
        for k, v in updates.items()
        if _sanitize_env_value(k)
    }

    # Update in-memory os.environ
    for k, v in sanitized_updates.items():
        os.environ[k] = v

    lines = []
    if os.path.exists(target_path):
        with open(target_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

    updated_keys = set()
    new_lines = []
    for line in lines:
        stripped = line.strip()
        matched_key = None
        for k in sanitized_updates:
            if stripped.startswith(f"{k}=") or stripped.startswith(f"export {k}="):
                matched_key = k
                break

        if matched_key:
            prefix = "export " if stripped.startswith("export ") else ""
            new_lines.append(f"{prefix}{matched_key}={sanitized_updates[matched_key]}\n")
            updated_keys.add(matched_key)
        else:
            new_lines.append(line)

    # Append any remaining new keys
    for k, v in sanitized_updates.items():
        if k not in updated_keys:
            if new_lines and not new_lines[-1].endswith("\n"):
                new_lines.append("\n")
            new_lines.append(f"{k}={v}\n")

    # Atomic write via temp file in same directory
    dir_name = os.path.dirname(target_path) or "."
    import tempfile
    with tempfile.NamedTemporaryFile("w", dir=dir_name, delete=False, encoding="utf-8") as tf:
        tf.writelines(new_lines)
        temp_name = tf.name

    os.replace(temp_name, target_path)
    return True


def get_system_admin_config() -> Dict[str, Any]:
    """Retrieves current admin system configuration with sensitive keys masked."""
    # 1. LLM Settings
    api_key = os.getenv("LLM_API_KEY", "").strip() or os.getenv("NINEROUTER_API_KEY", "").strip()
    base_url = (
        os.getenv("LLM_BASE_URL", "").strip()
        or os.getenv("NINEROUTER_BASE_URL", "").strip()
        or "http://localhost:20128/v1"
    )
    main_model = (
        os.getenv("LLM_MODEL", "").strip()
        or os.getenv("NINEROUTER_MODEL", "").strip()
        or "gpt-4o"
    )
    fast_model = (
        os.getenv("LLM_FAST_MODEL", "").strip()
        or os.getenv("NINEROUTER_FAST_MODEL", "").strip()
        or main_model
    )
    fallback_model = (
        os.getenv("LLM_FALLBACK_MODEL", "").strip()
        or os.getenv("NINEROUTER_FALLBACK_MODEL", "").strip()
    )
    try:
        temp = float(os.getenv("LLM_TEMPERATURE", "0.1").strip())
    except (ValueError, TypeError):
        temp = 0.1

    # 2. Storage Settings
    storage_type = os.getenv("STORAGE_TYPE", "local").strip().lower()
    s3_endpoint = os.getenv("S3_ENDPOINT_URL", "").strip()
    s3_access_key = os.getenv("S3_ACCESS_KEY_ID", "").strip()
    s3_secret_key = os.getenv("S3_SECRET_ACCESS_KEY", "").strip()
    s3_bucket = os.getenv("S3_BUCKET_NAME", "not-notebooklm").strip()
    s3_region = os.getenv("S3_REGION", "auto").strip()

    # 3. Secret Manager Provider
    secret_provider = "local"
    if os.getenv("INFISICAL_TOKEN") or os.getenv("INFISICAL_ENV") or os.getenv("INFISICAL_PROJECT_ID"):
        secret_provider = "infisical"
    elif os.getenv("DOPPLER_ENVIRONMENT") or os.getenv("DOPPLER_CONFIG") or os.getenv("DOPPLER_TOKEN"):
        secret_provider = "doppler"

    # 4. Embedding Settings
    embedding_provider = os.getenv("EMBEDDING_PROVIDER", "local").strip().lower()
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip() or os.getenv("GOOGLE_API_KEY", "").strip()
    gemini_model = os.getenv("GEMINI_EMBEDDING_MODEL", "models/gemini-embedding-001").strip()
    custom_embed_url = os.getenv("EMBEDDING_BASE_URL", "http://localhost:11434/v1").strip()
    custom_embed_key = os.getenv("EMBEDDING_API_KEY", "").strip()
    custom_embed_model = os.getenv("EMBEDDING_MODEL_NAME", "nomic-embed-text").strip()
    local_embed_model = os.getenv("LOCAL_EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2").strip()
    custom_local_path = os.getenv("CUSTOM_EMBEDDING_PATH", "").strip()

    # 5. Reranker Settings
    reranker_model = os.getenv("RERANKER_MODEL", "ms-marco-TinyBERT-L-2-v2").strip()
    try:
        reranker_top_n = int(os.getenv("RERANKER_TOP_N", "12").strip())
    except (ValueError, TypeError):
        reranker_top_n = 12

    # Profiles & Tier Bindings
    raw_profiles = get_gateway_profiles()
    masked_profiles = [
        {
            "id": p.get("id", "default"),
            "name": p.get("name", "Gateway"),
            "base_url": p.get("base_url", ""),
            "api_key_masked": mask_secret(p.get("api_key", "")),
            "has_api_key": bool(p.get("api_key") and not str(p.get("api_key")).startswith("your_")),
            "protocol": p.get("protocol", "openai"),
            "models": p.get("models", []),
        }
        for p in raw_profiles
    ]
    primary_pid = os.getenv("LLM_PRIMARY_PROFILE_ID", "default").strip()
    fast_pid = os.getenv("LLM_FAST_PROFILE_ID", primary_pid).strip()
    fallback_pid = os.getenv("LLM_FALLBACK_PROFILE_ID", primary_pid).strip()

    return {
        "llm": {
            "base_url": base_url,
            "api_key_masked": mask_secret(api_key),
            "has_api_key": bool(api_key and not api_key.startswith("your_") and api_key != "dummy_key"),
            "model": main_model,
            "fast_model": fast_model,
            "fallback_model": fallback_model or None,
            "temperature": temp,
            "profiles": masked_profiles,
            "primary_profile_id": primary_pid,
            "fast_profile_id": fast_pid,
            "fallback_profile_id": fallback_pid,
        },
        "storage": {
            "storage_type": storage_type,
            "s3_endpoint": s3_endpoint,
            "s3_bucket": s3_bucket,
            "s3_region": s3_region,
            "s3_access_key_masked": mask_secret(s3_access_key),
            "has_s3_secret": bool(s3_secret_key and not s3_secret_key.startswith("your_")),
            "is_configured": storage_type == "s3" and bool(s3_endpoint and s3_access_key and s3_secret_key and s3_bucket),
        },
        "secrets": {
            "active_provider": secret_provider,
            "infisical_project_id": os.getenv("INFISICAL_PROJECT_ID", ""),
            "infisical_env": os.getenv("INFISICAL_ENV", "dev"),
            "doppler_project": os.getenv("DOPPLER_PROJECT", ""),
            "doppler_config": os.getenv("DOPPLER_CONFIG", "dev"),
        },
        "embedding": {
            "provider": embedding_provider,
            "gemini_model": gemini_model,
            "gemini_key_masked": mask_secret(gemini_key),
            "has_gemini_key": bool(gemini_key and not gemini_key.startswith("your_")),
            "local_model": local_embed_model,
            "local_dimensions": 1024 if "e5" in local_embed_model.lower() else 384,
            "custom_base_url": custom_embed_url,
            "custom_model_name": custom_embed_model,
            "custom_key_masked": mask_secret(custom_embed_key),
            "has_custom_key": bool(custom_embed_key and not custom_embed_key.startswith("your_")),
            "custom_local_path": custom_local_path,
            "hybrid_bm25_enabled": True,
        },
        "reranker": {
            "model": reranker_model,
            "top_n": reranker_top_n,
        },
    }


async def test_llm_connection(
    base_url: str,
    api_key: str,
    model: str,
    protocol: str = "openai",
) -> Tuple[bool, str, float]:
    """Tests connectivity to the specified LLM gateway (OpenAI-compatible or native Anthropic) with latency measurement."""
    import time
    from llama_index.core.llms import ChatMessage as LlamaChatMessage, MessageRole

    start_time = time.perf_counter()
    try:
        if protocol == "anthropic":
            from llama_index.llms.anthropic import Anthropic as LlamaAnthropic
            test_model = (
                model
                if (model and not model.startswith("gpt-") and "claude" in model.lower())
                else "claude-3-5-haiku-20241022"
            )
            test_client = LlamaAnthropic(
                model=test_model,
                api_key=api_key,
                base_url=base_url if base_url and not base_url.startswith("https://api.anthropic.com") else None,
                max_tokens=10,
                timeout=15.0,
            )
        else:
            from llama_index.llms.openai_like import OpenAILike
            test_client = OpenAILike(
                api_base=base_url,
                api_key=api_key,
                model=model,
                is_chat_model=True,
                max_tokens=10,
                timeout=15.0,
            )
        test_msg = [LlamaChatMessage(role=MessageRole.USER, content="Ping")]
        resp = await test_client.achat(test_msg)
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        reply = str(getattr(resp, "message", resp)).strip()
        return True, f"Connection successful! Latency: {latency_ms}ms. Response: {reply[:30]}", latency_ms
    except Exception as e:
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return False, f"LLM test failed: {str(e)}", latency_ms


def test_s3_storage_connection(
    endpoint: str,
    access_key: str,
    secret_key: str,
    bucket: str,
    region: str = "auto"
) -> Tuple[bool, str]:
    """Tests authentication and bucket operations against an S3/R2/MinIO endpoint."""
    try:
        import boto3
        from botocore.config import Config
        from botocore.exceptions import ClientError

        s3 = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region or "auto",
            config=Config(signature_version="s3v4", connect_timeout=5, retries={"max_attempts": 1}),
        )

        try:
            s3.head_bucket(Bucket=bucket)
            return True, f"Successfully connected to bucket '{bucket}' on {endpoint}"
        except ClientError as e:
            err_code = e.response.get("Error", {}).get("Code", "")
            if err_code in ("404", "NoSuchBucket"):
                return False, f"Bucket '{bucket}' does not exist on {endpoint}."
            return False, f"Bucket head error: {e}"
    except ImportError:
        return False, "boto3 library is not installed in the environment."
    except Exception as e:
        return False, f"S3 connection failed: {str(e)}"


def test_embedding_endpoint(
    base_url: str,
    api_key: str,
    model_name: str
) -> Tuple[bool, str, int, float]:
    """
    Tests connectivity to an OpenAI-compatible /v1/embeddings endpoint.
    Performs live dimension sniffing and measures latency.
    """
    import time
    from rag.vector_store import OpenAICompatibleEmbedding

    start_time = time.perf_counter()
    try:
        embedder = OpenAICompatibleEmbedding(
            base_url=base_url,
            api_key=api_key,
            model_name=model_name,
            timeout=10.0,
        )
        vec = embedder._get_query_embedding("connectivity probe")
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        if not vec:
            return False, "Endpoint returned empty embedding array.", 0, latency_ms
        dim = len(vec)
        return True, f"Success! Verified {dim}-dimensional vector embeddings.", dim, latency_ms
    except Exception as e:
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return False, f"Embedding connection failed: {str(e)}", 0, latency_ms


def test_reranker_instance(
    model_name: str
) -> Tuple[bool, str, float]:
    """
    Tests live FlashRank cross-encoder ranking and measures execution time.
    """
    import time
    from flashrank import RerankRequest
    from rag.vector_store import get_flashrank_ranker

    start_time = time.perf_counter()
    try:
        ranker = get_flashrank_ranker(model_name=model_name)
        if not ranker:
            return False, f"Failed to instantiate reranker model '{model_name}'.", 0.0
        passages = [
            {"id": 0, "text": "First test passage about academic literature synthesis."},
            {"id": 1, "text": "Second test passage discussing vector database indexing."},
        ]
        res = ranker.rerank(RerankRequest(query="literature synthesis", passages=passages))
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        if res and len(res) == 2:
            return True, f"Reranker '{model_name}' operational! Ranked 2 passages in {latency_ms}ms.", latency_ms
        return False, "Reranker returned malformed rank results.", latency_ms
    except Exception as e:
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return False, f"Reranker test error: {str(e)}", latency_ms
