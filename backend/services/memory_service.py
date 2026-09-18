"""
Memory Service Layer for Long-Term Declarative Research Profile Memory.
Handles atomic, transactional CRUD operations in SQLite with strict token budgeting.
"""

import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from database import ResearchProfile, commit_with_retry, get_utc_now
def _count_text_tokens(text: str) -> int:
    """Helper to count tokens without triggering eager RAG sub-module imports."""
    try:
        from rag.token_budget import count_tokens
        return count_tokens(text)
    except Exception:
        # Fast conservative heuristic fallback: ~4 chars per token
        return max(1, len(text) // 4)

logger = logging.getLogger("uvicorn.error")

MAX_FACT_TOKENS = 50  # Hard ceiling per individual atomic fact
DEFAULT_PROFILE_TOKEN_BUDGET = 250  # Ceiling for total injected profile facts into System Prompt


def get_active_profile_facts(
    db: Session,
    chat_id: str,
    max_tokens: int = DEFAULT_PROFILE_TOKEN_BUDGET
) -> List[ResearchProfile]:
    """
    Retrieves currently active declarative research profile facts for a workspace session.
    Strictly caps cumulative tokens to prevent starving RAG and conversation context headroom.
    """
    if not chat_id:
        return []

    try:
        facts = (
            db.query(ResearchProfile)
            .filter(
                ResearchProfile.chat_id == chat_id,
                ResearchProfile.is_active == True
            )
            .order_by(ResearchProfile.created_at.desc())
            .all()
        )

        # Enforce collective token pool ceiling prioritizing recent directives
        retained = []
        cumulative_tokens = 0
        for f in facts:
            f_tokens = _count_text_tokens(f"{f.category}: {f.fact_text}")
            if cumulative_tokens + f_tokens > max_tokens:
                break
            retained.append(f)
            cumulative_tokens += f_tokens

        retained.reverse()
        return retained
    except Exception as e:
        logger.warning(f"[MemoryService] Error fetching active facts for {chat_id}: {e}")
        return []


def format_profile_for_prompt(facts: List[ResearchProfile]) -> str:
    """
    Renders active declarative facts into a concise, high-density System Prompt block.
    Returns empty string if no active facts are present.
    """
    if not facts:
        return ""

    lines = ["=== ACTIVE RESEARCH PROFILE & USER DIRECTIVES ==="]
    for f in facts:
        cat_label = f.category.capitalize() if f.category else "Directive"
        lines.append(f"- [{cat_label}]: {f.fact_text.strip()}")

    return "\n".join(lines)


def add_profile_fact(
    db: Session,
    chat_id: str,
    fact_text: str,
    category: str = "constraint"
) -> Optional[ResearchProfile]:
    """
    Stores an atomic declarative research fact in SQLite.
    Truncates excessive per-fact verbosity to maintain atomicity.
    """
    if not chat_id or not fact_text:
        return None

    clean_text = str(fact_text).strip().replace("\n", " ")
    if len(clean_text) < 5:
        return None

    # Sanitize length: max 250 characters (~50 tokens) per atomic fact
    if len(clean_text) > 250:
        clean_text = clean_text[:247].strip() + "..."

    clean_category = str(category or "constraint").lower().strip()[:50]

    try:
        new_fact = ResearchProfile(
            chat_id=chat_id,
            category=clean_category,
            fact_text=clean_text,
            is_active=True,
            created_at=get_utc_now(),
            updated_at=get_utc_now()
        )
        db.add(new_fact)
        commit_with_retry(db)
        logger.info(f"[MemoryService] Added active fact [{clean_category}] for {chat_id}: {clean_text[:60]}")
        return new_fact
    except Exception as e:
        logger.error(f"[MemoryService] Error adding fact for {chat_id}: {e}")
        return None


def invalidate_profile_fact(
    db: Session,
    fact_id: int,
    chat_id: str
) -> bool:
    """
    Deactivates a factual constraint when a user revokes or contradicts an earlier rule.
    Maintains historical audit trail rather than hard deleting.
    """
    try:
        fact = (
            db.query(ResearchProfile)
            .filter(
                ResearchProfile.id == fact_id,
                ResearchProfile.chat_id == chat_id
            )
            .first()
        )
        if not fact:
            return False

        fact.is_active = False
        fact.updated_at = get_utc_now()
        commit_with_retry(db)
        logger.info(f"[MemoryService] Inactivated fact ID {fact_id} for {chat_id}: {fact.fact_text[:50]}")
        return True
    except Exception as e:
        logger.error(f"[MemoryService] Error invalidating fact {fact_id}: {e}")
        return False


def delete_profile_fact(
    db: Session,
    fact_id: int,
    chat_id: str
) -> bool:
    """Permanently deletes a profile record on explicit user governance request."""
    try:
        fact = (
            db.query(ResearchProfile)
            .filter(
                ResearchProfile.id == fact_id,
                ResearchProfile.chat_id == chat_id
            )
            .first()
        )
        if not fact:
            return False

        db.delete(fact)
        commit_with_retry(db)
        logger.info(f"[MemoryService] Deleted fact ID {fact_id} for {chat_id}")
        return True
    except Exception as e:
        logger.error(f"[MemoryService] Error deleting fact {fact_id}: {e}")
        return False


async def extract_and_reconcile_research_memory(
    chat_id: str,
    user_message: str,
    db: Session,
    assistant_response: Optional[str] = None
) -> Dict[str, Any]:
    """
    Asynchronously analyzes a conversational turn using Fast LLM to:
    1. Extract newly declared permanent research constraints, objectives, or settings.
    2. Reconcile and invalidate existing facts that are contradicted or revoked by the user.
    Executes database mutations deterministically through the Python service layer.
    """
    if not chat_id or not user_message or len(user_message.strip()) < 8:
        return {"inserted": 0, "invalidated": 0}

    # Fetch currently active profile facts to check for contradictions
    active_facts = get_active_profile_facts(db, chat_id, max_tokens=400)
    facts_context_lines = []
    for f in active_facts:
        facts_context_lines.append(f"- [ID {f.id}] ({f.category}): {f.fact_text}")
    existing_facts_str = "\n".join(facts_context_lines) if facts_context_lines else "None (No active research profile facts stored yet)."

    assistant_context = ""
    if assistant_response and assistant_response.strip():
        assistant_context = f"\nLatest Assistant Response Context (for reference):\n\"{assistant_response.strip()[:500]}\"\n"

    prompt = (
        "You are an expert Research Profile Memory Extractor and Contradiction Reconciler.\n"
        "Your task is to analyze the user's latest message in an academic research assistant workspace.\n\n"
        f"Currently Active Research Profile Facts:\n{existing_facts_str}\n\n"
        f"Latest User Message:\n\"{user_message.strip()}\"\n"
        f"{assistant_context}\n"
        "Task Guidelines:\n"
        "1. INSERT NEW FACTS:\n"
        "   - Detect permanent research constraints, exclusion criteria, hardware setups, target venues, deadlines, or methodologies stated by the user.\n"
        "   - Must be permanent directives (e.g. 'Never recommend closed-source datasets', 'Our GPU is RTX 3060 12GB', 'Targeting IEEE TMI').\n"
        "   - DO NOT extract ephemeral questions, greetings, or specific paper questions.\n"
        "   - Each fact must be atomic, precise, and under 25 words.\n"
        "   - Valid categories: 'constraint', 'objective', 'methodology', 'hardware', 'venue'.\n\n"
        "2. RECONCILE / INVALIDATE CONTRADICTIONS:\n"
        "   - If the user explicitly cancels, updates, or contradicts an existing fact (e.g. earlier fact forbade arXiv, but user now says 'it is okay to use arXiv now'), output the target fact ID in 'invalidate_ids'.\n"
        "   - If no existing facts are contradicted, keep 'invalidate_ids' empty.\n\n"
        "Respond ONLY with valid JSON schema:\n"
        "{\n"
        "  \"insert_facts\": [\n"
        "    {\"category\": \"constraint\", \"fact_text\": \"Concise directive text\"}\n"
        "  ],\n"
        "  \"invalidate_ids\": [1, 2],\n"
        "  \"reason\": \"Brief justification\"\n"
        "}"
    )

    try:
        from rag.llm_factory import acall_fast_with_fallback
        from utils.text_processing import extract_json_from_llm
        import json

        raw_resp = await acall_fast_with_fallback(lambda llm: llm.acomplete(prompt))
        clean_json_str = extract_json_from_llm(raw_resp.text if hasattr(raw_resp, "text") else str(raw_resp))
        data = json.loads(clean_json_str)

        if not isinstance(data, dict):
            return {"inserted": 0, "invalidated": 0, "error": "Invalid JSON response structure"}

        raw_inv = data.get("invalidate_ids")
        if isinstance(raw_inv, (int, str)):
            invalidate_ids = [raw_inv]
        elif isinstance(raw_inv, list):
            invalidate_ids = raw_inv
        else:
            invalidate_ids = []

        invalidated_count = 0
        for fid in invalidate_ids:
            if fid is None:
                continue
            try:
                fid_int = int(fid)
                if invalidate_profile_fact(db, fid_int, chat_id):
                    invalidated_count += 1
            except Exception as inv_err:
                logger.debug(f"[MemoryService] Error invalidating ID {fid}: {inv_err}")

        raw_ins = data.get("insert_facts")
        if isinstance(raw_ins, dict):
            insert_facts = [raw_ins]
        elif isinstance(raw_ins, list):
            insert_facts = raw_ins
        else:
            insert_facts = []

        inserted_count = 0
        for item in insert_facts:
            if not isinstance(item, dict):
                continue
            f_text = (item.get("fact_text") or "").strip()
            f_cat = (item.get("category") or "constraint").strip().lower() or "constraint"
            if f_text and len(f_text) >= 5:
                # Normalized equality and intra-batch deduplication
                is_duplicate = any(
                    existing.fact_text and f_text.lower() == existing.fact_text.strip().lower()
                    for existing in active_facts
                    if existing.is_active
                )
                if not is_duplicate:
                    new_fact = add_profile_fact(db, chat_id, f_text, f_cat)
                    if new_fact:
                        inserted_count += 1
                        active_facts.append(new_fact)

        return {
            "inserted": inserted_count,
            "invalidated": invalidated_count,
            "reason": str(data.get("reason") or "")
        }
    except Exception as e:
        logger.warning(f"[MemoryService] Background reconciliation failed: {e}")
        return {"inserted": 0, "invalidated": 0, "error": str(e)}

