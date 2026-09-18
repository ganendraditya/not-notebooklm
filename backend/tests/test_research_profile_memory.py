import pytest
import asyncio
from unittest.mock import patch, AsyncMock
from fastapi import HTTPException
from database import SessionLocal, ChatSession, ResearchProfile, commit_with_retry
from services.memory_service import (
    add_profile_fact,
    get_active_profile_facts,
    format_profile_for_prompt,
    invalidate_profile_fact,
    delete_profile_fact,
    extract_and_reconcile_research_memory
)
from routers.chats import update_chat_research_fact
import models


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


@pytest.mark.asyncio
async def test_reconciliation_null_handling_and_resilience(test_db):
    chat = ChatSession(title="Null Handling Mock Chat")
    test_db.add(chat)
    commit_with_retry(test_db)

    try:
        # LLM returns nulls on invalidate_ids, insert_facts, fact_text, reason
        mock_llm_resp = (
            '{"insert_facts": [null, {"fact_text": null}, {"category": null, "fact_text": "Valid research constraint"}], '
            '"invalidate_ids": null, "reason": null}'
        )

        with patch("rag.llm_factory.acall_fast_with_fallback", new=AsyncMock(return_value=mock_llm_resp)):
            res = await extract_and_reconcile_research_memory(
                chat_id=chat.id,
                user_message="Set research constraint to valid text.",
                db=test_db
            )
            assert res["inserted"] == 1
            assert res["invalidated"] == 0
            assert res["reason"] == ""

        active = get_active_profile_facts(test_db, chat.id)
        assert len(active) == 1
        assert active[0].fact_text == "Valid research constraint"
        assert active[0].category == "constraint"
    finally:
        test_db.query(ResearchProfile).filter(ResearchProfile.chat_id == chat.id).delete()
        test_db.delete(chat)
        commit_with_retry(test_db)


@pytest.mark.asyncio
async def test_deduplication_exact_match_and_intra_batch(test_db):
    chat = ChatSession(title="Deduplication Test Chat")
    test_db.add(chat)
    commit_with_retry(test_db)

    try:
        # 1. Existing rule containing substring
        f1 = add_profile_fact(test_db, chat.id, "Do not use PyTorch in this project.", "constraint")
        assert f1 is not None

        # 2. LLM emits "Use PyTorch" (which is a substring of f1, but should NOT be dropped)
        # AND emits "Use PyTorch" twice in the same batch (intra-batch duplicate)
        mock_llm_resp = (
            '{"insert_facts": ['
            '  {"category": "methodology", "fact_text": "Use PyTorch in this project."},'
            '  {"category": "methodology", "fact_text": "Use PyTorch in this project."}'
            '], "invalidate_ids": []}'
        )

        with patch("rag.llm_factory.acall_fast_with_fallback", new=AsyncMock(return_value=mock_llm_resp)):
            res = await extract_and_reconcile_research_memory(
                chat_id=chat.id,
                user_message="Please switch to PyTorch now.",
                db=test_db
            )
            # Only one inserted, the second duplicate in the same batch is skipped
            assert res["inserted"] == 1

        active = get_active_profile_facts(test_db, chat.id)
        assert len(active) == 2
        texts = [f.fact_text for f in active]
        assert "Do not use PyTorch in this project." in texts
        assert "Use PyTorch in this project." in texts
    finally:
        test_db.query(ResearchProfile).filter(ResearchProfile.chat_id == chat.id).delete()
        test_db.delete(chat)
        commit_with_retry(test_db)


@pytest.mark.asyncio
async def test_assistant_response_context_in_prompt(test_db):
    chat = ChatSession(title="Prompt Context Test Chat")
    test_db.add(chat)
    commit_with_retry(test_db)

    try:
        captured_prompt = None

        async def fake_acall(llm_callable):
            nonlocal captured_prompt
            class DummyLLM:
                async def acomplete(self, prompt):
                    nonlocal captured_prompt
                    captured_prompt = prompt
                    class DummyResp:
                        text = '{"insert_facts": [], "invalidate_ids": []}'
                    return DummyResp()
            return await llm_callable(DummyLLM())

        with patch("rag.llm_factory.acall_fast_with_fallback", side_effect=fake_acall):
            await extract_and_reconcile_research_memory(
                chat_id=chat.id,
                user_message="Yes, let us focus only on PubMed articles.",
                db=test_db,
                assistant_response="Would you like to restrict literature to PubMed?"
            )

        assert captured_prompt is not None
        assert "Latest Assistant Response Context (for reference):" in captured_prompt
        assert "Would you like to restrict literature to PubMed?" in captured_prompt
    finally:
        test_db.query(ResearchProfile).filter(ResearchProfile.chat_id == chat.id).delete()
        test_db.delete(chat)
        commit_with_retry(test_db)


