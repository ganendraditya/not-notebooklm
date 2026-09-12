import json
import logging
from typing import List, Optional
from llama_index.core.llms import LLM

from utils.text_processing import extract_json_from_llm

logger = logging.getLogger("uvicorn.error")

async def judge_and_filter_papers_with_llm(
    query: str,
    candidates: List[dict],
    target_count: int,
    llm: Optional[LLM] = None
) -> List[dict]:
    """
    Stage 3.5: Multi-Criteria Academic Rubric Judge & Relevance Auditor.
    Evaluates candidate papers retrieved from registries across 3 strict rubrics:
    1. Core Domain Match (prevents keyword-overlap false positives)
    2. Problem Statement & Methodology Alignment
    3. Academic Substance (discards general blog/noise/unrelated fields)
    """
    if not candidates:
        return []
    
    if llm is None:
        return candidates[:target_count]

    try:
        eval_items = []
        for idx, c in enumerate(candidates):
            title = c.get("title", "").strip()
            snippet = c.get("snippet", "").strip()[:400]
            venue = c.get("venue", "").strip()
            year = c.get("year", "")
            eval_items.append(f"[{idx}] Title: {title} ({year})\nVenue: {venue}\nAbstract/Snippet: {snippet}")

        eval_context = "\n\n".join(eval_items)

        judge_prompt = (
            "You are a Senior Academic Peer Reviewer and Scientific Literature Selection Judge.\n"
            "Your objective: Strictly evaluate each retrieved research candidate against the user's research query using a multi-criteria rubric.\n\n"
            f"User Research Query:\n\"{query}\"\n\n"
            f"Candidate Papers to Audit ({len(candidates)} candidates):\n{eval_context}\n\n"
            "ACADEMIC EVALUATION RUBRIC:\n"
            "1. CORE DOMAIN ALIGNMENT:\n"
            "   - Accept papers that directly investigate the specific target domain.\n"
            "   - Strictly reject keyword coincidence (e.g. if query is 'AI in road crack detection', REJECT medical crack, dental crack, building wall crack, train rail track).\n"
            "2. METHODOLOGICAL & PROBLEM MATCH:\n"
            "   - The paper must address the research questions or methods requested (e.g. classification, prediction, empirical experiment, survey).\n"
            "3. RANKING & QUOTA FULFILLMENT:\n"
            f"   - Target requested: {target_count} papers.\n"
            f"   - Evaluate all candidates. Include ALL candidate indices that genuinely match the research domain, ranked from highest scientific relevance to lowest.\n"
            f"   - If there are at least {target_count} genuine matching candidates that pass the rubric, return at least {target_count} indices.\n"
            f"   - DO NOT arbitrarily stop or truncate to fewer than {target_count} if valid relevant candidates are available.\n"
            "   - ONLY exclude candidate indices if they are genuine noise, off-topic, or keyword coincidences.\n\n"
            "OUTPUT FORMAT:\n"
            "Return ONLY a JSON list of integer indices of accepted papers in ranked order (best matches first).\n"
            "Example format: [2, 0, 4, 1]"
        )

        resp = await llm.acomplete(judge_prompt)
        raw_out = extract_json_from_llm(resp.text)
        valid_indices = json.loads(raw_out)

        if isinstance(valid_indices, list):
            filtered_papers = []
            seen_indices = set()
            for idx in valid_indices:
                if isinstance(idx, int) and 0 <= idx < len(candidates) and idx not in seen_indices:
                    seen_indices.add(idx)
                    filtered_papers.append(candidates[idx])
            
            if filtered_papers:
                return filtered_papers[:target_count]
    except Exception as e:
        logger.debug(f"[AI Judge Auditor Warning]: {e} -> fallback to candidates")

    return candidates[:target_count]
