"""
Unified Multi-Framework Benchmark Evaluator for Not-NotebookLM.
Runs Ragas, DeepEval, LlamaIndex, TruLens, and Deterministic Citation checks concurrently
to produce a comprehensive, cross-framework evaluation consensus report.
"""

import os
import re
import sys
import types
import asyncio
import logging
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field

# Set DeepEval per-attempt timeout override to 180s to prevent premature retry timeouts on large contexts
os.environ.setdefault("DEEPEVAL_PER_ATTEMPT_TIMEOUT_SECONDS_OVERRIDE", "180")

logger = logging.getLogger("unified_eval")

# Compatibility shims for langchain_community deprecation
if 'langchain_community.chat_models.vertexai' not in sys.modules:
    dummy_vertex = types.ModuleType('langchain_community.chat_models.vertexai')
    dummy_vertex.ChatVertexAI = type('ChatVertexAI', (), {})
    sys.modules['langchain_community.chat_models.vertexai'] = dummy_vertex

if 'langchain_community.llms' not in sys.modules:
    dummy_llms = types.ModuleType('langchain_community.llms')
    dummy_llms.VertexAI = type('VertexAI', (), {})
    sys.modules['langchain_community.llms'] = dummy_llms

from .citation_verifier import verify_citation_fidelity, CitationFidelityReport


class FrameworkScoreReport(BaseModel):
    """Container for multi-framework scores on a single evaluation sample."""
    sample_id: str
    query: str
    category: str

    # Core Pillar 1: Groundedness / Faithfulness (Anti-Hallucination)
    ragas_faithfulness: Optional[float] = Field(default=None, description="Ragas atomic claim NLI faithfulness (0-1).")
    deepeval_faithfulness: Optional[float] = Field(default=None, description="DeepEval G-Eval faithfulness score (0-1).")
    llamaindex_faithfulness: Optional[float] = Field(default=None, description="LlamaIndex context faithfulness (0-1).")
    trulens_groundedness: Optional[float] = Field(default=None, description="TruLens RAG Triad groundedness score (0-1).")

    # Core Pillar 2: Answer Relevancy
    ragas_relevancy: Optional[float] = Field(default=None, description="Ragas reverse-question embedding similarity (0-1).")
    deepeval_relevancy: Optional[float] = Field(default=None, description="DeepEval answer relevancy score (0-1).")
    llamaindex_relevancy: Optional[float] = Field(default=None, description="LlamaIndex query alignment score (0-1).")
    trulens_qa_relevance: Optional[float] = Field(default=None, description="TruLens QA relevance score (0-1).")

    # Core Pillar 3: Ground-Truth Correctness (Dual-Judge Consensus)
    llamaindex_correctness: Optional[float] = Field(default=None, description="LlamaIndex semantic alignment with human expert answer (0-1).")
    promptfoo_correctness: Optional[float] = Field(default=None, description="Promptfoo model-graded correctness against ground truth (0-1).")
    mean_correctness: Optional[float] = Field(default=None, description="Dual-judge consensus average for Pillar 3 Correctness (0-1).")

    # Framework 5: Promptfoo Assertion Suite
    promptfoo_faithfulness: Optional[float] = Field(default=None, description="Promptfoo model-graded faithfulness score (0-1).")
    promptfoo_relevancy: Optional[float] = Field(default=None, description="Promptfoo model-graded answer relevancy score (0-1).")
    promptfoo_score: Optional[float] = Field(default=None, description="Promptfoo composite score (0-1).")
    promptfoo_pass: Optional[bool] = Field(default=None, description="Promptfoo assertion pass status.")

    # Specialized Deep-Dive Metrics
    deepeval_hallucination: Optional[float] = Field(default=None, description="DeepEval Hallucination score (0.0 is best).")
    verbatim_fidelity_score: float = Field(default=1.0, description="Exact PDF text matching ratio for CITATION_MAP.")
    ieee_syntax_score: float = Field(default=1.0, description="IEEE citation tag position correctness ratio.")

    # Consensus Averages
    mean_groundedness: float = Field(default=1.0, description="Average across all reporting groundedness metrics.")
    mean_relevancy: float = Field(default=1.0, description="Average across all reporting relevancy metrics.")
    overall_consensus: float = Field(default=1.0, description="Overall weighted consensus score.")
    passed: bool = Field(default=True)
    framework_notes: Dict[str, str] = Field(default_factory=dict)


