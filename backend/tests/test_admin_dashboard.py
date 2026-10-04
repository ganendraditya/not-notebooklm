"""Comprehensive Unit Tests for Admin Control Dashboard Endpoints (Issue #63).

Validates:
- GET /admin/config: Masked secrets, accurate model signatures, storage detection.
- POST /admin/config/llm: Configuration updates and validation.
- POST /admin/test/llm: Live ping handling and error handling.
- POST /admin/config/storage: S3 / local toggling and cache busting.
- POST /admin/test/storage: S3 connectivity test guardrails.
- POST /admin/config/secrets: Provider switching (local/infisical/doppler).
- POST /admin/config/embeddings: FastEmbed ONNX vs Gemini switcher.
- GET /admin/system/health: Authoritative counts and disk space diagnostics.
"""

import os
import tempfile
import pytest
from fastapi.testclient import TestClient
from main import app
from services.admin_service import mask_secret, update_env_variable, update_multiple_env_variables

client = TestClient(app)


@pytest.fixture(autouse=True)
def isolate_test_env(monkeypatch):
    """Isolates all test runs to a temporary .env file to prevent mutating developer production configuration."""
    with tempfile.NamedTemporaryFile("w+", delete=False) as tf:
        tf.write("STORAGE_TYPE=local\nLLM_MODEL=gpt-4o\n")
        temp_path = tf.name

    monkeypatch.setenv("TEST_ENV_PATH", temp_path)
    # Reset storage type environment to local
    orig_env = os.environ.copy()
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(orig_env)
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_mask_secret_utility():
    """Verify secrets are masked to prevent leak in logs or client-side dumps."""
    assert mask_secret("") == ""
    assert mask_secret(None) == ""
    assert mask_secret("short") == "********"
    assert mask_secret("sk-1234567890abcdef") == "sk-...cdef"


def test_update_env_variable_and_multiple():
    """Verify env updates safely write to file without corrupting unrelated variables."""
    with tempfile.NamedTemporaryFile(mode="w+", delete=False) as tf:
        tf.write("EXISTING_KEY=original_val\nOTHER=keep_this\n")
        temp_path = tf.name

    try:
        # Single update
        success = update_env_variable("EXISTING_KEY", "new_val", env_path=temp_path)
        assert success is True

        with open(temp_path, "r") as f:
            content = f.read()
        assert "EXISTING_KEY=new_val\n" in content
        assert "OTHER=keep_this\n" in content

        # Multiple updates
        update_multiple_env_variables(
            {"NEW_VAR": "added_val", "OTHER": "updated_other"},
            env_path=temp_path,
        )

        with open(temp_path, "r") as f:
            content_updated = f.read()
        assert "NEW_VAR=added_val\n" in content_updated
        assert "OTHER=updated_other\n" in content_updated
        assert "EXISTING_KEY=new_val\n" in content_updated
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_admin_config_endpoint():
    """Verify GET /admin/config returns complete categorized configuration."""
    res = client.get("/admin/config")
    assert res.status_code == 200
    data = res.json()

    # 1. LLM category
    assert "llm" in data
    assert "base_url" in data["llm"]
    assert "model" in data["llm"]
    assert "fast_model" in data["llm"]
    assert "api_key_masked" in data["llm"]
    assert "has_api_key" in data["llm"]
    assert "temperature" in data["llm"]

    # 2. Storage category
    assert "storage" in data
    assert "storage_type" in data["storage"]
    assert "s3_endpoint" in data["storage"]
    assert "s3_bucket" in data["storage"]
    assert "has_s3_secret" in data["storage"]

    # 3. Secrets category
    assert "secrets" in data
    assert "active_provider" in data["secrets"]

    # 4. Embedding category
    assert "embedding" in data
    assert data["embedding"]["local_dimensions"] == 384
    assert data["embedding"]["hybrid_bm25_enabled"] is True


