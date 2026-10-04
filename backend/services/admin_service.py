"""Admin Control Plane and Configuration Service for NotbookLM.

Manages BYOK LLM credentials, S3 storage providers, secret manager adapters,
and vector database health diagnostics without modifying repository source files.
"""

import os
import logging
from typing import Dict, Any, Optional, Tuple
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

    return {
        "llm": {
            "base_url": base_url,
            "api_key_masked": mask_secret(api_key),
            "has_api_key": bool(api_key and not api_key.startswith("your_") and api_key != "dummy_key"),
            "model": main_model,
            "fast_model": fast_model,
            "fallback_model": fallback_model or None,
            "temperature": temp,
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
            "local_model": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 (FastEmbed ONNX, 384-dim)",
            "local_dimensions": 384,
            "hybrid_bm25_enabled": True,
        },
    }


async def test_llm_connection(base_url: str, api_key: str, model: str) -> Tuple[bool, str, float]:
    """Tests connectivity to the specified OpenAI-compatible LLM gateway with latency measurement."""
    import time
    from llama_index.llms.openai_like import OpenAILike
    from llama_index.core.llms import ChatMessage as LlamaChatMessage, MessageRole

    start_time = time.perf_counter()
    try:
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

        # Check bucket accessibility
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
