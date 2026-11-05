import importlib.util
import json
import os
import sys
from pathlib import Path
from types import ModuleType

import pytest

from services import admin_service


@pytest.fixture(autouse=True)
def isolated_llm_config(monkeypatch, tmp_path):
    for key in tuple(os.environ):
        if key.startswith(("LLM_", "NINEROUTER_")):
            monkeypatch.delenv(key)
    monkeypatch.setenv("TEST_ENV_PATH", str(tmp_path / "unused.env"))


@pytest.fixture
def catalog(monkeypatch):
    database = ModuleType("database")
    database.get_db = lambda: None
    database.ChatSession = type("ChatSession", (), {})
    database.Document = type("Document", (), {})
    database.ChatMessage = type("ChatMessage", (), {})
    files = ModuleType("utils.file_utils")
    files.UPLOAD_DIR = "unused"
    monkeypatch.setitem(sys.modules, "database", database)
    monkeypatch.setitem(sys.modules, "rag", ModuleType("rag"))
    monkeypatch.setitem(sys.modules, "utils.file_utils", files)
    path = Path(__file__).resolve().parents[1] / "routers" / "settings.py"
    spec = importlib.util.spec_from_file_location("isolated_model_catalog_router", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.get_llm_models


def test_unconfigured_system_has_no_synthetic_provider_or_model(catalog):
    assert admin_service.get_gateway_profiles() == []
    config = admin_service.get_system_admin_config()["llm"]
    assert config["profiles"] == []
    assert config["base_url"] == ""
    assert config["model"] == ""
    assert catalog()["workspace_models"] == []


def test_explicit_empty_profiles_remain_empty_despite_legacy_values(monkeypatch, catalog):
    monkeypatch.setenv("LLM_PROFILES_JSON", "[]")
    monkeypatch.setenv("LLM_BASE_URL", "https://legacy.invalid/v1")
    monkeypatch.setenv("LLM_MODEL", "legacy-model")
    assert admin_service.get_gateway_profiles() == []
    assert catalog()["workspace_models"] == []
    assert admin_service.get_system_admin_config()["llm"]["model"] == "legacy-model"


@pytest.mark.parametrize("prefix", ["LLM", "NINEROUTER"])
def test_explicit_legacy_endpoint_and_model_are_adapted_without_rewriting(monkeypatch, catalog, prefix):
    monkeypatch.setenv(f"{prefix}_BASE_URL", "https://legacy.invalid/v1")
    monkeypatch.setenv(f"{prefix}_API_KEY", "fixture-key-not-real")
    monkeypatch.setenv(f"{prefix}_MODEL", "legacy-model")
    profiles = admin_service.get_gateway_profiles()
    assert len(profiles) == 1
    assert profiles[0]["id"] == "default"
    assert profiles[0]["base_url"] == "https://legacy.invalid/v1"
    assert profiles[0]["api_key"] == "fixture-key-not-real"
    assert catalog()["workspace_models"][0]["id"] == "legacy-model"


def test_endpoint_without_registered_model_has_no_builtin_model(monkeypatch, catalog):
    monkeypatch.setenv("LLM_BASE_URL", "https://api.openai.com/v1")
    assert admin_service.get_gateway_profiles()[0]["models"] == []
    assert catalog()["workspace_models"] == []


def test_legacy_endpoint_and_model_survive_a_stale_primary_profile_id(monkeypatch, catalog):
    monkeypatch.setenv("LLM_BASE_URL", "https://legacy.invalid/v1")
    monkeypatch.setenv("LLM_MODEL", "explicit-legacy-model")
    monkeypatch.setenv("LLM_PRIMARY_PROFILE_ID", "no-longer-registered")
    assert catalog()["workspace_models"][0]["id"] == "explicit-legacy-model"


@pytest.mark.parametrize("models", [[], [{"id": "hidden", "enabled": False}]])
def test_empty_or_disabled_model_lists_do_not_resurrect_defaults(monkeypatch, catalog, models):
    monkeypatch.setenv("LLM_MODEL", "old-model")
    monkeypatch.setenv("LLM_PROFILES_JSON", json.dumps([{
        "id": "default", "name": "Saved name", "base_url": "https://provider.invalid/v1", "models": models,
    }]))
    assert catalog()["workspace_models"] == []
    assert admin_service.get_gateway_profiles()[0]["models"] == admin_service._normalize_profile_models({"models": models}, "")


def test_configured_pairs_names_credentials_and_order_are_preserved(monkeypatch, catalog):
    profiles = [
        {"id": "custom-b", "name": "Existing provider B", "base_url": "https://b.invalid/v1", "api_key": "fixture-b", "models": [{"id": "shared", "name": "Existing label B", "enabled": True}]},
        {"id": "custom-a", "name": "Existing provider A", "base_url": "https://a.invalid/v1", "api_key": "fixture-a", "models": [{"id": "shared", "name": "Existing label A", "enabled": True}]},
    ]
    raw = json.dumps(profiles)
    monkeypatch.setenv("LLM_PROFILES_JSON", raw)
    monkeypatch.setenv("LLM_BASE_URL", "https://legacy.invalid/v1")
    assert admin_service.get_gateway_profiles() == profiles
    models = catalog()["workspace_models"]
    assert [(model["profile_id"], model["id"]) for model in models] == [("custom-b", "shared"), ("custom-a", "shared")]
    assert [model["name"] for model in models] == ["Existing label B", "Existing label A"]
    assert os.environ["LLM_PROFILES_JSON"] == raw
    assert all("api_key" not in model for model in models)


def test_only_explicit_primary_legacy_model_is_adapted_not_a_vendor_catalog(monkeypatch, catalog):
    monkeypatch.setenv("LLM_MODEL", "configured-main")
    monkeypatch.setenv("LLM_PRIMARY_PROFILE_ID", "primary")
    monkeypatch.setenv("LLM_PROFILES_JSON", json.dumps([
        {"id": "primary", "name": "Saved primary", "base_url": "https://api.deepseek.com/v1"},
        {"id": "other", "name": "Saved other", "base_url": "https://api.anthropic.com", "protocol": "anthropic"},
    ]))
    models = catalog()["workspace_models"]
    assert [(model["profile_id"], model["id"]) for model in models] == [("primary", "configured-main")]


@pytest.mark.parametrize("prefix", ["LLM", "NINEROUTER"])
@pytest.mark.parametrize("registered_models", [None, [], [{"id": "custom-model", "name": "Saved model", "enabled": True}]])
def test_mixed_legacy_preserves_effective_primary_without_inventing_a_profile(monkeypatch, prefix, registered_models):
    profile = {"id": "custom-profile", "name": "Saved provider", "base_url": "https://profile.invalid/v1", "api_key": "fixture-profile-key"}
    if registered_models is not None:
        profile["models"] = registered_models
    raw = json.dumps([profile])
    monkeypatch.setenv("LLM_PROFILES_JSON", raw)
    monkeypatch.setenv(f"{prefix}_BASE_URL", "https://legacy.invalid/v1")
    monkeypatch.setenv(f"{prefix}_API_KEY", "fixture-legacy-key")
    monkeypatch.setenv(f"{prefix}_MODEL", "legacy-model")

    config = admin_service.get_system_admin_config()["llm"]
    assert config["primary_profile_id"] == "default"
    assert config["fast_profile_id"] == config["fallback_profile_id"] == "default"
    assert config["base_url"] == "https://legacy.invalid/v1"
    assert config["model"] == "legacy-model"
    assert [item["id"] for item in config["profiles"]] == ["custom-profile"]
    assert config["profiles"][0]["models"] == (registered_models or [])
    assert os.environ["LLM_PROFILES_JSON"] == raw
    assert "LLM_PRIMARY_PROFILE_ID" not in os.environ

    monkeypatch.setenv("LLM_PRIMARY_PROFILE_ID", "custom-profile")
    assert admin_service.get_system_admin_config()["llm"]["primary_profile_id"] == "custom-profile"
