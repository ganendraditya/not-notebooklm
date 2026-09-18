"""
Memory Service Layer for Long-Term Declarative Research Profile Memory.
Handles atomic, transactional CRUD operations in SQLite with strict token budgeting.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import text

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
            .order_by(ResearchProfile.created_at.asc())
            .all()
        )

        # Enforce collective token pool ceiling
        retained = []
        cumulative_tokens = 0
        for f in facts:
            f_tokens = _count_text_tokens(f"{f.category}: {f.fact_text}")
            if cumulative_tokens + f_tokens > max_tokens:
                break
            retained.append(f)
            cumulative_tokens += f_tokens

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
