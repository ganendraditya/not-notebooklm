"""
Unit and integration tests for Issue #47:
Context-Aware Sliding Window for Fast-LLM Intent Classification.
"""

import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from unittest.mock import MagicMock, AsyncMock
from llama_index.core.llms import ChatMessage as LlamaChatMessage, MessageRole
from rag.intent import format_micro_dialogue_trace, classify_user_intent
from rag.llm_factory import get_fast_llm


def test_format_micro_dialogue_trace_empty():
    assert format_micro_dialogue_trace(None) == ""
    assert format_micro_dialogue_trace([]) == ""


def test_format_micro_dialogue_trace_dict_and_stripping():
    history = [
        {"role": "user", "content": "Bandingkan Paper [1] dan [2]."},
        {
            "role": "assistant", 
            "content": "Paper [1] menggunakan metode A sedangkan Paper [2] menggunakan B. <!-- CITATION_MAP: {\"1\": [\"quote\"]} --> <!-- SOURCES_DATA: [{\"title\": \"doc\"}] -->"
        },
    ]
    trace = format_micro_dialogue_trace(history, max_turns=2, max_chars=150)
    assert "User: Bandingkan Paper [1] dan [2]." in trace
    assert "Assistant: Paper [1] menggunakan metode A sedangkan Paper [2] menggunakan B." in trace
    assert "<!-- CITATION_MAP" not in trace
    assert "<!-- SOURCES_DATA" not in trace


def test_format_micro_dialogue_trace_truncation():
    long_text = "A" * 300
    history = [
        {"role": "user", "content": "Pertanyaan"},
        {"role": "assistant", "content": long_text}
    ]
    trace = format_micro_dialogue_trace(history, max_turns=1, max_chars=50)
    # Must be truncated to 50 chars + ellipsis
    assert len("A" * 50 + "...") <= 55
    assert "A" * 50 + "..." in trace
    assert "A" * 100 not in trace


def test_format_micro_dialogue_trace_llama_chat_messages_windowing():
    # 6 messages (3 full turns)
    messages = [
        LlamaChatMessage(role=MessageRole.USER, content="Turn 1 User"),
        LlamaChatMessage(role=MessageRole.ASSISTANT, content="Turn 1 Assistant"),
        LlamaChatMessage(role=MessageRole.USER, content="Turn 2 User"),
        LlamaChatMessage(role=MessageRole.ASSISTANT, content="Turn 2 Assistant"),
        LlamaChatMessage(role=MessageRole.USER, content="Turn 3 User"),
        LlamaChatMessage(role=MessageRole.ASSISTANT, content="Turn 3 Assistant"),
    ]
    # max_turns=2 should capture only Turn 2 and Turn 3 (last 4 messages)
    trace = format_micro_dialogue_trace(messages, max_turns=2, max_chars=150)
    assert "Turn 1 User" not in trace
    assert "Turn 2 User" in trace
    assert "Turn 2 Assistant" in trace
    assert "Turn 3 User" in trace
    assert "Turn 3 Assistant" in trace


@pytest.mark.asyncio
async def test_classify_user_intent_injects_dialogue_trace_into_prompt():
    mock_llm = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = "ANALYZE_WORKSPACE"
    mock_llm.acomplete = AsyncMock(return_value=mock_resp)

    history = [
        {"role": "user", "content": "Bandingkan metode kedua paper ini."},
        {"role": "assistant", "content": "Paper 1 memakai CNN, paper 2 memakai Vision Transformer."}
    ]

    res = await classify_user_intent(
        user_query="Lalu bagaimana dengan limitasinya?",
        has_docs=True,
        doc_count=2,
        llm=mock_llm,
        chat_history=history
    )
    assert res == "ANALYZE_WORKSPACE"
    prompt_sent = mock_llm.acomplete.call_args[0][0]
    assert "Recent Dialogue Context (Last turns):" in prompt_sent
    assert "User: Bandingkan metode kedua paper ini." in prompt_sent
    assert "Paper 1 memakai CNN" in prompt_sent
    assert "User Prompt: \"Lalu bagaimana dengan limitasinya?\"" in prompt_sent


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_fast_llm_anaphora_intent_resolution():
    """Live test verifying that Fast LLM correctly resolves follow-up queries using conversation context."""
    llm = get_fast_llm()
    history = [
        {"role": "user", "content": "Bandingkan hasil akurasi model A dan model B pada paper ini."},
        {"role": "assistant", "content": "Model A memperoleh akurasi 94% sedangkan Model B hanya 81% karena adanya masalah vanishing gradient."}
    ]

    # 1. Follow-up query that implies document context -> must be ANALYZE_WORKSPACE
    res_followup = await classify_user_intent(
        user_query="Kenapa bisa begitu?",
        has_docs=True,
        doc_count=2,
        llm=llm,
        chat_history=history
    )
    assert res_followup == "ANALYZE_WORKSPACE"

    # 2. Another follow-up continuation
    res_continue = await classify_user_intent(
        user_query="Lanjutkan",
        has_docs=True,
        doc_count=2,
        llm=llm,
        chat_history=history
    )
    assert res_continue == "ANALYZE_WORKSPACE"

    # 3. Genuine small talk even with history -> must still be GENERAL_CHAT
    res_chat = await classify_user_intent(
        user_query="Terima kasih banyak atas penjelasannya!",
        has_docs=True,
        doc_count=2,
        llm=llm,
        chat_history=history
    )
    assert res_chat == "GENERAL_CHAT"

    # 4. Search query even with history -> must still be SEARCH_NEW
    res_search = await classify_user_intent(
        user_query="Tolong carikan 10 paper baru tentang diffusion models",
        has_docs=True,
        doc_count=2,
        llm=llm,
        chat_history=history
    )
    assert res_search == "SEARCH_NEW"
