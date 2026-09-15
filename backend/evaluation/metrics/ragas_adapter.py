import os
import sys
import logging
from typing import List, Dict, Any, Optional
from datasets import Dataset

logger = logging.getLogger("uvicorn.error")

# Ensure Ragas compatibility shims
import evaluation

try:
    from ragas.metrics import faithfulness
    from ragas import evaluate
    from langchain_openai import ChatOpenAI
    RAGAS_AVAILABLE = True
except Exception as e:
    logger.warning(f"[RagasAdapter] Failed to initialize Ragas: {e}")
    RAGAS_AVAILABLE = False


def evaluate_batch_with_ragas(
    eval_records: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Evaluates a batch of RAG turns using official Ragas metrics and the project's configured LLM gateway.
    """
    if not RAGAS_AVAILABLE or not eval_records:
        return {
            "ragas_faithfulness": 0.000,
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
    api_key = os.getenv("LLM_API_KEY", "")
    model = os.getenv("LLM_MODEL", "gpt-4o")

    try:
        ragas_llm = ChatOpenAI(
            base_url=base_url,
            api_key=api_key,
            model=model,
            temperature=0.0
        )

        dataset = Dataset.from_dict(dataset_dict)
        results = evaluate(
            dataset=dataset,
            metrics=[faithfulness],
            llm=ragas_llm,
            raise_exceptions=False
        )

        scores = {}
        if hasattr(results, "to_pandas"):
            df = results.to_pandas()
            if "faithfulness" in df.columns:
                valid_vals = df["faithfulness"].dropna()
                scores["ragas_faithfulness"] = round(float(valid_vals.mean()), 3) if not valid_vals.empty else 0.000
                scores["case_scores"] = [round(float(v), 3) if not (v != v) else 0.000 for v in df["faithfulness"]]
        else:
            scores["ragas_faithfulness"] = round(float(results.get("faithfulness", 0.000)), 3)

        scores["available"] = True
        return scores
    except Exception as e:
        logger.warning(f"[RagasAdapter] Execution failed: {e}")
        return {
            "ragas_faithfulness": 0.000,
            "error": str(e),
            "available": False
        }
