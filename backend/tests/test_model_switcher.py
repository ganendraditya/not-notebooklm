import pytest
from fastapi.testclient import TestClient
from main import app
from database import SessionLocal, ChatSession, commit_with_retry
from rag.llm_factory import get_candidate_llm_chain, clear_llm_cache

client = TestClient(app)

def test_chat_session_model_and_profile_binding():
    """Verify ChatSession model and profile_id can be set on creation and updated via PATCH."""
    # 1. Create with model and profile
    res = client.post("/chats", json={
        "title": "Model Switcher Test",
        "model": "deepseek-reasoner",
        "profile_id": "deepseek"
    })
    assert res.status_code == 200
    data = res.json()
    chat_id = data["id"]
    assert data.get("model") == "deepseek-reasoner"
    assert data.get("profile_id") == "deepseek"

    # 2. Get chat details verifies model and profile_id are populated
    res_get = client.get(f"/chats/{chat_id}")
    assert res_get.status_code == 200
    data_get = res_get.json()
    assert data_get.get("model") == "deepseek-reasoner"
    assert data_get.get("profile_id") == "deepseek"

    # 3. Update model to another provider
    res_patch = client.patch(f"/chats/{chat_id}", json={
        "model": "claude-3-7-sonnet-20250219",
        "profile_id": "anthropic"
    })
    assert res_patch.status_code == 200
    assert res_patch.json().get("model") == "claude-3-7-sonnet-20250219"
    assert res_patch.json().get("profile_id") == "anthropic"

    # 4. Clear model override back to default
    res_clear = client.patch(f"/chats/{chat_id}", json={
        "model": "",
        "profile_id": ""
    })
    assert res_clear.status_code == 200
    assert res_clear.json().get("model") is None
    assert res_clear.json().get("profile_id") is None

    # Clean up
    client.delete(f"/chats/{chat_id}")

def test_llm_models_workspace_models_endpoint():
    """Verify /llm/models returns workspace_models list with enabled models."""
    res = client.get("/llm/models")
    assert res.status_code == 200
    data = res.json()
    assert data.get("status") == "success"
    assert "workspace_models" in data
    workspace_models = data["workspace_models"]
    assert isinstance(workspace_models, list)
    assert len(workspace_models) > 0
    # First model has id, name, profile_id, protocol
    first = workspace_models[0]
    assert "id" in first
    assert "name" in first
    assert "profile_id" in first
    assert "protocol" in first

def test_get_candidate_llm_chain_with_model_override():
    """Verify get_candidate_llm_chain puts model_override as the first synthesizer."""
    clear_llm_cache()
    # Default without override
    chain_default = get_candidate_llm_chain()
    assert len(chain_default) > 0

    # With override
    chain_override = get_candidate_llm_chain(model_override="test-custom-model-id", profile_id_override="default")
    assert len(chain_override) > 0
    first_llm, first_label = chain_override[0]
    assert "Session Model (test-custom-model-id)" in first_label
    assert getattr(first_llm, "model", None) == "test-custom-model-id"
    clear_llm_cache()