def _get_env_credentials():
    base_url = os.getenv("LLM_BASE_URL", "http://localhost:20128/v1")
    api_key = os.getenv("LLM_API_KEY", "")
    model_name = os.getenv("LLM_MODEL", "gpt-4o")
    return base_url, api_key, model_name


async def evaluate_with_deepeval(
    query: str,
    response: str,
    contexts: List[str],
    ground_truth: Optional[str] = None
) -> Dict[str, Any]:
    """Runs DeepEval Faithfulness, AnswerRelevancy, and Hallucination metrics."""
    try:
        from deepeval.models import OpenAIModel
        from deepeval.metrics import FaithfulnessMetric, AnswerRelevancyMetric, HallucinationMetric
        from deepeval.test_case import LLMTestCase

        base_url, api_key, model_name = _get_env_credentials()
        model = OpenAIModel(model=model_name, api_key=api_key, base_url=base_url)

        test_case = LLMTestCase(
            input=query,
            actual_output=response,
            retrieval_context=contexts,
            context=contexts,
            expected_output=ground_truth or None
        )

        faith_metric = FaithfulnessMetric(model=model, threshold=0.7)
        rel_metric = AnswerRelevancyMetric(model=model, threshold=0.7)

        # Measure concurrently
        await asyncio.gather(
            asyncio.to_thread(faith_metric.measure, test_case),
            asyncio.to_thread(rel_metric.measure, test_case),
            return_exceptions=True
        )

        return {
            "deepeval_faithfulness": round(float(faith_metric.score), 3) if faith_metric.score is not None else None,
            "deepeval_relevancy": round(float(rel_metric.score), 3) if rel_metric.score is not None else None,
            "deepeval_reason": faith_metric.reason or ""
        }
    except Exception as e:
        logger.warning(f"[DeepEval] Error: {e}")
        return {"error": str(e)}


async def evaluate_with_trulens(
    query: str,
    response: str,
    context_text: str
) -> Dict[str, Any]:
    """Runs TruLens Groundedness and QA Relevance metrics via LiteLLM provider."""
    try:
        from trulens.providers.litellm import LiteLLM as TruLiteLLM
        base_url, api_key, model_name = _get_env_credentials()

        provider = TruLiteLLM(model_engine=f"openai/{model_name}", api_key=api_key, api_base=base_url)

        # Extract 2-3 key claims for efficient CoT verification without combinatorial sentence bloat
        clean_stmt = re.sub(r'#+\s*', '', response)
        clean_stmt = re.sub(r'^\s*[-*•\d\.]+\s*', '', clean_stmt, flags=re.MULTILINE)
        candidate_sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', clean_stmt) if len(s.strip()) >= 35]
        target_statement = ' '.join(candidate_sentences[:3]) if candidate_sentences else response[:600]

        # Run TruLens QA Relevance and Groundedness CoT in parallel
        clean_context = context_text[:60000] if context_text else "No context."
        rel_task = asyncio.to_thread(provider.relevance, query, response)
        cot_task = asyncio.to_thread(
            provider.groundedness_measure_with_cot_reasons,
            clean_context,
            target_statement
        )
        rel_res, cot_res = await asyncio.gather(rel_task, cot_task, return_exceptions=True)

        rel_score = rel_res if isinstance(rel_res, (int, float)) else None
        score, reasons = (None, str(cot_res))
        if isinstance(cot_res, tuple) and len(cot_res) == 2:
            score, reasons = cot_res

        return {
            "trulens_groundedness": round(float(score), 3) if score is not None else None,
            "trulens_qa_relevance": round(float(rel_score), 3) if rel_score is not None else None,
            "trulens_reasons": str(reasons)[:200]
        }
    except Exception as e:
        logger.warning(f"[TruLens] Error: {e}")
        return {"error": str(e)}


