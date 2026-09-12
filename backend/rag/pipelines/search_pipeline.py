import json
import asyncio
import logging
from typing import List, Optional, Callable, Any
from llama_index.core.llms import ChatMessage as LlamaChatMessage, MessageRole
from rag.search import (
    plan_academic_search,
    search_academic_papers_planned,
    judge_and_filter_papers_with_llm,
    get_existing_notebook_sources_signatures,
)
from rag.prompts import get_search_synthesis_prompt
from rag.llm_factory import get_fast_llm, astream_llm_response
from utils.text_processing import clean_doi, normalize_title_str

logger = logging.getLogger("uvicorn.error")

async def handle_academic_search_pipeline(
    chat_id: str,
    query: str,
    formatted_history: List[LlamaChatMessage],
    target_llm,
    report_status,
    on_delta: Optional[Callable[[str], Any]] = None
) -> str:
    """Discovers, filters, audits, and synthesizes scholarly literature with iterative batch replenishment."""
    fast_llm = get_fast_llm() or target_llm

    await report_status("Analyzing query parameters, constraints, and language...")
    plan = await plan_academic_search(query, formatted_history, fast_llm)
    
    target_count = plan.get('target_count', 12)
    user_requested_count = plan.get('user_requested_count')
    is_capped = plan.get('is_capped', False)
    cap_limit = plan.get('cap_limit', 25)
    filter_conflicts = plan.get('filter_conflicts', [])

    # Multiplier: always 2x pool candidates (capped at 50 to protect API latency and memory)
    pool_target = min(max(target_count * 2, 10), 50)
    search_plan = dict(plan)
    search_plan['target_count'] = pool_target

    await report_status("Searching verified global academic repositories...")
    existing_sigs = get_existing_notebook_sources_signatures(chat_id)
    raw_papers = await asyncio.to_thread(search_academic_papers_planned, search_plan, existing_sigs)
    
    if not raw_papers:
        return f"Maaf, tidak ditemukan paper ilmiah yang cocok dengan kriteria pencarian untuk topik: '{query}'."

    # Stage 1 AI Quality Auditor: Strict domain & methodology verification
    await report_status("Auditing paper relevance, domain alignment, and methodology...")
    verified_papers = await judge_and_filter_papers_with_llm(query, raw_papers, target_count, fast_llm)
    if not verified_papers:
        verified_papers = raw_papers[:target_count]

    # Stage 2 Iterative Batch Loop: If noise was discarded and we undershot target_count, fetch Batch 2
    if len(verified_papers) < target_count and len(raw_papers) >= pool_target:
        needed = target_count - len(verified_papers)
        await report_status("Expanding academic search for additional verified studies...")

        # Track all seen papers from Batch 1 to prevent duplicates
        seen_dois_batch = set(existing_sigs.get("dois", set()))
        seen_titles_batch = list(existing_sigs.get("titles", []))
        for p in raw_papers:
            if p.get("doi"):
                seen_dois_batch.add(clean_doi(p["doi"]).lower())
            if p.get("title"):
                t_norm = normalize_title_str(p["title"])
                if t_norm:
                    seen_titles_batch.append((t_norm, set(t_norm.split())))
        batch2_sigs = {"dois": seen_dois_batch, "titles": seen_titles_batch}

        batch2_pool = min(max(needed * 2, 10), 30)
        batch2_plan = dict(plan)
        batch2_plan['target_count'] = batch2_pool

        try:
            batch2_raw = await asyncio.to_thread(search_academic_papers_planned, batch2_plan, batch2_sigs)
            if batch2_raw:
                await report_status("Screening additional literature candidates for quality...")
                batch2_verified = await judge_and_filter_papers_with_llm(query, batch2_raw, needed, fast_llm)
                for bp in batch2_verified:
                    if len(verified_papers) < target_count:
                        verified_papers.append(bp)
        except Exception as batch2_err:
            logger.debug(f"[SearchPipeline Batch 2 Warning]: {batch2_err}")

    papers = verified_papers[:target_count]

    # Format candidate papers for synthesis
    paper_bullet_list = []
    for p in papers[:25]:
        p_authors = ", ".join(p.get("authors", [])[:3]) if p.get("authors") else "Academic Researchers"
        p_venue = p.get("venue", "Academic Publication")
        paper_bullet_list.append(
            f"- **{p.get('title')}** ({p.get('year')}) by {p_authors} in *{p_venue}*\n"
            f"  Abstract: {p.get('snippet', '')[:400]}"
        )
    papers_context = "\n\n".join(paper_bullet_list)

    synthesis_prompt = get_search_synthesis_prompt(
        user_query=query, 
        paper_count=len(papers), 
        papers_context=papers_context,
        user_requested_count=user_requested_count,
        is_capped=is_capped,
        cap_limit=cap_limit,
        filter_conflicts=filter_conflicts
    )

    synth_msgs = [
        LlamaChatMessage(role=MessageRole.SYSTEM, content=synthesis_prompt),
        *(formatted_history if formatted_history else []),
        LlamaChatMessage(role=MessageRole.USER, content=query)
    ]
    
    await report_status("Synthesizing literature review and preparing verified source cards...")
    text_response = await astream_llm_response(target_llm, synth_msgs, on_delta=on_delta)
    
    # Append structured SOURCES_DATA payload for frontend ChatMessageItem interactive import card
    sources_json_str = json.dumps(papers, ensure_ascii=False)
    return f"{text_response}\n\n<!-- SOURCES_DATA: {sources_json_str} -->"
