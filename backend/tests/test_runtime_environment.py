import ast
import builtins
import importlib.util
import os
from pathlib import Path
import runpy
import sys
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

import runtime_environment


BACKEND_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture
def local_env(tmp_path, monkeypatch):
    backend = tmp_path / "backend"
    backend.mkdir()
    path = backend / ".env"
    values = {
        "DOTENV_FIXTURE_VALUE": "dummy-file-value",
        "DOTENV_FIXTURE_EMPTY": "dummy-nonempty-value",
        "DATABASE_URL": f"sqlite:///{tmp_path / 'fixture.db'}",
        "LLM_API_KEY": "dummy-file-key",
        "LLM_BASE_URL": "https://fixture.invalid/v1",
        "QDRANT_URL": "http://fixture.invalid:6333",
        "ALLOWED_ORIGINS": "http://localhost:3000",
    }
    path.write_text("".join(f"{key}={value}\n" for key, value in values.items()), encoding="utf-8")
    monkeypatch.setattr(runtime_environment, "BACKEND_ENV_PATH", path)
    with patch.dict(os.environ):
        for key in values:
            monkeypatch.delenv(key, raising=False)
        monkeypatch.delenv("PYTHON_DOTENV_DISABLED", raising=False)
        yield path, values


def test_initializer_import_does_not_load_environment(monkeypatch):
    loader = Mock()
    monkeypatch.setattr("dotenv.load_dotenv", loader)
    spec = importlib.util.spec_from_file_location("isolated_runtime_environment", BACKEND_DIR / "runtime_environment.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    loader.assert_not_called()
    assert module.BACKEND_ENV_PATH == BACKEND_DIR / ".env"


def test_initializer_loads_only_backend_file_from_unrelated_cwd(local_env, tmp_path, monkeypatch):
    path, values = local_env
    unrelated = tmp_path / "unrelated"
    unrelated.mkdir()
    (unrelated / ".env").write_text("DOTENV_FIXTURE_VALUE=dummy-cwd-value\n", encoding="utf-8")
    monkeypatch.chdir(unrelated)
    original = path.read_bytes()

    assert runtime_environment.load_backend_environment() is True
    assert {key: os.environ[key] for key in values} == values
    assert path.read_bytes() == original


@pytest.mark.parametrize("injected_value", ["dummy-injected-value", ""])
@pytest.mark.parametrize("marker", [{}, {"DOPPLER_ENVIRONMENT": "dummy-dev"}, {"INFISICAL_INJECTED": "1"}])
def test_existing_values_take_precedence_and_missing_values_still_load(local_env, monkeypatch, injected_value, marker):
    for key, value in marker.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("DOTENV_FIXTURE_VALUE", injected_value)

    runtime_environment.load_backend_environment()

    assert os.environ["DOTENV_FIXTURE_VALUE"] == injected_value
    assert os.environ["DOTENV_FIXTURE_EMPTY"] == "dummy-nonempty-value"
    for key, value in marker.items():
        assert os.environ[key] == value


def test_missing_backend_file_does_not_fall_back_to_parent_or_create_file(local_env, tmp_path, monkeypatch):
    path, _ = local_env
    path.unlink()
    parent_env = tmp_path / ".env"
    parent_env.write_text("DOTENV_FIXTURE_VALUE=dummy-parent-value\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert runtime_environment.load_backend_environment() is False
    assert "DOTENV_FIXTURE_VALUE" not in os.environ
    assert not path.exists()
    assert parent_env.read_text(encoding="utf-8") == "DOTENV_FIXTURE_VALUE=dummy-parent-value\n"


def test_interpolation_uses_injected_values(local_env, monkeypatch):
    path, _ = local_env
    path.write_text("DOTENV_FIXTURE_VALUE=dummy-local\nDOTENV_FIXTURE_EMPTY=${DOTENV_FIXTURE_VALUE}/suffix\n", encoding="utf-8")
    monkeypatch.setenv("DOTENV_FIXTURE_VALUE", "dummy-injected")

    runtime_environment.load_backend_environment()

    assert os.environ["DOTENV_FIXTURE_EMPTY"] == "dummy-injected/suffix"


def test_explicit_dotenv_disable_is_respected(local_env, monkeypatch):
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")

    assert runtime_environment.load_backend_environment() is False
    assert "DOTENV_FIXTURE_VALUE" not in os.environ


class ReachedConsumer(BaseException):
    pass


@pytest.mark.parametrize(
    ("relative_path", "consumer"),
    [
        ("main.py", "database"),
        ("evaluation/run_benchmark.py", "rag.llm_factory"),
        ("evaluation/eval_full50_niah.py", "rag.llm_factory"),
        ("evaluation/eval_conversational_niah.py", "rag.llm_factory"),
        ("evaluation/benchmark_indexing_before_after.py", "rag.llm_factory"),
        ("evaluation/benchmark_indexing_3way.py", "rag.llm_factory"),
        ("evaluation/benchmark_indexing_50.py", "rag.llm_factory"),
        ("evaluation/benchmark_indexing_status.py", "benchmark_indexing_50"),
        ("evaluation/benchmark_retrieval_head_to_head.py", "qdrant_client"),
    ],
)
def test_entry_points_initialize_before_configuration_consumers(local_env, monkeypatch, relative_path, consumer):
    _, values = local_env
    original_import = builtins.__import__
    initialized = []
    loader = Mock(wraps=runtime_environment.load_backend_environment)
    monkeypatch.setattr(runtime_environment, "load_backend_environment", loader)
    monkeypatch.setattr(sys, "path", sys.path.copy())
    monkeypatch.setattr(sys, "argv", [relative_path])

    def import_until_consumer(name, globals=None, locals=None, fromlist=(), level=0):
        if name == consumer:
            initialized.append({key: os.environ.get(key) for key in values})
            raise ReachedConsumer
        if name.startswith("fastapi"):
            return SimpleNamespace(FastAPI=object, CORSMiddleware=object, StaticFiles=object)
        if name == "journal_indexer":
            return SimpleNamespace(lookup_journal_index=None, lookup_sinta_live=None, SCOPUS_DB_PATH="unused")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", import_until_consumer)
    with pytest.raises(ReachedConsumer):
        runpy.run_path(str(BACKEND_DIR / relative_path), run_name="__main__")

    assert initialized == [values]
    loader.assert_called_once_with()


def test_api_preserves_injected_database_url_before_database_import(local_env, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    original_import = builtins.__import__
    observed = []

    def import_until_database(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "database":
            observed.append(os.environ["DATABASE_URL"])
            raise ReachedConsumer
        if name.startswith("fastapi"):
            return SimpleNamespace(FastAPI=object, CORSMiddleware=object, StaticFiles=object)
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", import_until_database)
    with pytest.raises(ReachedConsumer):
        runpy.run_path(str(BACKEND_DIR / "main.py"))

    assert observed == ["sqlite:///:memory:"]


def test_cli_initializes_before_command_dispatch(local_env, monkeypatch):
    from cli import main as cli_main

    _, values = local_env
    observed = []
    monkeypatch.setattr(sys, "argv", ["notbooklm", "init"])
    monkeypatch.setattr(cli_main, "run_init_wizard", lambda: observed.append({key: os.environ.get(key) for key in values}))

    cli_main.main()

    assert observed == [values]


@pytest.mark.parametrize("relative_path", ["services/admin_service.py", "rag/llm_factory.py"])
def test_library_import_does_not_refill_removed_values(local_env, monkeypatch, relative_path):
    original_import = builtins.__import__

    def import_with_llm_adapters_stubbed(name, globals=None, locals=None, fromlist=(), level=0):
        if name in ("llama_index.llms.openai_like", "llama_index.llms.anthropic"):
            return SimpleNamespace(OpenAILike=object, Anthropic=object)
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", import_with_llm_adapters_stubbed)
    monkeypatch.setattr("dotenv.load_dotenv", Mock(side_effect=AssertionError("Library import must not load dotenv")))

    runpy.run_path(str(BACKEND_DIR / relative_path))

    assert "DOTENV_FIXTURE_VALUE" not in os.environ


@pytest.mark.parametrize("directory", ["rag", "services", "providers", "utils", "cli", "evaluation"])
def test_dotenv_dependency_is_owned_by_initializer(directory):
    for path in (BACKEND_DIR / directory).rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert node.module != "dotenv", path.relative_to(BACKEND_DIR)
                if directory in ("rag", "services", "providers", "utils"):
                    assert node.module != "runtime_environment", path.relative_to(BACKEND_DIR)
            elif isinstance(node, ast.Import):
                assert all(alias.name != "dotenv" for alias in node.names), path.relative_to(BACKEND_DIR)
