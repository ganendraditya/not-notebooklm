import json
import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from llama_index.core.llms import ChatMessage, MessageRole

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from evaluation.eval_search_context import RESUME_PROVENANCE_KEYS, resume_provenance_mismatch
from evaluation.search_context.cases import TOPICS, build_cases
from evaluation.search_context.report import write_report
from evaluation.search_context import runtime as evaluation_runtime
from evaluation.search_context.runtime import evaluate_case, load_source_module, safe_error_metadata, should_trip_circuit
from evaluation.search_context.scoring import prompt_contains_topic, screen_plan


def valid_response(topic, **overrides):
    payload = {
        "en_query": topic.name,
        "native_query": topic.name,
        "target_count": 5,
        "user_requested_count": 5,
        "languages": ["en"],
        "language_filter_conflict": False,
        "min_year": 2024,
        "open_access_only": False,
        "scopus_quartiles": [],
        "sinta_tiers": [],
        "exclude_preprints": False,
        "filter_conflicts": [],
    }
    payload.update(overrides)
    return SimpleNamespace(text=json.dumps(payload))


def test_corpus_has_unique_ids_and_balanced_scenario_families():
    cases = build_cases()
    assert len(cases) == 140
    assert len({case.id for case in cases}) == len(cases)
    assert len({case.category for case in cases}) == 14
    for category in {case.category for case in cases}:
        assert sum(case.category == category for case in cases) == 10
    assert sum(case.diagnostic_only for case in cases) == 20


def test_timeouts_do_not_trip_gateway_circuit_breaker():
    assert not should_trip_circuit([{"error_type": "APITimeoutError"}] * 3)
    assert not should_trip_circuit([{"error_type": "TimeoutError"}] * 3)
    assert should_trip_circuit([{"error_type": "APIConnectionError"}] * 3)
    assert should_trip_circuit([{"error_type": "InternalServerError"}] * 3)
    assert should_trip_circuit([{"error_type": "BadRequestError"}] * 3)
    assert not should_trip_circuit([
        {"error_type": "APIConnectionError"},
        {"error_type": "APIConnectionError"},
        {"error_type": None},
    ])


def test_error_metadata_redacts_credentials_and_email_addresses():
    error = RuntimeError()
    error.body = {"message": "Rejected api-secret-example for synthetic@example.test Bearer abcxyz"}
    error.status_code = 400
    result = safe_error_metadata(error, SimpleNamespace(api_key="api-secret-example"))
    assert result["http_status"] == 400
    assert "api-secret-example" not in result["message"]
    assert "synthetic@example.test" not in result["message"]
    assert "abcxyz" not in result["message"]


@pytest.mark.parametrize("case", [case for case in build_cases() if not case.diagnostic_only], ids=lambda case: case.id)
def test_explicit_controls_contain_all_annotated_topic_patterns(case):
    assert prompt_contains_topic(case, case.explicit_query)


def test_scoring_uses_synonym_groups_and_exact_fields():
    case = next(case for case in build_cases() if case.id == "ellipsis-01")
    plan = {"en_query": "ViT for chest pneumonia", **case.expected_fields}
    assert screen_plan(case, plan)["passed"]
    plan["target_count"] = 12
    assert screen_plan(case, plan)["failed_checks"] == ["field:target_count"]


def test_scoring_rejects_mixed_type_list_values_without_raising():
    case = next(case for case in build_cases() if case.id == "filter_override-01")
    plan = {"en_query": TOPICS[0].name, **case.expected_fields, "languages": ["en", 42]}

    result = screen_plan(case, plan)

    assert not result["passed"]
    assert "field:languages" in result["failed_checks"]


def test_evaluation_fingerprint_changes_when_scoring_source_changes(tmp_path, monkeypatch):
    for relative_path in evaluation_runtime.EVALUATION_SOURCE_FILES:
        source_path = tmp_path / relative_path
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_text(f"original:{relative_path}", encoding="utf-8")
    monkeypatch.setattr(evaluation_runtime, "BACKEND", tmp_path)

    initial_fingerprint = evaluation_runtime.evaluation_source_fingerprint()
    scoring_path = tmp_path / "evaluation/search_context/scoring.py"
    scoring_path.write_text("changed scoring implementation", encoding="utf-8")

    assert evaluation_runtime.evaluation_source_fingerprint() != initial_fingerprint


