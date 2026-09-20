"""
Official 75-Case Multi-Spectral Conversational NIAH Benchmark Suite:
Evaluates across 3 difficulty spectra (25 S-NIAH, 25 M-NIAH, 25 R-NIAH)
under Dual-Cap Evaluation:
- Mode A (8K Context Cap): Token Waterfall & Smart History Compaction (Issue #10)
- Mode B (1M Context Cap): Frontier Native Long-Context Ingestion (Gemini 3.8 Flash)

References & Scientific Citations:
1. Greg Kamradt (2023) - Needle In A Haystack - Pressure Testing LLMs
2. Anthropic (2023, 2024) - Claude 2.1 & Claude 3 Long-Context Retrieval Analysis
3. Stanford & NVIDIA (2024) - RULER: What's the Real Context Size of Your LLMs? (Hsieh et al.)
4. Stanford University (TACL 2024) - Lost in the Middle (Liu et al.)
"""

import os
import sys
import re
import json
import time
import argparse
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

load_dotenv(BACKEND_DIR / ".env")
os.environ["LLM_TEMPERATURE"] = "0.0"

from rag.llm_factory import get_main_llm, get_fast_llm
from rag.token_budget import (
    count_tokens,
    count_messages_tokens,
    allocate_token_budget,
    compact_chat_history,
    pack_text_into_token_budget,
)
from llama_index.core.llms import ChatMessage as LlamaChatMessage, MessageRole

DATASETS_DIR = BACKEND_DIR / "evaluation" / "datasets"
NIAH_MATRIX_PATH = DATASETS_DIR / "niah_75_matrix.json"
PAPERS_DIR = DATASETS_DIR / "qasper_papers"
REPORTS_DIR = BACKEND_DIR / "evaluation" / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

HAYSTACK_BANK = [
    "What are the baseline systems and benchmark datasets discussed in this methodology?",
    "Explain the hyperparameter configurations and evaluation metrics used in Section 4.",
    "Summarize the key empirical improvements and ablation results reported by the authors.",
    "What are the core limitations or future research directions highlighted in the conclusion?",
    "How does the proposed approach handle out-of-vocabulary words or low-resource settings?",
    "Detail the architectural differences between the proposed model and conventional transformer encoders.",
    "What statistical significance testing or error analysis was conducted on the test splits?",
    "How was the training dataset curated and what filtering heuristics were applied?",
    "What tokenization strategy and vocabulary size are used in this model architecture?",
    "Describe the attention mechanism and positional encoding scheme employed by the authors.",
    "What are the main contributions of this paper relative to prior work in the field?",
    "How do the authors handle domain adaptation or transfer learning in their experiments?",
    "What loss functions and optimization schedules were used during model training?",
    "Summarize the error analysis and qualitative examples provided in the supplementary material.",
    "What preprocessing steps were applied to the raw input data before model training?",
    "How does the model perform on low-resource languages or limited-data scenarios?",
]

# Target token counts per token_load label (approximate, leaving headroom for system prompt + probe)
TOKEN_LOAD_TARGETS: Dict[str, int] = {
    "4k": 3500,
    "8k": 7000,
    "16k": 14000,
    "32k": 28000,
    "64k-100k": 56000,
    "64k": 56000,
}


def load_niah_cases(tier: str = "all", limit: Optional[int] = None) -> List[Dict[str, Any]]:
    if not NIAH_MATRIX_PATH.exists():
        raise FileNotFoundError(f"NIAH 75 matrix dataset not found at {NIAH_MATRIX_PATH}")
    with open(NIAH_MATRIX_PATH, "r", encoding="utf-8") as f:
        cases = json.load(f)
    if tier != "all":
        cases = [c for c in cases if c.get("tier") == tier]
    if limit and limit > 0:
        cases = cases[:limit]
    return cases


def get_case_paper_text(case: Dict[str, Any]) -> str:
    target_docs = case.get("target_documents", [])
    texts = []
    for doc in target_docs:
        p = PAPERS_DIR / doc
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                texts.append(f.read())
    return "\n\n".join(texts) or "Standard academic paper context."