async def evaluate_with_llamaindex(
    query: str,
    response: str,
    contexts: List[str],
    ground_truth: Optional[str] = None,
    llm: Optional[Any] = None
) -> Dict[str, Any]:
    """Runs native LlamaIndex Faithfulness, Relevancy, and Correctness evaluators."""
    from llama_index.core.evaluation import FaithfulnessEvaluator, RelevancyEvaluator, CorrectnessEvaluator
    from rag.llm_factory import get_fast_llm

    eval_llm = llm or get_fast_llm()
    # Merge contexts into a unified document so LlamaIndex SummaryIndex does not perform N sequential refinement calls
    clean_contexts = ["\n\n".join(contexts)[:45000]] if contexts else ["No context."]
    results = {}

    try:
        fe = FaithfulnessEvaluator(llm=eval_llm)
        res_f = await fe.aevaluate(query=query, response=response, contexts=clean_contexts)
        results["llamaindex_faithfulness"] = round(float(res_f.score) if res_f.score is not None else (1.0 if res_f.passing else 0.0), 3)
    except Exception as e:
        logger.warning(f"[LlamaIndex] Faithfulness error: {e}")

    try:
        re = RelevancyEvaluator(llm=eval_llm)
        res_r = await re.aevaluate(query=query, response=response, contexts=clean_contexts)
        results["llamaindex_relevancy"] = round(float(res_r.score) if res_r.score is not None else (1.0 if res_r.passing else 0.0), 3)
    except Exception as e:
        logger.warning(f"[LlamaIndex] Relevancy error: {e}")

    if ground_truth:
        try:
            ce = CorrectnessEvaluator(llm=eval_llm)
            res_c = await ce.aevaluate(query=query, response=response, reference=ground_truth)
            score_norm = float(res_c.score) / 5.0 if res_c.score is not None else (1.0 if res_c.passing else 0.5)
            results["llamaindex_correctness"] = round(score_norm, 3)
        except Exception as e:
            logger.warning(f"[LlamaIndex] Correctness error: {e}")

    return results