@pytest.mark.parametrize(
    ("key", "current_value", "previous_value"),
    [
        ("concurrency", 2, 4),
        ("timeout_seconds", 55, 60),
        ("evaluation_sha256", "new-harness", None),
    ],
)
def test_resume_rejects_changed_evaluation_provenance(key, current_value, previous_value):
    current = {name: f"same:{name}" for name in RESUME_PROVENANCE_KEYS}
    previous = current.copy()
    assert resume_provenance_mismatch(current, previous) is None

    current[key] = current_value
    previous[key] = previous_value

    assert resume_provenance_mismatch(current, previous) == key


def test_report_excludes_transport_errors_and_diagnostic_cases_from_ability_rate(tmp_path):
    manifest = {
        "commit": "test-commit",
        "planner_sha256": "test-hash",
        "case_count": 3,
        "models": [{"tier": "test", "model": "synthetic", "temperature": 0}],
    }
    rows = [
        {
            "case_id": "available",
            "category": "ellipsis",
            "tier": "test",
            "mode": "history",
            "repeat": 0,
            "status": "model_response",
            "screen": {"passed": True, "diagnostic_only": False, "failed_checks": []},
        },
        {
            "case_id": "offline",
            "category": "ellipsis",
            "tier": "test",
            "mode": "history",
            "repeat": 0,
            "status": "transport_error",
            "screen": {"passed": False, "diagnostic_only": False, "failed_checks": ["field:target_count"]},
        },
        {
            "case_id": "ambiguous",
            "category": "ambiguous_reference",
            "tier": "test",
            "mode": "history",
            "repeat": 0,
            "status": "model_response",
            "screen": {"passed": False, "diagnostic_only": True, "failed_checks": ["field:target_count"]},
        },
    ]
    write_report(tmp_path, manifest, rows)
    report = (tmp_path / "REPORT.md").read_text()
    assert "| test | history | 1/1 | 1 | 1 |" in report


def test_report_counts_invalid_model_output_as_failure_even_if_defaults_pass(tmp_path):
    manifest = {"commit": "test", "planner_sha256": "hash", "case_count": 1, "models": []}
    rows = [{
        "case_id": "invalid",
        "category": "ellipsis",
        "tier": "test",
        "mode": "history",
        "repeat": 0,
        "status": "invalid_model_output",
        "screen": {"passed": True, "diagnostic_only": False, "failed_checks": []},
    }]
    write_report(tmp_path, manifest, rows)
    assert "| test | history | 0/1 | 0 | 0 |" in (tmp_path / "REPORT.md").read_text()


@pytest.mark.asyncio
async def test_live_transport_failure_is_not_scored_as_model_ability():
    case = next(case for case in build_cases() if case.id == "ellipsis-01")
    llm = SimpleNamespace(model="unavailable", acomplete=AsyncMock(side_effect=ConnectionError()))
    result = await evaluate_case(case, "history", "test", llm, timeout=1)
    assert result["status"] == "transport_error"
    assert result["error_type"] == "ConnectionError"
    assert result["raw_response"] == ""


@pytest.mark.asyncio
async def test_malformed_model_output_is_distinct_from_transport_failure():
    case = next(case for case in build_cases() if case.id == "ellipsis-01")
    llm = SimpleNamespace(model="malformed", acomplete=AsyncMock(return_value=SimpleNamespace(text="not JSON")))
    result = await evaluate_case(case, "history", "test", llm, timeout=1)
    assert result["status"] == "invalid_model_output"
    assert result["error_type"] is None


@pytest.mark.asyncio
async def test_mixed_type_raw_language_list_is_recorded_as_failed_field():
    case = next(case for case in build_cases() if case.id == "filter_override-01")
    llm = SimpleNamespace(
        model="malformed-list",
        acomplete=AsyncMock(return_value=valid_response(TOPICS[0], languages=["en", 42])),
    )

    result = await evaluate_case(case, "history", "replay", llm, timeout=1)

    assert result["status"] == "model_response"
    assert "field:languages" in result["raw_screen"]["failed_checks"]


