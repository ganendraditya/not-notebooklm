import os

import pytest

from services import admin_service


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    for key in ("DOPPLER_ENVIRONMENT", "INFISICAL_INJECTED"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("TEST_ENV_PATH", str(tmp_path / "local.env"))
    monkeypatch.setenv("LLM_API_KEY", "dummy-original-key")
    monkeypatch.setenv("LLM_MODEL", "dummy-original-model")
    return tmp_path / "local.env"


@pytest.mark.parametrize(
    ("marker", "value", "provider"),
    [
        ("DOPPLER_ENVIRONMENT", "dummy-dev", "doppler"),
        ("INFISICAL_INJECTED", "1", "infisical"),
    ],
)
@pytest.mark.parametrize("existing_file", [False, True])
@pytest.mark.parametrize("explicit_path", [False, True])
def test_vault_updates_do_not_create_or_change_local_env(
    isolated_config, monkeypatch, marker, value, provider, existing_file, explicit_path,
):
    path = isolated_config.with_name("explicit.env") if explicit_path else isolated_config
    original = b"# Existing local credentials stay untouched\nLLM_API_KEY=dummy-dormant-key\n"
    if existing_file:
        path.write_bytes(original)
    monkeypatch.setenv(marker, value)

    assert admin_service.update_multiple_env_variables(
        {"LLM_API_KEY": "dummy-runtime-key", "LLM_MODEL": "dummy-runtime-model"},
        env_path=str(path) if explicit_path else None,
    ) is True

    assert os.environ["LLM_API_KEY"] == "dummy-runtime-key"
    assert os.environ["LLM_MODEL"] == "dummy-runtime-model"
    assert path.exists() == existing_file
    if existing_file:
        assert path.read_bytes() == original
    assert sorted(entry.name for entry in path.parent.iterdir()) == ([path.name] if existing_file else [])
    assert admin_service.get_configuration_persistence(str(path)) == {
        "mode": "runtime", "active_provider": provider, "has_local_env": existing_file,
    }


def test_vault_single_update_does_not_access_file_contents(isolated_config, monkeypatch):
    monkeypatch.setenv("DOPPLER_ENVIRONMENT", "dummy-dev")

    def deny_open(*args, **kwargs):
        raise AssertionError("Vault updates must not open a local configuration file")

    monkeypatch.setattr("builtins.open", deny_open)

    assert admin_service.update_env_variable("LLM_MODEL", "dummy-runtime-model") is True
    assert os.environ["LLM_MODEL"] == "dummy-runtime-model"


@pytest.mark.parametrize("existing_file", [False, True])
def test_local_updates_keep_existing_persistence_behavior(isolated_config, existing_file):
    if existing_file:
        isolated_config.write_text("OTHER=keep\nLLM_MODEL=previous\n", encoding="utf-8")

    assert admin_service.update_env_variable("LLM_MODEL", "dummy-local-model") is True

    assert os.environ["LLM_MODEL"] == "dummy-local-model"
    contents = isolated_config.read_text(encoding="utf-8")
    assert "LLM_MODEL=dummy-local-model\n" in contents
    if existing_file:
        assert "OTHER=keep\n" in contents
    assert admin_service.get_configuration_persistence() == {
        "mode": "local_env", "active_provider": "local", "has_local_env": True,
    }


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("DOPPLER_PROJECT", "dummy-project"),
        ("DOPPLER_CONFIG", "dummy-config"),
        ("DOPPLER_TOKEN", "dummy-token"),
        ("INFISICAL_PROJECT_ID", "dummy-project"),
        ("INFISICAL_ENV", "dev"),
        ("INFISICAL_TOKEN", "dummy-token"),
        ("DOPPLER_ENVIRONMENT", " "),
        ("INFISICAL_INJECTED", "0"),
    ],
)
def test_launch_settings_alone_do_not_identify_an_active_vault(isolated_config, monkeypatch, key, value):
    monkeypatch.setenv(key, value)

    config = admin_service.get_system_admin_config()

    assert config["secrets"]["active_provider"] == "local"
    assert config["persistence"]["mode"] == "local_env"


def test_doppler_marker_has_same_precedence_as_launcher(isolated_config, monkeypatch):
    monkeypatch.setenv("DOPPLER_ENVIRONMENT", "dummy-dev")
    monkeypatch.setenv("INFISICAL_INJECTED", "1")

    assert admin_service.get_runtime_secret_provider() == "doppler"


def test_local_file_diagnostic_does_not_expose_file_contents(isolated_config, monkeypatch):
    isolated_config.write_text("LLM_API_KEY=dummy-dormant-key\n", encoding="utf-8")
    monkeypatch.setenv("INFISICAL_INJECTED", "1")

    config = admin_service.get_system_admin_config()

    assert config["persistence"] == {
        "mode": "runtime", "active_provider": "infisical", "has_local_env": True,
    }
    assert "dummy-dormant-key" not in str(config)


def test_returning_to_local_mode_does_not_flush_runtime_credentials(isolated_config, monkeypatch):
    isolated_config.write_text("LLM_API_KEY=dummy-local-key\n", encoding="utf-8")
    monkeypatch.setenv("DOPPLER_ENVIRONMENT", "dummy-dev")
    admin_service.update_env_variable("LLM_API_KEY", "dummy-runtime-key")
    monkeypatch.delenv("DOPPLER_ENVIRONMENT")

    admin_service.update_env_variable("LLM_MODEL", "dummy-local-model")

    contents = isolated_config.read_text(encoding="utf-8")
    assert "LLM_API_KEY=dummy-local-key\n" in contents
    assert "LLM_MODEL=dummy-local-model\n" in contents
    assert "dummy-runtime-key" not in contents
