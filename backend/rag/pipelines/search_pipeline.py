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

logger = logging.getLogger("uvicorn.error")

async def handle_academic_search_pipeline(
    chat_id: str,
    query: str,
    formatted_history: List[LlamaChatMessage],
    target_llm,
    report_status,
    on_delta: Optional[Callable[[str], Any]] = None
) -> str:
    """Discovers, filters, audits, and synthesizes scholarly literature."""
    from rag.engine import get_fast_llm
    fast_llm = get_fast_llm() or target_llm

    await report_status("Planning academic query parameters & search terms...")
    plan = await plan_academic_search(query, formatted_history, fast_llm)
    
    target_count = plan.get('target_count', 15)
    # Request 2x candidate pool so AI Judge has plenty of candidates to audit & filter
    search_plan = dict(plan)
    search_plan['target_count'] = max(target_count * 2, 20)

    await report_status("Searching verified academic repositories for candidate papers...")
    existing_sigs = get_existing_notebook_sources_signatures(chat_id)
    raw_papers = await asyncio.to_thread(search_academic_papers_planned, search_plan, existing_sigs)
    
    if not raw_papers:
        return f"Maaf, tidak ditemukan paper ilmiah yang cocok dengan kriteria pencarian untuk topik: '{query}'."

    # Fast AI Relevance Judge: Evaluate paper summaries, audit domain relevance, and discard any noise
    await report_status("AI Auditor evaluating paper relevance & filtering noise...")
    papers = await judge_and_filter_papers_with_llm(query, raw_papers, target_count, fast_llm)
    if not papers:
        papers = raw_papers[:target_count]

    await report_status("Synthesizing research landscape and structuring sources...")
    
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

    synthesis_prompt = get_search_synthesis_prompt(query, len(papers), papers_context)

    synth_msgs = [
        LlamaChatMessage(role=MessageRole.SYSTEM, content=synthesis_prompt),
        *(formatted_history if formatted_history else []),
        LlamaChatMessage(role=MessageRole.USER, content=query)
    ]
    
    await report_status("Synthesizing literature review and citation insights...")
    from rag.engine import astream_llm_response
    text_response = await astream_llm_response(target_llm, synth_msgs, on_delta=on_delta)
    
    # Append structured SOURCES_DATA payload for frontend ChatMessageItem interactive import card
    sources_json_str = json.dumps(papers, ensure_ascii=False)
    return f"{text_response}\n\n<!-- SOURCES_DATA: {sources_json_str} -->"