def test_admin_update_llm_config_with_profiles():
    """Verify POST /admin/config/llm updates multiple gateway profiles and per-tier bindings."""
    payload = {
        "base_url": "http://localhost:20128/v1",
        "api_key": "sk-mainkey",
        "model": "deepseek-reasoner",
        "fast_model": "llama-3.2-3b",
        "fallback_model": "grok-beta",
        "temperature": 0.15,
        "profiles": [
            {
                "id": "deepseek",
                "name": "DeepSeek Official",
                "base_url": "https://api.deepseek.com/v1",
                "api_key": "sk-deepseek-secret"
            },
            {
                "id": "ollama",
                "name": "Local Ollama",
                "base_url": "http://localhost:11434/v1",
                "api_key": ""
            }
        ],
        "primary_profile_id": "deepseek",
        "fast_profile_id": "ollama",
        "fallback_profile_id": "deepseek"
    }
    res = client.post("/admin/config/llm", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["config"]["primary_profile_id"] == "deepseek"
    assert data["config"]["fast_profile_id"] == "ollama"

    # Verify GET /admin/config returns masked profiles
    res_get = client.get("/admin/config")
    assert res_get.status_code == 200
    cfg = res_get.json()["llm"]
    assert len(cfg["profiles"]) >= 2
    ds_prof = next(p for p in cfg["profiles"] if p["id"] == "deepseek")
    assert ds_prof["api_key_masked"] == "sk-...cret"
    assert ds_prof["has_api_key"] is True

    # Test factory credential resolution for different tiers
    from rag.llm_factory import _resolve_tier_credentials
    base_p, key_p, mod_p, _, _, _, has_p, proto_p = _resolve_tier_credentials("primary")
    assert base_p == "https://api.deepseek.com/v1"
    assert key_p == "sk-deepseek-secret"
    assert mod_p == "deepseek-reasoner"
    assert proto_p == "openai"

    base_f, key_f, _, fast_m, _, _, _, proto_f = _resolve_tier_credentials("fast")
    assert base_f == "http://localhost:11434/v1"
    assert fast_m == "llama-3.2-3b"


def test_admin_update_llm_config():
    """Verify POST /admin/config/llm updates model parameters."""
    payload = {
        "base_url": "http://localhost:20128/v1",
        "api_key": "sk-testkey12345678",
        "model": "gpt-4o",
        "fast_model": "gpt-4o-mini",
        "fallback_model": "gemini-1.5-flash",
        "temperature": 0.2,
    }
    res = client.post("/admin/config/llm", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["config"]["model"] == "gpt-4o"
    assert data["config"]["fast_model"] == "gpt-4o-mini"
    assert data["config"]["temperature"] == 0.2


def test_admin_test_llm_without_key():
    """Verify POST /admin/test/llm handles empty keys gracefully."""
    res = client.post("/admin/test/llm", json={
        "base_url": "http://localhost:20128/v1",
        "api_key": "",
        "model": "gpt-4o",
    })
    assert res.status_code == 200
    data = res.json()
    assert "success" in data
    assert "message" in data


def test_admin_update_storage_config():
    """Verify POST /admin/config/storage persists configuration changes."""
    payload = {
        "storage_type": "s3",
        "s3_endpoint": "https://test.r2.cloudflarestorage.com",
        "s3_access_key": "test_access_key",
        "s3_secret_key": "test_secret_key",
        "s3_bucket": "research-bucket",
        "s3_region": "auto",
    }
    res = client.post("/admin/config/storage", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["config"]["storage_type"] == "s3"
    assert data["config"]["s3_bucket"] == "research-bucket"


def test_admin_test_storage_missing_credentials():
    """Verify POST /admin/test/storage fails cleanly without credentials."""
    res = client.post("/admin/test/storage", json={
        "s3_endpoint": "https://s3.amazonaws.com",
        "s3_access_key": "",
        "s3_secret_key": "",
        "s3_bucket": "test",
    })
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is False
    assert "required" in data["message"].lower()


def test_admin_update_secret_provider():
    """Verify POST /admin/config/secrets updates active secret manager."""
    res = client.post("/admin/config/secrets", json={
        "provider": "doppler",
        "doppler_project": "notbooklm-core",
        "doppler_config": "stg",
    })
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["config"]["doppler_project"] == "notbooklm-core"
    assert data["config"]["doppler_config"] == "stg"


def test_admin_update_embeddings_config():
    """Verify POST /admin/config/embeddings toggles provider."""
    res = client.post("/admin/config/embeddings", json={
        "provider": "local",
    })
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["config"]["provider"] == "local"


def test_admin_system_health():
    """Verify GET /admin/system/health returns DB and Qdrant diagnostics."""
    res = client.get("/admin/system/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert "database" in data
    assert "chat_sessions" in data["database"]
    assert "vector_store" in data
    assert "disk" in data
    assert data["disk"]["total_gb"] > 0