def test_patch_fact_endpoint_validation(test_db):
    chat = ChatSession(title="Patch Validation Chat")
    test_db.add(chat)
    commit_with_retry(test_db)

    try:
        fact = add_profile_fact(test_db, chat.id, "Target venue is IEEE TMI", "venue")
        assert fact is not None

        # 1. Update with text < 5 characters should raise HTTPException(400)
        req_too_short = models.UpdateFactRequest(fact_text="12")
        with pytest.raises(HTTPException) as exc_info:
            update_chat_research_fact(chat.id, fact.id, req_too_short, test_db)
        assert exc_info.value.status_code == 400
        assert "at least 5 characters" in exc_info.value.detail

        # 2. Update with valid text succeeds
        req_valid = models.UpdateFactRequest(fact_text="Target venue is MICCAI 2026")
        res = update_chat_research_fact(chat.id, fact.id, req_valid, test_db)
        assert res["fact_text"] == "Target venue is MICCAI 2026"
    finally:
        test_db.query(ResearchProfile).filter(ResearchProfile.chat_id == chat.id).delete()
        test_db.delete(chat)
        commit_with_retry(test_db)


@pytest.mark.asyncio
async def test_regenerate_message_stream_memory_flow(test_db):
    from database import ChatMessage
    from routers.messages import regenerate_message_stream

    chat = ChatSession(title="Regenerate Test Chat")
    test_db.add(chat)
    commit_with_retry(test_db)

    try:
        m1 = ChatMessage(chat_id=chat.id, role="user", content="Our target hardware is RTX 4090 24GB")
        m2 = ChatMessage(chat_id=chat.id, role="assistant", content="Acknowledged.")
        test_db.add_all([m1, m2])
        commit_with_retry(test_db)

        req = models.RegenerateMessageRequest(message_index=1)

        extracted_turn = None
        async def mock_extract(cid, user_msg, db, resp_text):
            nonlocal extracted_turn
            extracted_turn = (cid, user_msg, resp_text)
            return {"inserted": 1, "invalidated": 0}

        with patch("routers.messages.rag.query_chat", new=AsyncMock(return_value="New assistant reply")), \
             patch("services.memory_service.extract_and_reconcile_research_memory", side_effect=mock_extract):
            response = await regenerate_message_stream(chat.id, req, test_db)
            async for _ in response.body_iterator:
                pass
            await asyncio.sleep(0.05)

        assert extracted_turn is not None
        assert extracted_turn[0] == chat.id
        assert extracted_turn[1] == "Our target hardware is RTX 4090 24GB"
        assert extracted_turn[2] == "New assistant reply"
    finally:
        test_db.query(ChatMessage).filter(ChatMessage.chat_id == chat.id).delete()
        test_db.delete(chat)
        commit_with_retry(test_db)


@pytest.mark.asyncio
async def test_edit_message_stream_memory_flow(test_db):
    from database import ChatMessage
    from routers.messages import edit_message_stream

    chat = ChatSession(title="Edit Test Chat")
    test_db.add(chat)
    commit_with_retry(test_db)

    try:
        m1 = ChatMessage(chat_id=chat.id, role="user", content="Initial prompt")
        m2 = ChatMessage(chat_id=chat.id, role="assistant", content="Initial reply")
        test_db.add_all([m1, m2])
        commit_with_retry(test_db)

        req = models.EditMessageRequest(message="New edited user directive: only open source", message_index=0)

        extracted_turn = None
        async def mock_extract(cid, user_msg, db, resp_text):
            nonlocal extracted_turn
            extracted_turn = (cid, user_msg, resp_text)
            return {"inserted": 1, "invalidated": 0}

        with patch("routers.messages.rag.query_chat", new=AsyncMock(return_value="Edited reply")), \
             patch("services.memory_service.extract_and_reconcile_research_memory", side_effect=mock_extract):
            response = await edit_message_stream(chat.id, req, test_db)
            async for _ in response.body_iterator:
                pass
            await asyncio.sleep(0.05)

        assert extracted_turn is not None
        assert extracted_turn[0] == chat.id
        assert extracted_turn[1] == "New edited user directive: only open source"
        assert extracted_turn[2] == "Edited reply"
    finally:
        test_db.query(ChatMessage).filter(ChatMessage.chat_id == chat.id).delete()
        test_db.delete(chat)
        commit_with_retry(test_db)