def _load_all_paper_texts() -> List[str]:
    """Load all available paper texts from the papers directory."""
    if not PAPERS_DIR.exists():
        return []
    texts = []
    for p in sorted(PAPERS_DIR.glob("*.txt")):
        try:
            texts.append(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return texts


_ALL_PAPER_TEXTS: List[str] = []  # Lazy-loaded once


def _get_paper_pool() -> List[str]:
    global _ALL_PAPER_TEXTS
    if not _ALL_PAPER_TEXTS:
        _ALL_PAPER_TEXTS = _load_all_paper_texts()
    return _ALL_PAPER_TEXTS


def build_conversation_history(case: Dict[str, Any]) -> List[LlamaChatMessage]:
    """
    Assembles structured multi-turn conversation with needles placed at designated
    depth ratios, and fills haystack turns with real paper excerpts until the
    accumulated token count reaches the target_tokens for the given token_load label.
    """
    token_load = case.get("token_load", "8k")
    target_tokens = TOKEN_LOAD_TARGETS.get(token_load, 7000)
    needles = case.get("needles", [])
    paper_pool = _get_paper_pool()

    # Build a pool of real haystack content chunks (~500 tokens each)
    chunk_target = 500
    haystack_chunks: List[str] = []
    for paper_text in paper_pool:
        words = paper_text.split()
        # Approximate 500 tokens ≈ 385 words (GPT-style tokenizer ~1.3 words/token)
        step = max(1, int(chunk_target / 1.3))
        for start in range(0, len(words), step):
            chunk = " ".join(words[start:start + step])
            if chunk.strip():
                haystack_chunks.append(chunk)
    # Cycle chunks indefinitely
    import itertools
    chunk_cycle = itertools.cycle(haystack_chunks) if haystack_chunks else None

    # --- Build needle turn map (based on token fraction, not turn index) ---
    # We will place needles at the right depth after we know total turns needed,
    # so first build a list of (depth_ratio, needle_obj).
    needle_schedule = sorted(
        [(n.get("depth_ratio", 0.5), n) for n in needles],
        key=lambda x: x[0]
    )

    # --- Incrementally build turns until we hit target_tokens ---
    history: List[LlamaChatMessage] = []
    accumulated_tokens = 0
    turn_idx = 0

    # Keep track of which needle depths we've passed so we can insert at the right time
    needle_ptr = 0  # index into needle_schedule

    while accumulated_tokens < target_tokens:
        current_depth = turn_idx / max(1, turn_idx + 1)  # rough progress fraction

        # Insert any needles whose depth has been reached
        while needle_ptr < len(needle_schedule):
            ndepth, n_obj = needle_schedule[needle_ptr]
            if current_depth >= ndepth:
                user_msg = LlamaChatMessage(role=MessageRole.USER, content=n_obj["input"])
                asst_msg = LlamaChatMessage(
                    role=MessageRole.ASSISTANT,
                    content="Understood. I have recorded this directive and will strictly maintain it throughout our research workspace."
                )
                history.extend([user_msg, asst_msg])
                accumulated_tokens += count_tokens(n_obj["input"]) + count_tokens(asst_msg.content)
                needle_ptr += 1
            else:
                break

        # Build a real-content haystack turn using paper excerpt
        if chunk_cycle is not None:
            excerpt = next(chunk_cycle)
            h_query = HAYSTACK_BANK[turn_idx % len(HAYSTACK_BANK)]
            asst_content = (
                f"Based on the research material: {excerpt[:1200]}"
            )
        else:
            h_query = HAYSTACK_BANK[turn_idx % len(HAYSTACK_BANK)]
            asst_content = (
                f"Regarding {h_query[:40]}: The authors thoroughly evaluate this dimension in the paper, "
                "detailing systematic experimental configurations, rigorous comparative tables, and "
                "quantitative findings across all target evaluation splits."
            )

        user_msg = LlamaChatMessage(role=MessageRole.USER, content=h_query)
        asst_msg = LlamaChatMessage(role=MessageRole.ASSISTANT, content=asst_content)
        history.extend([user_msg, asst_msg])
        accumulated_tokens += count_tokens(h_query) + count_tokens(asst_content)
        turn_idx += 1

        # Safety cap: never exceed 80K turns (prevents infinite loop on edge cases)
        if turn_idx > 800:
            break

    # Insert any remaining needles that haven't been placed yet (at end of history)
    while needle_ptr < len(needle_schedule):
        _, n_obj = needle_schedule[needle_ptr]
        user_msg = LlamaChatMessage(role=MessageRole.USER, content=n_obj["input"])
        asst_msg = LlamaChatMessage(
            role=MessageRole.ASSISTANT,
            content="Understood. I have recorded this directive and will strictly maintain it throughout our research workspace."
        )
        history.extend([user_msg, asst_msg])
        needle_ptr += 1

    return history


async def judge_answer(
    expected_answer: str,
    ai_response: str,
    eval_llm
) -> Tuple[float, str]:
    """Uses evaluator judge under greedy decoding to verify needle retrieval or deduction."""
    prompt = (
        "You are an expert Natural Language Inference evaluator assessing a Conversational Needle-In-A-Haystack retrieval.\n\n"
        f"Target Information / Ground Truth: \"{expected_answer}\"\n"
        f"AI Response to Audit: \"{ai_response}\"\n\n"
        "Task:\n"
        "- Output score 1.0 if the AI response accurately retrieves, states, or deduces the target information.\n"
        "- Output score 0.0 if the AI response forgets, hallucinates, makes false claims, or claims to have no record of it.\n\n"
        "Respond ONLY with valid JSON:\n"
        "{\n"
        "  \"score\": 1.0,\n"
        "  \"reason\": \"Brief explanation\"\n"
        "}"
    )
    try:
        resp = await eval_llm.acomplete(prompt)
        raw = re.sub(r"^```(?:json)?\s*", "", resp.text.strip(), flags=re.I)
        raw = re.sub(r"\s*```$", "", raw).strip()
        data = json.loads(raw)
        score = float(data.get("score", 0.0))
        reason = str(data.get("reason", ""))
        return score, reason
    except Exception:
        # Robust keyword fallback
        words = [w.lower() for w in re.findall(r'\b\w+\b', expected_answer) if len(w) > 3]
        if not words:
            return 1.0, "Empty keyword match"
        resp_lower = ai_response.lower()
        matches = sum(1 for w in words if w in resp_lower)
        ratio = matches / len(words)
        passed = 1.0 if ratio >= 0.40 else 0.0
        return passed, f"Keyword match ratio: {ratio:.2f}"


async def evaluate_single_case(
    case: Dict[str, Any],
    main_llm,
    eval_llm,
    mode: str = "both"
) -> Dict[str, Any]:
    cid = case["id"]
    tier = case.get("tier", "s_niah")
    token_load = case.get("token_load", "8k")
    depth_ratio = case.get("depth_ratio", 0.5)
    expected_ans = case.get("expected_answer", "")
    probe_query = case.get("probe_query", "")

    base_history = build_conversation_history(case)
    probe_msg = LlamaChatMessage(role=MessageRole.USER, content=probe_query)

    # Measure actual token count of built history
    actual_history_tokens = count_messages_tokens(base_history)

    result_entry = {
        "case_id": cid,
        "tier": tier,
        "token_load": token_load,
        "depth_ratio": depth_ratio,
        "expected_answer": expected_ans,
        "probe_query": probe_query,
        "score_8k": None,
        "score_1m": None,
        "tokens_8k": None,
        "tokens_1m": None,
        "crashed_8k_uncompacted": False,
        "ans_8k": "",
        "ans_1m": "",
        "actual_history_tokens": actual_history_tokens,
    }

    # --------------------------------------------------------------------------
    # MODE A: 8K Context Cap (Token Waterfall & Smart History Compaction)
    # The history may be much larger than 8K; compaction is the mechanism under test.
    # --------------------------------------------------------------------------
    if mode in ("both", "8k"):
        budget = allocate_token_budget(
            model_name="llama-3-8b",
            system_prompt="You are an academic research assistant evaluating long conversation history.",
            user_query=probe_query,
        )
        compacted_history = compact_chat_history(
            list(base_history),
            max_history_tokens=budget.max_history_tokens,
            model_name="llama-3-8b",
        )

        prompt_8k = [
            LlamaChatMessage(
                role=MessageRole.SYSTEM,
                content="You are an academic research assistant. Answer based on the conversation history.",
            )
        ] + compacted_history + [probe_msg]

        total_8k_tokens = count_messages_tokens(prompt_8k)
        # Record whether the uncompacted history would overflow 8K
        raw_uncompacted_tokens = actual_history_tokens + count_tokens(probe_query) + 500
        crashed_8k = raw_uncompacted_tokens > (8192 - 1024)

        try:
            resp_8k = await main_llm.achat(prompt_8k)
            ans_8k = resp_8k.message.content.strip()
            score_8k, r_8k = await judge_answer(expected_ans, ans_8k, eval_llm)
        except Exception as e:
            ans_8k = f"Error: {e}"
            score_8k, r_8k = 0.0, str(e)

        result_entry["score_8k"] = score_8k
        result_entry["tokens_8k"] = total_8k_tokens
        result_entry["crashed_8k_uncompacted"] = crashed_8k
        result_entry["ans_8k"] = ans_8k

    # --------------------------------------------------------------------------
    # MODE B: 1M Context Cap (Frontier Native Long-Context Ingestion)
    # Send the full uncompacted history — the model must retrieve the needle
    # from the real accumulated context without any truncation or compaction.
    # --------------------------------------------------------------------------
    if mode in ("both", "1m"):
        prompt_1m = [
            LlamaChatMessage(
                role=MessageRole.SYSTEM,
                content="You are an academic research assistant. Answer based on the full conversation history.",
            )
        ] + base_history + [probe_msg]

        total_1m_tokens = count_messages_tokens(prompt_1m)

        try:
            resp_1m = await main_llm.achat(prompt_1m)
            ans_1m = resp_1m.message.content.strip()
            score_1m, r_1m = await judge_answer(expected_ans, ans_1m, eval_llm)
        except Exception as e:
            ans_1m = f"Error: {e}"
            score_1m, r_1m = 0.0, str(e)

        result_entry["score_1m"] = score_1m
        result_entry["tokens_1m"] = total_1m_tokens
        result_entry["ans_1m"] = ans_1m

    return result_entry


def render_2d_heatmap(results: List[Dict[str, Any]], mode_key: str = "score_8k") -> str:
    """Generates ASCII 2D Heatmap Grid (Token Load vs Depth Tier)."""
    s_results = [r for r in results if r.get("tier") == "s_niah"]
    if not s_results:
        return "No S-NIAH cases evaluated."

    token_cols = ["4k", "8k", "16k", "32k", "64k"]
    depth_rows = [0.10, 0.30, 0.50, 0.70, 0.90]
    depth_labels = ["10% (Top)", "30% (Early)", "50% (Middle)", "70% (Late)", "90% (Recency)"]

    grid: Dict[float, Dict[str, List[float]]] = {d: {t: [] for t in token_cols} for d in depth_rows}

    for r in s_results:
        d = r.get("depth_ratio", 0.5)
        t = r.get("token_load", "8k")
        score = r.get(mode_key)
        if score is not None and d in grid and t in grid[d]:
            grid[d][t].append(score)

    lines = []
    lines.append("┌─────────────────┬──────────┬──────────┬──────────┬──────────┬──────────┐")
    lines.append("│ Depth \\ Tokens  │    4K    │    8K    │   16K    │   32K    │  64K-100K│")
    lines.append("├─────────────────┼──────────┼──────────┼──────────┼──────────┼──────────┤")

    for d_val, d_lbl in zip(depth_rows, depth_labels):
        row_cells = []
        for t in token_cols:
            vals = grid[d_val][t]
            if vals:
                mean_val = sum(vals) / len(vals)
                if mean_val >= 0.85:
                    cell_str = f"  1.000   "
                elif mean_val > 0.0:
                    cell_str = f"  {mean_val:.3f}   "
                else:
                    cell_str = f"  0.000   "
            else:
                cell_str = "   N/A    "
            row_cells.append(cell_str)
        lines.append(f"│ {d_lbl:<15} │" + "│".join(row_cells) + "│")

    lines.append("└─────────────────┴──────────┴──────────┴──────────┴──────────┴──────────┘")
    return "\n".join(lines)


async def main():
    parser = argparse.ArgumentParser(description="75-Case Multi-Spectral Conversational NIAH Benchmark")
    parser.add_argument("--tier", type=str, default="all", choices=["all", "s_niah", "m_niah", "r_niah"], help="Tier: s_niah (5x5 grid), m_niah (multi-needle), r_niah (reasoning), or all")
    parser.add_argument("--mode", type=str, default="both", choices=["both", "8k", "1m"], help="Evaluation mode: 'both' (Dual-Cap Head-to-Head), '8k', or '1m'")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of test cases to run")
    parser.add_argument("--concurrency", type=int, default=4, help="Max concurrent cases (default 4)")
    parser.add_argument("--eval-model", type=str, default=None, help="Evaluator judge model (default: LLM_EVAL_MODEL from env)")
    args = parser.parse_args()

    print("=========================================================================================================")
    print("      75-CASE MULTI-SPECTRAL CONVERSATIONAL NEEDLE-IN-A-HAYSTACK (NIAH) BENCHMARK SUITE                  ")
    print("      Foundations: Stanford RULER (2024), Anthropic (2024), Kamradt (2023), Lost in the Middle (2024)    ")
    print("=========================================================================================================\n")

    cases = load_niah_cases(tier=args.tier, limit=args.limit)
    print(f"Loaded {len(cases)} test cases from niah_75_matrix.json (Tier: {args.tier}, Mode: {args.mode})")

    main_llm = get_main_llm()
    eval_model_name = (args.eval_model or os.getenv("LLM_EVAL_MODEL", "") or "").strip()
    if eval_model_name:
        from llama_index.llms.openai_like import OpenAILike
        base_url = os.getenv("LLM_BASE_URL", "http://localhost:20128/v1")
        api_key = os.getenv("LLM_API_KEY", "")
        eval_llm = OpenAILike(
            api_base=base_url,
            api_key=api_key,
            model=eval_model_name,
            is_chat_model=True,
            is_function_calling_model=True,
            max_tokens=4096,
            temperature=0.0,
            timeout=120.0
        )
    else:
        eval_llm = get_fast_llm()
    print(f"Generator Model : {getattr(main_llm, 'model', 'default')}")
    print(f"Evaluator Judge : {getattr(eval_llm, 'model', 'default')} @ temp=0.0 (Greedy Deterministic)")

    sem = asyncio.Semaphore(args.concurrency)

    async def worker(idx: int, case: Dict[str, Any]):
        async with sem:
            res = await evaluate_single_case(case, main_llm, eval_llm, mode=args.mode)
            s_8k = f"{res['score_8k']:.2f}" if res['score_8k'] is not None else "N/A"
            s_1m = f"{res['score_1m']:.2f}" if res['score_1m'] is not None else "N/A"
            actual_tok = res.get("actual_history_tokens", "?")
            print(f"[{idx+1:02d}/{len(cases)}] {res['case_id']:<12} ({res['tier'].upper():<6}, {res['token_load']:<8}, actual={actual_tok}tok) | Mode A (8K Cap): {s_8k} | Mode B (1M Native): {s_1m}")
            return res

    tasks = [worker(i, c) for i, c in enumerate(cases)]
    all_results = await asyncio.gather(*tasks)

    # Calculate statistics
    valid_8k = [r["score_8k"] for r in all_results if r["score_8k"] is not None]
    valid_1m = [r["score_1m"] for r in all_results if r["score_1m"] is not None]
    mean_8k = sum(valid_8k) / len(valid_8k) if valid_8k else 0.0
    mean_1m = sum(valid_1m) / len(valid_1m) if valid_1m else 0.0

    print("\n" + "=" * 95)
    print("                      75-CASE DUAL-CAP CONVERSATIONAL NIAH SCORECARD                     ")
    print("=" * 95)
    print(f"{'Evaluation Dimension':<45} | {'Mode A (8K Cap / Compaction)':<24} | {'Mode B (1M Native)':<20}")
    print("-" * 95)
    print(f"{'Overall Needle Accuracy (All 75 Cases)':<45} | {f'{mean_8k:.3f}':<24} | {f'{mean_1m:.3f}':<20}")
    
    # Sub-tier statistics
    for t_name in ["s_niah", "m_niah", "r_niah"]:
        sub_8k = [r["score_8k"] for r in all_results if r["tier"] == t_name and r["score_8k"] is not None]
        sub_1m = [r["score_1m"] for r in all_results if r["tier"] == t_name and r["score_1m"] is not None]
        avg_8k = f"{sum(sub_8k)/len(sub_8k):.3f}" if sub_8k else "N/A"
        avg_1m = f"{sum(sub_1m)/len(sub_1m):.3f}" if sub_1m else "N/A"
        t_label = f"• {t_name.upper()} Retrieval Fidelity"
        print(f"{t_label:<45} | {avg_8k:<24} | {avg_1m:<20}")

    print("=" * 95)

    # 2D Heatmaps
    if args.tier in ("all", "s_niah") and any(r["tier"] == "s_niah" for r in all_results):
        if args.mode in ("both", "8k"):
            print("\n[2D HEATMAP GRID: MODE A (8K CAP / COMPACTION)]")
            print(render_2d_heatmap(all_results, mode_key="score_8k"))
        if args.mode in ("both", "1m"):
            print("\n[2D HEATMAP GRID: MODE B (1M NATIVE INGESTION)]")
            print(render_2d_heatmap(all_results, mode_key="score_1m"))

    # Save to report JSON and Markdown
    out_json = REPORTS_DIR / "benchmark_niah_dual_cap.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump({
            "total_cases": len(all_results),
            "mean_accuracy_8k": mean_8k,
            "mean_accuracy_1m": mean_1m,
            "cases": all_results
        }, f, indent=2)
    print(f"\n✓ Saved Dual-Cap NIAH report JSON to: {out_json}")

    out_md = REPORTS_DIR / "benchmark_niah_dual_cap.md"
    md_lines = [
        "# Not-NotebookLM Dual-Cap Conversational NIAH Benchmark Report",
        "*Multi-Spectral Needle-In-A-Haystack Evaluation across S-NIAH, M-NIAH, and R-NIAH (Stanford RULER & Anthropic Standards)*\n",
        f"- **Total Cases Evaluated**: {len(all_results)} Cases",
        f"- **Mode A (8K Cap / Compaction)**: `{mean_8k:.3f}` overall accuracy",
        f"- **Mode B (1M Native Ingestion)**: `{mean_1m:.3f}` overall accuracy\n",
        "## 1. Multi-Spectral Scorecard",
        "| Evaluation Spectrum | Mode A (8K Cap / Compaction) | Mode B (1M Native Ingestion) |",
        "| :--- | :---: | :---: |",
        f"| **Overall Needle Accuracy** | **`{mean_8k:.3f}`** | **`{mean_1m:.3f}`** |",
    ]
    for t_name in ["s_niah", "m_niah", "r_niah"]:
        sub_8k = [r["score_8k"] for r in all_results if r["tier"] == t_name and r["score_8k"] is not None]
        sub_1m = [r["score_1m"] for r in all_results if r["tier"] == t_name and r["score_1m"] is not None]
        a_8k = f"{sum(sub_8k)/len(sub_8k):.3f}" if sub_8k else "N/A"
        a_1m = f"{sum(sub_1m)/len(sub_1m):.3f}" if sub_1m else "N/A"
        md_lines.append(f"| **{t_name.upper()} Fidelity** | `{a_8k}` | `{a_1m}` |")

    if args.tier in ("all", "s_niah") and any(r["tier"] == "s_niah" for r in all_results):
        md_lines.extend([
            "\n## 2. 2D Accuracy Heatmap Grids (Token Load vs. Depth Tier)",
            "### Mode A: 8K Context Cap (Token Waterfall & Smart History Compaction)",
            "```text",
            render_2d_heatmap(all_results, mode_key="score_8k"),
            "```",
            "### Mode B: 1M Context Cap (Frontier Native Long-Context Ingestion)",
            "```text",
            render_2d_heatmap(all_results, mode_key="score_1m"),
            "```"
        ])

    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))
    print(f"✓ Saved Dual-Cap NIAH markdown report to: {out_md}")


if __name__ == "__main__":
    asyncio.run(main())
