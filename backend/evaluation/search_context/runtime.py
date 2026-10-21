import asyncio
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import time
from types import ModuleType
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from llama_index.core.llms import ChatMessage

from .cases import SearchContextCase
from .scoring import prompt_contains_topic, screen_plan


BACKEND = Path(__file__).resolve().parents[2]
EVALUATION_SOURCE_FILES = (
    "runtime_environment.py",
    "evaluation/eval_search_context.py",
    "evaluation/search_context/__init__.py",
    "evaluation/search_context/cases.py",
    "evaluation/search_context/proofs.py",
    "evaluation/search_context/report.py",
    "evaluation/search_context/runtime.py",
    "evaluation/search_context/scoring.py",
    "rag/llm_factory.py",
    "rag/token_budget.py",
    "utils/text_processing.py",
)


def load_source_module(name: str, relative_path: str) -> ModuleType:
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, BACKEND / relative_path)
    if spec is None or spec.loader is None:
        raise ImportError(relative_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def source_fingerprint() -> str:
    return hashlib.sha256((BACKEND / "services/search/query_planner.py").read_bytes()).hexdigest()


def _endpoint_fingerprint(base_url: str, protocol: str) -> str:
    parsed = urlsplit(base_url.strip())
    authority = parsed.netloc.rsplit("@", 1)[-1].lower()
    safe_endpoint = urlunsplit((parsed.scheme.lower(), authority, parsed.path.rstrip("/"), "", ""))
    identity = f"{protocol.lower()}\0{safe_endpoint}"
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def evaluation_source_fingerprint() -> str:
    digest = hashlib.sha256()
    for relative_path in EVALUATION_SOURCE_FILES:
        digest.update(relative_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update((BACKEND / relative_path).read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def should_trip_circuit(rows: list[dict[str, Any]]) -> bool:
    fatal_errors = {
        "APIConnectionError", "ConnectError", "ConnectionError",
        "AuthenticationError", "PermissionDeniedError", "InternalServerError",
        "BadRequestError",
    }
    return len(rows) >= 3 and all(row.get("error_type") in fatal_errors for row in rows[-3:])


def safe_error_metadata(error: Exception, llm: Any) -> dict[str, Any]:
    body = getattr(error, "body", None)
    message = body.get("message", "") if isinstance(body, dict) else ""
    if not message and isinstance(body, dict) and isinstance(body.get("error"), dict):
        message = body["error"].get("message", "")
    if not message:
        message = type(error).__name__
    message = str(message)
    key = getattr(llm, "api_key", "")
    if hasattr(key, "get_secret_value"):
        key = key.get_secret_value()
    if isinstance(key, str) and len(key) > 5:
        message = message.replace(key, "[REDACTED]")
    message = re.sub(r"Bearer\s+[^\s\"']+", "Bearer [REDACTED]", message, flags=re.IGNORECASE)
    message = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[REDACTED EMAIL]", message)
    return {"http_status": getattr(error, "status_code", None), "message": message[:1000]}


class ObservedLLM:
    def __init__(self, llm: Any, timeout: float):
        self.llm = llm
        self.timeout = timeout
        self.prompt = ""
        self.text = ""
        self.error_type: str | None = None
        self.error_metadata: dict[str, Any] = {}
        self.response_metadata: dict[str, Any] = {}

    async def acomplete(self, prompt: str) -> Any:
        self.prompt = prompt
        try:
            response = await asyncio.wait_for(self.llm.acomplete(prompt), timeout=self.timeout)
        except Exception as error:
            self.error_type = type(error).__name__
            self.error_metadata = safe_error_metadata(error, self.llm)
            raise
        self.text = response.text
        raw = getattr(response, "raw", None)
        if hasattr(raw, "model_dump"):
            raw = raw.model_dump()
        if isinstance(raw, dict):
            self.response_metadata = {
                key: raw[key] for key in ("model", "usage") if key in raw
            }
        return response


def configured_models(tiers: list[str], model_override: str | None = None) -> list[tuple[str, Any, dict[str, Any]]]:
    factory = load_source_module("search_context_llm_factory", "rag/llm_factory.py")
    models = []
    seen = set()
    for tier in tiers:
        base, key, primary, fast, fallback, temperature, configured, protocol = factory._resolve_tier_credentials(tier)
        configured_model = {"fast": fast, "primary": primary, "fallback": fallback}[tier]
        model = model_override or configured_model
        identity = (base, model, protocol)
        if identity in seen or not configured or not model:
            continue
        seen.add(identity)
        llm = factory._create_llm_instance(
            protocol=protocol,
            base_url=base,
            api_key=key,
            model=model,
            temperature=temperature,
            max_tokens=4096 if tier == "fast" else 16384,
            timeout=45.0,
        )
        if llm is not None:
            if hasattr(llm, "max_retries"):
                llm.max_retries = 0
            models.append((tier, llm, {
                "tier": tier,
                "model": model,
                "protocol": protocol,
                "endpoint_fingerprint": _endpoint_fingerprint(base, protocol),
                "temperature": temperature,
                "model_override": bool(model_override),
                "configured_model": configured_model,
            }))
    return models


async def evaluate_case(
    case: SearchContextCase,
    mode: str,
    tier: str,
    llm: Any,
    timeout: float,
    repeat: int = 0,
) -> dict[str, Any]:
    planner = load_source_module("search_context_query_planner", "services/search/query_planner.py")
    query = case.explicit_query if mode == "explicit" else case.query
    history = [] if mode in {"explicit", "no_history", "fallback"} else list(case.history)
    if mode == "summary_as_user":
        history = [
            type(turn)("user" if turn.role == "system" else turn.role, turn.content)
            for turn in history
        ]
    messages = [ChatMessage(role=turn.role, content=turn.content) for turn in history]
    effective_llm = None if mode == "fallback" else llm
    observed = ObservedLLM(effective_llm, timeout) if effective_llm is not None else None
    started = time.perf_counter()
    plan = await planner.plan_academic_search(query, messages, llm=observed)
    raw_plan = None
    status = "deterministic_fallback" if observed is None else "model_response"
    if observed is not None:
        if observed.error_type:
            status = "transport_error"
        else:
            try:
                raw_plan = json.loads(planner.extract_json_from_llm(observed.text))
                if not isinstance(raw_plan, dict):
                    status = "invalid_model_output"
            except (ValueError, TypeError):
                status = "invalid_model_output"
    return {
        "case_id": case.id,
        "category": case.category,
        "tier": tier,
        "model": getattr(effective_llm, "model", None),
        "mode": mode,
        "repeat": repeat,
        "status": status,
        "error_type": observed.error_type if observed else None,
        "error_metadata": observed.error_metadata if observed else {},
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "history_roles": [turn.role for turn in history],
        "prompt_contains_topic": prompt_contains_topic(case, observed.prompt) if observed else None,
        "prompt": observed.prompt if observed else None,
        "raw_response": observed.text if observed else None,
        "response_metadata": observed.response_metadata if observed else {},
        "raw_plan": raw_plan,
        "plan": plan,
        "screen": screen_plan(case, plan),
        "raw_screen": screen_plan(case, raw_plan) if isinstance(raw_plan, dict) else None,
    }