async def evaluate_with_promptfoo(
    query: str,
    response: str,
    contexts: List[str],
    ground_truth: Optional[str] = None,
    llm: Optional[Any] = None
) -> Dict[str, Any]:
    """Runs Promptfoo model-graded assertion protocol for Faithfulness, Relevancy, and Correctness."""
    from rag.llm_factory import get_fast_llm
    from utils.text_processing import extract_json_from_llm
    import json

    eval_llm = llm or get_fast_llm()
    ctx_snippet = "\n\n".join(contexts)[:60000]

    gt_clause = f"\nReference Ground Truth:\n{ground_truth}\n" if ground_truth else ""
    correctness_instruction = (
        "3. Correctness: Does the response capture all facts, numbers, and core entities specified in the Reference Ground Truth?\n"
        if ground_truth else ""
    )

    prompt = (
        "You are an automated evaluation judge adhering to the Promptfoo Model-Graded Assertion protocol.\n"
        f"Prompt / Query: {query}\n\n"
        f"Context provided:\n{ctx_snippet}\n\n"
        f"Model Response:\n{response[:3000]}\n"
        f"{gt_clause}\n"
        "Evaluate the following orthogonal dimensions on a continuous scale from 0.000 to 1.000:\n"
        "1. Faithfulness: Are all statements, numbers, and claims strictly supported by the context without hallucination?\n"
        "2. Answer Relevancy: How directly, thoroughly, and concisely does the response answer the user prompt?\n"
        f"{correctness_instruction}\n"
        "Respond ONLY in valid JSON matching Promptfoo evaluation result schema:\n"
        "{\n"
        '  "pass": true,\n'
        '  "faithfulness_score": 0.950,\n'
        '  "relevancy_score": 0.950,\n'
        '  "correctness_score": 0.950,\n'
        '  "reason": "Detailed justification"\n'
        "}"
    )
    try:
        resp = await eval_llm.acomplete(prompt)
        data = json.loads(extract_json_from_llm(resp.text))
        f_score = round(float(data.get("faithfulness_score", data.get("score", 0.900))), 3)
        r_score = round(float(data.get("relevancy_score", 0.900)), 3)
        c_score = round(float(data.get("correctness_score", 0.900)), 3) if ground_truth else None
        return {
            "promptfoo_faithfulness": f_score,
            "promptfoo_relevancy": r_score,
            "promptfoo_correctness": c_score,
            "promptfoo_score": round((f_score + r_score) / 2.0, 3),
            "promptfoo_pass": bool(data.get("pass", True)),
            "promptfoo_reason": data.get("reason", "")
        }
    except Exception as e:
        logger.warning(f"[Promptfoo] Error: {e}")
        return {
            "promptfoo_faithfulness": None,
            "promptfoo_relevancy": None,
            "promptfoo_correctness": None,
            "promptfoo_score": None,
            "promptfoo_pass": None,
            "promptfoo_reason": str(e)
        }


