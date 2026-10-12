from types import SimpleNamespace

import journal_indexer

from evaluation.benchmark_indexing_50 import (
    _reported_token_count,
    run_v0_before,
    run_with_isolated_sinta_cache,
    select_sinta_only_seeds,
)


def test_v0_llm_failure_is_recorded_without_a_scored_prediction():
    class FailedLLM:
        def complete(self, _prompt):
            raise RuntimeError("offline")

    result = run_v0_before(
        {"journal": "Unknown Journal", "venue_type": "journal", "issns": []},
        FailedLLM(),
    )

    assert result["status"] == "error"
    assert result["output"] is None
    assert result["llm_called"] is True
    assert result["reported_tokens"] is None


def test_benchmark_uses_provider_reported_token_usage_only():
    openai_response = SimpleNamespace(
        raw={"usage": {"prompt_tokens": 12, "completion_tokens": 8, "total_tokens": 20}}
    )
    gemini_response = SimpleNamespace(
        raw={"usage_metadata": {"prompt_token_count": 12, "candidates_token_count": 8, "total_token_count": 20}}
    )
    response_without_usage = SimpleNamespace(raw={})

    assert _reported_token_count(openai_response) == 20
    assert _reported_token_count(gemini_response) == 20
    assert _reported_token_count(response_without_usage) is None


def test_each_benchmark_variant_gets_an_independent_sinta_cache():
    def lookup_and_cache(_case):
        cached = journal_indexer._read_sinta_cache("12345678")
        if cached is not None:
            return "warm"
        journal_indexer._write_sinta_cache("12345678", {"tier": "S1"})
        return "cold"

    assert run_with_isolated_sinta_cache([{}], lookup_and_cache) == ["cold"]
    assert run_with_isolated_sinta_cache([{}], lookup_and_cache) == ["cold"]


def test_sinta_ground_truth_seeds_exclude_scopus_indexed_issns():
    sinta_only = select_sinta_only_seeds({"22527877", "23547960"})

    assert all(seed["issn"].replace("-", "") not in {"22527877", "23547960"} for seed in sinta_only)
