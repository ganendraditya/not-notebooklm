import os
import re
import sys
import logging
from typing import List, Dict, Any, Optional
from datasets import Dataset

logger = logging.getLogger("uvicorn.error")

# Ensure Ragas compatibility shims & telemetry disabled
import evaluation
os.environ["RAGAS_DO_NOT_TRACK"] = "true"

try:
    from ragas.metrics import faithfulness, answer_relevancy, context_recall, context_precision
    from ragas import aevaluate
    from langchain_openai import ChatOpenAI
    from langchain_google_genai import GoogleGenerativeAIEmbeddings
    RAGAS_AVAILABLE = True
except Exception as e:
    logger.warning(f"[RagasAdapter] Failed to initialize Ragas: {e}")
    RAGAS_AVAILABLE = False


class CleanChatOpenAI(ChatOpenAI):
    """ChatOpenAI wrapper that automatically strips markdown code fences so Ragas parser never fails."""
    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        res = await super()._agenerate(messages, stop=stop, run_manager=run_manager, **kwargs)
        for gen in res.generations:
            t = gen.text.strip()
            if t.startswith("```"):
                t = re.sub(r"^```(?:json)?\s*", "", t)
                t = re.sub(r"\s*```$", "", t)
                gen.text = t.strip()
                if hasattr(gen, "message") and hasattr(gen.message, "content"):
                    gen.message.content = t.strip()
        return res


async def evaluate_batch_with_ragas(
    eval_records: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Evaluates a batch of RAG turns asynchronously using official Ragas metrics across all dimensions:
    - Generation: Faithfulness, Answer Relevancy
    """
    if not RAGAS_AVAILABLE or not eval_records:
        return {
            "ragas_faithfulness": 0.000,
            "ragas_answer_relevancy": 0.000,
            "ragas_context_recall": 0.000,
            "ragas_context_precision": 0.000,
            "available": False
        }

    dataset_dict = {
        "user_input": [r["question"] for r in eval_records],
        "response": [r["answer"] for r in eval_records],
        "retrieved_contexts": [r["contexts"] for r in eval_records],
    }
    if any(r.get("ground_truth") for r in eval_records):
        dataset_dict["reference"] = [r.get("ground_truth", "") for r in eval_records]

    base_url = os.getenv("LLM_BASE_URL", "http://localhost:20128/v1")
    api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or "dummy-key"
    model = os.getenv("LLM_EVAL_MODEL") or os.getenv("LLM_FAST_MODEL") or "ag/gemini-3.1-pro-low"
    gemini_key = os.getenv("GEMINI_API_KEY")

    try:
        ragas_llm = CleanChatOpenAI(
            base_url=base_url,
            api_key=api_key,
            model=model,
            temperature=0.0
        )

        active_metrics = [faithfulness]
        from ragas.run_config import RunConfig
        dataset = Dataset.from_dict(dataset_dict)
        results = await aevaluate(
            dataset=dataset,
            metrics=active_metrics,
            llm=ragas_llm,
            run_config=RunConfig(timeout=180, max_retries=2, max_workers=4),
            raise_exceptions=False
        )

        scores = {}
        if hasattr(results, "to_pandas"):
            df = results.to_pandas()
            for col, key in [
                ("faithfulness", "ragas_faithfulness"),
                ("answer_relevancy", "ragas_answer_relevancy"),
                ("context_recall", "ragas_context_recall"),
                ("context_precision", "ragas_context_precision")
            ]:
                if col in df.columns:
                    valid_vals = df[col].dropna()
                    scores[key] = round(float(valid_vals.mean()), 3) if not valid_vals.empty else 0.000
                    scores[f"case_{col}"] = [round(float(v), 3) if not (v != v) else 0.000 for v in df[col]]
        else:
            for k in ["faithfulness", "answer_relevancy", "context_recall", "context_precision"]:
                scores[f"ragas_{k}"] = round(float(results.get(k, 0.000)), 3)

        scores["available"] = True
        return scores
    except Exception as e:
        logger.warning(f"[RagasAdapter] Execution failed: {e}")
        return {
            "ragas_faithfulness": 0.000,
            "ragas_answer_relevancy": 0.000,
            "ragas_context_recall": 0.000,
            "ragas_context_precision": 0.000,
            "error": str(e),
            "available": False
        }
