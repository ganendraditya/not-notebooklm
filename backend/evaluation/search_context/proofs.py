import json
from pathlib import Path
from types import SimpleNamespace

from llama_index.core.llms import ChatMessage

from .cases import TOPICS, build_cases
from .runtime import evaluate_case, load_source_module


class FixedAnswerLLM:
    def __init__(self, topic: str, language_filter_conflict: bool = False):
        self.model = "synthetic-correct-response"
        self.topic = topic
        self.language_filter_conflict = language_filter_conflict
        self.prompt = ""

    async def acomplete(self, prompt: str) -> SimpleNamespace:
        self.prompt = prompt
        return SimpleNamespace(text=json.dumps({
            "en_query": self.topic,
            "native_query": self.topic,
            "target_count": 5,
            "user_requested_count": 5,
            "languages": ["en"],
            "language_filter_conflict": self.language_filter_conflict,
            "min_year": 2024,
            "open_access_only": False,
            "scopus_quartiles": [],
            "sinta_tiers": [],
            "exclude_preprints": False,
            "filter_conflicts": [],
        }))


async def write_proofs(output: Path) -> list[dict]:
    compactor = load_source_module("search_context_token_budget", "rag/token_budget.py")
    planner = load_source_module("search_context_query_planner", "services/search/query_planner.py")
    original_counter = compactor.count_tokens
    compactor.count_tokens = lambda text, model_name=None: max(1, len((text or "").split()))
    results = []
    try:
        for index, topic in enumerate(TOPICS):
            case = next(case for case in build_cases() if case.id == f"filter_override-{index + 1:02d}")
            override = await evaluate_case(
                case,
                "history",
                "replay",
                FixedAnswerLLM(topic.name, language_filter_conflict=True),
                5,
            )
            results.append({
                "id": f"language-override-{index + 1:02d}",
                "mechanism": "preserve_correct_model_language_when_conflict_is_explicit",
                "model_is_synthetic": True,
                "raw_languages": override["raw_plan"]["languages"],
                "final_languages": override["plan"]["languages"],
                "resolved": override["raw_screen"]["passed"] and override["plan"]["languages"] == ["en"],
                "evidence": override,
            })
            history = [ChatMessage(role="user", content=f"The research topic is {topic.name}.")]
            history += [
                ChatMessage(role="user", content="Keep the output concise and preserve table formatting."),
                ChatMessage(role="assistant", content="Formatting is noted and the research topic is unchanged."),
            ] * 40
            compacted = await compactor.acompact_chat_history(
                history,
                max_history_tokens=120,
                summarizer_func=lambda _text, name=topic.name: f"The active research topic is {name}.",
            )
            llm = FixedAnswerLLM(topic.name)
            await planner.plan_academic_search("Find 5 more on that topic in English.", compacted, llm=llm)
            results.append({
                "id": f"summary-handoff-{index + 1:02d}",
                "mechanism": "include_compaction_bridge_as_historical_context_in_planner_prompt",
                "model_is_synthetic": True,
                "token_counter_is_deterministic_word_count": True,
                "summary_contains_topic": topic.name in (compacted[0].content or ""),
                "prompt_contains_topic": topic.name in llm.prompt,
                "resolved": topic.name in (compacted[0].content or "") and topic.name in llm.prompt,
                "compacted_history": [message.model_dump(mode="json") for message in compacted],
                "prompt": llm.prompt,
            })
    finally:
        compactor.count_tokens = original_counter
    (output / "proofs.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    resolved = sum(result["resolved"] for result in results)
    summary_handoffs = sum(result["resolved"] for result in results if result["id"].startswith("summary-handoff-"))
    language_overrides = sum(result["resolved"] for result in results if result["id"].startswith("language-override-"))
    lines = [
        "# Post-fix search-context checks", "",
        f"Resolved deterministic checks: {resolved}/{len(results)} across two code paths and ten synthetic topics.",
        "These checks use the real planner and compactor with fixed synthetic model output. They verify data flow and normalization, not model quality or registry results.",
        "", "## Compaction bridge", "",
        "The real compactor creates a system-role bridge containing a history summary. The planner recognizes the server-generated bridge marker and includes the bridge as historical context, before the current request.",
        f"Topic retained from summary through planner prompt: {summary_handoffs}/10.",
        "The bridge remains contextual data. Other unrecognized system-role messages are omitted.",
        "", "## Language-filter precedence", "",
        "When the model explicitly reports a conflict and returns English, postprocessing preserves English rather than restoring the stale Mandarin filter.",
        f"Correct model language preserved: {language_overrides}/10.",
        "Separate tests verify that a non-conflicting UI filter remains active and malformed model language fields fall back to that filter.",
        "", "## Limits", "",
        "The fixed responses are deliberate test inputs, not live model observations.",
        "The compactor test supplies a fixed summary. It does not measure summarizer accuracy or how often production chats trigger compaction.",
        "The full stress corpus remains a synthetic test set, not an estimate of production success rate.",
        "Full inputs, prompts, and outputs: `proofs.json`.", "",
    ]
    (output / "PROOFS.md").write_text("\n".join(lines), encoding="utf-8")
    return results
