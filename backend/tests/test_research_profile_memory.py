import pytest
import asyncio
from unittest.mock import patch, AsyncMock
from database import SessionLocal, ChatSession, ResearchProfile, commit_with_retry
from services.memory_service import (
    add_profile_fact,
    get_active_profile_facts,
    format_profile_for_prompt,
    invalidate_profile_fact,
    delete_profile_fact,
    extract_and_reconcile_research_memory
)


@pytest.fixture
def test_db():
    db = SessionLocal()
    yield db
    db.close()


def test_research_profile_crud_operations(test_db):
    chat = ChatSession(title="Memory Test Chat")
    test_db.add(chat)
    commit_with_retry(test_db)

    try:
        # 1. Create atomic facts
        f1 = add_profile_fact(test_db, chat.id, "Exclude papers older than 5 years and exclude arXiv.", "constraint")
        f2 = add_profile_fact(test_db, chat.id, "Local cluster has 1 GPU RTX 3060 (12GB VRAM).", "hardware")
        f3 = add_profile_fact(test_db, chat.id, "Target venue is IEEE Transactions on Medical Imaging.", "venue")

        assert f1 is not None and f2 is not None and f3 is not None
        active = get_active_profile_facts(test_db, chat.id)
        assert len(active) == 3

        # 2. Verify prompt formatting with budget
        prompt_block = format_profile_for_prompt(active)
        assert "=== ACTIVE RESEARCH PROFILE & USER DIRECTIVES ===" in prompt_block
        assert "[Constraint]: Exclude papers older than 5 years" in prompt_block
        assert "[Hardware]: Local cluster has 1 GPU RTX 3060" in prompt_block

        # 3. Test Invalidation (Reconciliation)
        ok = invalidate_profile_fact(test_db, f1.id, chat.id)
        assert ok is True
        active_after = get_active_profile_facts(test_db, chat.id)
        assert len(active_after) == 2
        still_has_f1 = any(f.id == f1.id for f in active_after)
        assert not still_has_f1

        # 4. Test Hard Deletion
        del_ok = delete_profile_fact(test_db, f2.id, chat.id)
        assert del_ok is True
        assert len(get_active_profile_facts(test_db, chat.id)) == 1

    finally:
        test_db.query(ResearchProfile).filter(ResearchProfile.chat_id == chat.id).delete()
        test_db.delete(chat)
        commit_with_retry(test_db)


@pytest.mark.asyncio
async def test_reconciliation_workflow_with_mock_llm(test_db):
    chat = ChatSession(title="Reconciliation Mock Chat")
    test_db.add(chat)
    commit_with_retry(test_db)

    try:
        # Existing rule: exclude arxiv
        f1 = add_profile_fact(test_db, chat.id, "Do not use arXiv papers.", "constraint")
        assert f1.is_active is True

        # User says: "Actually arXiv is allowed now" -> Mock LLM emits invalidation on f1
        mock_llm_resp = '{"insert_facts": [{"category": "constraint", "fact_text": "arXiv papers are permitted"}], "invalidate_ids": [' + str(f1.id) + '], "reason": "User revoked arXiv restriction"}'

        with patch("rag.llm_factory.acall_fast_with_fallback", new=AsyncMock(return_value=mock_llm_resp)):
            res = await extract_and_reconcile_research_memory(
                chat_id=chat.id,
                user_message="Actually arXiv papers are permitted now.",
                db=test_db
            )
            assert res["inserted"] == 1
            assert res["invalidated"] == 1

        active = get_active_profile_facts(test_db, chat.id)
        assert len(active) == 1
        assert "permitted" in active[0].fact_text
        # Old fact is now inactive
        old_fact = test_db.query(ResearchProfile).filter(ResearchProfile.id == f1.id).first()
        assert old_fact.is_active is False

    finally:
        test_db.query(ResearchProfile).filter(ResearchProfile.chat_id == chat.id).delete()
        test_db.delete(chat)
        commit_with_retry(test_db)