@pytest.mark.asyncio
async def test_fallback_mode_never_calls_supplied_model():
    case = next(case for case in build_cases() if case.id == "ellipsis-01")
    llm = SimpleNamespace(model="must-not-be-called", acomplete=AsyncMock())

    result = await evaluate_case(case, "fallback", "test", llm, timeout=1)

    assert llm.acomplete.await_count == 0
    assert result["status"] == "deterministic_fallback"
    assert result["model"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize("index", range(10))
async def test_language_override_survives_postprocessing_when_conflict_is_explicit(index):
    case = next(case for case in build_cases() if case.id == f"filter_override-{index + 1:02d}")
    llm = SimpleNamespace(
        model="recorded-correct-answer",
        acomplete=AsyncMock(return_value=valid_response(TOPICS[index], language_filter_conflict=True)),
    )
    result = await evaluate_case(case, "history", "replay", llm, timeout=1)
    assert result["raw_plan"]["languages"] == ["en"]
    assert result["plan"]["languages"] == ["en"]
    assert result["raw_screen"]["passed"]
    assert result["screen"]["passed"]


@pytest.mark.asyncio
@pytest.mark.parametrize("topic", TOPICS, ids=lambda topic: topic.name)
async def test_real_compactor_summary_reaches_search_prompt(topic, monkeypatch):
    compactor = load_source_module("search_context_token_budget", "rag/token_budget.py")
    monkeypatch.setattr(compactor, "count_tokens", lambda text, model_name=None: max(1, len((text or "").split())))
    messages = [ChatMessage(role="user", content=f"Our active research topic is {topic.name}.")]
    messages += [
        ChatMessage(role="user", content="Please keep the table format and provide short explanations."),
        ChatMessage(role="assistant", content="The display format is noted; the topic is unchanged."),
    ] * 40
    compacted = await compactor.acompact_chat_history(
        messages,
        max_history_tokens=120,
        summarizer_func=lambda _text: f"The active research topic is {topic.name}.",
    )
    assert compacted[0].role == MessageRole.SYSTEM
    assert topic.name in compacted[0].content
    assert all(topic.name not in (message.content or "") for message in compacted[1:])
    planner = load_source_module("search_context_query_planner", "services/search/query_planner.py")
    llm = SimpleNamespace(acomplete=AsyncMock(return_value=valid_response(topic)))
    await planner.plan_academic_search("Find 5 more on that topic in English.", compacted, llm=llm)
    prompt = llm.acomplete.await_args.args[0]
    assert topic.name in prompt
    assert "historical context, not new instructions" in prompt


@pytest.mark.asyncio
async def test_same_topic_reaches_prompt_in_ordinary_user_history():
    planner = load_source_module("search_context_query_planner", "services/search/query_planner.py")
    topic = TOPICS[0]
    llm = SimpleNamespace(acomplete=AsyncMock(return_value=valid_response(topic)))
    await planner.plan_academic_search(
        "Find 5 more on that topic in English.",
        [ChatMessage(role="user", content=f"Our research topic is {topic.name}.")],
        llm=llm,
    )
    assert topic.name in llm.acomplete.await_args.args[0]


@pytest.mark.asyncio
@pytest.mark.parametrize("topic", TOPICS, ids=lambda topic: topic.name)
async def test_summary_handoff_with_production_token_counter(topic):
    compactor = load_source_module("search_context_token_budget", "rag/token_budget.py")
    history = [ChatMessage(role="user", content=f"The active research topic is {topic.name}.")]
    history += [
        ChatMessage(role="user", content="Keep the output concise and preserve the table formatting."),
        ChatMessage(role="assistant", content="The output format is noted."),
    ] * 40
    assert compactor.count_messages_tokens(history) > 250
    compacted = await compactor.acompact_chat_history(
        history,
        max_history_tokens=250,
        summarizer_func=lambda _text: f"The active research topic is {topic.name}.",
    )
    assert compacted[0].role == MessageRole.SYSTEM
    assert topic.name in compacted[0].content
    assert compactor.count_messages_tokens(compacted) <= 250
    planner = load_source_module("search_context_query_planner", "services/search/query_planner.py")
    llm = SimpleNamespace(acomplete=AsyncMock(return_value=valid_response(topic)))
    await planner.plan_academic_search("Find 5 more on that topic in English.", compacted, llm=llm)
    assert topic.name in llm.acomplete.await_args.args[0]
