import os
import sys
import logging
from typing import List, Dict, Any, Optional
from datasets import Dataset

logger = logging.getLogger("uvicorn.error")

# Ensure Ragas compatibility shims
import evaluation

try:
    from ragas.metrics import faithfulness, answer_relevancy
    from ragas import evaluate
    from langchain_openai import ChatOpenAI
    from langchain_google_genai import GoogleGenerativeAIEmbeddings
    RAGAS_AVAILABLE = True
except Exception as e:
    logger.warning(f"[RagasAdapter] Failed to initialize Ragas: {e}")
    RAGAS_AVAILABLE = False


def evaluate_batch_with_ragas(
    eval_records: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Evaluates a batch of RAG turns using official Ragas metrics (Faithfulness & Answer Relevancy)
    powered by the project's configured LLM gateway and Google GenAI embeddings.
    """
    if not RAGAS_AVAILABLE or not eval_records:
        return {
            "ragas_faithfulness": 0.000,
            "ragas_answer_relevancy": 0.000,
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
    gemini_key = os.getenv("GEMINI_API_KEY")

    try:
        ragas_llm = ChatOpenAI(
            base_url=base_url,
            api_key=api_key,
            model=model,
            temperature=0.0
        )

        embeddings = None
        if gemini_key:
            try:
                embeddings = GoogleGenerativeAIEmbeddings(
                    model="models/gemini-embedding-001",
                    google_api_key=gemini_key
                )
            except Exception as e:
                logger.warning(f"[RagasAdapter] Could not load Google embeddings: {e}")

        active_metrics = [faithfulness]
        if embeddings is not None:
            active_metrics.append(answer_relevancy)

        dataset = Dataset.from_dict(dataset_dict)
        results = evaluate(
            dataset=dataset,
            metrics=active_metrics,
            llm=ragas_llm,
            embeddings=embeddings,
            raise_exceptions=False
        )

        scores = {}
        if hasattr(results, "to_pandas"):
            df = results.to_pandas()
            if "faithfulness" in df.columns:
                valid_faith = df["faithfulness"].dropna()
                scores["ragas_faithfulness"] = round(float(valid_faith.mean()), 3) if not valid_faith.empty else 0.000
                scores["case_faithfulness"] = [round(float(v), 3) if not (v != v) else 0.000 for v in df["faithfulness"]]
            if "answer_relevancy" in df.columns:
                valid_rel = df["answer_relevancy"].dropna()
                scores["ragas_answer_relevancy"] = round(float(valid_rel.mean()), 3) if not valid_rel.empty else 0.000
                scores["case_relevancy"] = [round(float(v), 3) if not (v != v) else 0.000 for v in df["answer_relevancy"]]
        else:
            scores["ragas_faithfulness"] = round(float(results.get("faithfulness", 0.000)), 3)
            scores["ragas_answer_relevancy"] = round(float(results.get("answer_relevancy", 0.000)), 3)

        scores["available"] = True
        return scores
    except Exception as e:
        logger.warning(f"[RagasAdapter] Execution failed: {e}")
        return {
            "ragas_faithfulness": 0.000,
            "ragas_answer_relevancy": 0.000,
            "error": str(e),
            "available": False
        }