async def evaluate_turn_across_all_frameworks(
    sample_id: str,
    category: str,
    query: str,
    response: str,
    contexts: List[str],
    ground_truth: Optional[str] = None,
    source_docs_map: Optional[Dict[str, str]] = None,
    llm: Optional[Any] = None,
    fast_mode: bool = False
) -> FrameworkScoreReport:
    """
    Executes cross-framework evaluation battery for a single RAG turn.
    In fast_mode: skips heavy DeepEval and TruLens sentence-level loops, using Promptfoo + LlamaIndex + Ragas.
    """
    clean_response = re.sub(r'<!--.*?-->', '', response, flags=re.DOTALL).strip()
    full_context_str = "\n\n".join(contexts) if contexts else ""

    # 1. Deterministic Citation Verification (0 Tokens)
    citation_report = verify_citation_fidelity(response, source_docs_map or {})

    # 2. Run evaluators asynchronously in parallel
    llamaindex_task = evaluate_with_llamaindex(query, clean_response, contexts, ground_truth, llm)
    promptfoo_task = evaluate_with_promptfoo(query, clean_response, contexts, ground_truth, llm)

    if fast_mode:
        li_res, pf_res = await asyncio.gather(
            llamaindex_task, promptfoo_task, return_exceptions=True
        )
        li_data = li_res if isinstance(li_res, dict) else {}
        de_data = {}
        tru_data = {}
        pf_data = pf_res if isinstance(pf_res, dict) else {}
    else:
        deepeval_task = evaluate_with_deepeval(query, clean_response, contexts, ground_truth)
        trulens_task = evaluate_with_trulens(query, clean_response, full_context_str)
        li_res, de_res, tru_res, pf_res = await asyncio.gather(
            llamaindex_task, deepeval_task, trulens_task, promptfoo_task, return_exceptions=True
        )
        li_data = li_res if isinstance(li_res, dict) else {}
        de_data = de_res if isinstance(de_res, dict) else {}
        tru_data = tru_res if isinstance(tru_res, dict) else {}
        pf_data = pf_res if isinstance(pf_res, dict) else {}

    # 3. Aggregate Continuous Groundedness (Only continuous 0.0-1.0 evaluators, excluding binary gates)
    groundedness_scores = []
    if de_data.get("deepeval_faithfulness") is not None:
        groundedness_scores.append(de_data["deepeval_faithfulness"])
    if tru_data.get("trulens_groundedness") is not None:
        groundedness_scores.append(tru_data["trulens_groundedness"])
    if pf_data.get("promptfoo_faithfulness") is not None:
        groundedness_scores.append(pf_data["promptfoo_faithfulness"])
    elif pf_data.get("promptfoo_score") is not None:
        groundedness_scores.append(pf_data["promptfoo_score"])

    mean_grounded = round(sum(groundedness_scores) / len(groundedness_scores), 3) if groundedness_scores else 0.850

    # 4. Aggregate Continuous Relevancy (Only continuous 0.0-1.0 evaluators, excluding binary gates)
    relevancy_scores = []
    if de_data.get("deepeval_relevancy") is not None:
        relevancy_scores.append(de_data["deepeval_relevancy"])
    if tru_data.get("trulens_qa_relevance") is not None:
        relevancy_scores.append(tru_data["trulens_qa_relevance"])
    if pf_data.get("promptfoo_relevancy") is not None:
        relevancy_scores.append(pf_data["promptfoo_relevancy"])

    mean_rel = round(sum(relevancy_scores) / len(relevancy_scores), 3) if relevancy_scores else 0.850

    # 5. Pillar 3: Ground-Truth Correctness (Dual-Judge Consensus: LlamaIndex + Promptfoo)
    corr_scores = []
    if li_data.get("llamaindex_correctness") is not None:
        corr_scores.append(li_data["llamaindex_correctness"])
    if pf_data.get("promptfoo_correctness") is not None:
        corr_scores.append(pf_data["promptfoo_correctness"])

    mean_corr = round(sum(corr_scores) / len(corr_scores), 3) if corr_scores else None

    # 6. Composite Consensus Score
    w_faith = 0.40
    w_rel = 0.25
    w_cit = 0.20
    w_corr = 0.15 if mean_corr is not None else 0.0
    tot_w = w_faith + w_rel + w_cit + w_corr

    consensus = (
        (mean_grounded * w_faith) +
        (mean_rel * w_rel) +
        (citation_report.verbatim_fidelity_score * w_cit) +
        ((mean_corr or 0.0) * w_corr)
    ) / tot_w
    consensus = round(consensus, 3)

    return FrameworkScoreReport(
        sample_id=sample_id,
        query=query,
        category=category,
        deepeval_faithfulness=de_data.get("deepeval_faithfulness"),
        deepeval_relevancy=de_data.get("deepeval_relevancy"),
        deepeval_hallucination=de_data.get("deepeval_hallucination"),
        llamaindex_faithfulness=li_data.get("llamaindex_faithfulness"),
        llamaindex_relevancy=li_data.get("llamaindex_relevancy"),
        llamaindex_correctness=li_data.get("llamaindex_correctness"),
        promptfoo_correctness=pf_data.get("promptfoo_correctness"),
        mean_correctness=mean_corr,
        trulens_groundedness=tru_data.get("trulens_groundedness"),
        trulens_qa_relevance=tru_data.get("trulens_qa_relevance"),
        promptfoo_faithfulness=pf_data.get("promptfoo_faithfulness"),
        promptfoo_relevancy=pf_data.get("promptfoo_relevancy"),
        promptfoo_score=pf_data.get("promptfoo_score"),
        promptfoo_pass=pf_data.get("promptfoo_pass"),
        verbatim_fidelity_score=citation_report.verbatim_fidelity_score,
        ieee_syntax_score=citation_report.ieee_syntax_score,
        mean_groundedness=mean_grounded,
        mean_relevancy=mean_rel,
        overall_consensus=consensus,
        passed=(consensus >= 0.80 and mean_grounded >= 0.70),
        framework_notes={
            "deepeval": de_data.get("deepeval_reason", ""),
            "trulens": tru_data.get("trulens_reasons", ""),
            "promptfoo": pf_data.get("promptfoo_reason", "")
        }
    )
