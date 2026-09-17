import os
import pytest
from rag.token_budget import (
    count_tokens,
    count_messages_tokens,
    get_model_context_window,
    allocate_token_budget,
    pack_text_into_token_budget,
    TokenBudget,
)
from llama_index.core.llms import ChatMessage, MessageRole


def test_get_model_context_window_known_models():
    """Verify registry resolves correct limits for major frontier and open-source models."""
    assert get_model_context_window("gemini-1.5-pro") == 1_000_000
    assert get_model_context_window("gemini-2.0-flash") == 1_000_000
    assert get_model_context_window("claude-3-5-sonnet-20241022") == 200_000
    assert get_model_context_window("gpt-4o") == 128_000
    assert get_model_context_window("gpt-4o-mini") == 128_000
    assert get_model_context_window("llama-3.1-70b-instruct") == 128_000
    assert get_model_context_window("llama-3-8b") == 8_192
    assert get_model_context_window("qwen2.5-72b-instruct") == 128_000
    assert get_model_context_window("deepseek-chat") == 64_000
    assert get_model_context_window("mistral-small-latest") == 32_768


def test_get_model_context_window_env_override(monkeypatch):
    """Verify LLM_CONTEXT_WINDOW environment variable overrides any model name."""
    monkeypatch.setenv("LLM_CONTEXT_WINDOW", "65536")
    assert get_model_context_window("llama-3-8b") == 65_536


def test_count_tokens():
    """Verify token counting returns positive, accurate counts for text."""
    sample_text = "The quick brown fox jumps over the lazy dog."
    cnt = count_tokens(sample_text)
    assert 8 <= cnt <= 12

    empty_cnt = count_tokens("")
    assert empty_cnt == 0

    none_cnt = count_tokens(None)
    assert none_cnt == 0


def test_count_messages_tokens():
    """Verify structured chat message token counting."""
    messages = [
        ChatMessage(role=MessageRole.SYSTEM, content="You are a helpful assistant."),
        ChatMessage(role=MessageRole.USER, content="Hello, tell me about RAG."),
    ]
    cnt = count_messages_tokens(messages)
    assert cnt > 10

    dict_messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, tell me about RAG."},
    ]
    cnt_dict = count_messages_tokens(dict_messages)
    assert cnt_dict > 10


def test_allocate_token_budget_8k_model():
    """Verify Priority Waterfall allocation for compact 8k models."""
    budget = allocate_token_budget(
        model_name="llama-3-8b",
        system_prompt="System instructions for citation grounding.",
        user_query="Compare transformer architectures.",
    )
    assert budget.max_context == 8_192
    assert budget.reserved_output == 2_048
    assert budget.safety_padding == 150
    # Total input prompt budget must leave room for output
    assert budget.total_prompt_budget == 8_192 - 2_048 - 150
    # Sum of allocations cannot exceed available pool
    assert budget.max_rag_tokens <= budget.available_pool
    assert budget.max_rag_tokens + budget.max_history_tokens <= budget.available_pool


def test_allocate_token_budget_large_model():
    """Verify Priority Waterfall allocation for large context models (Stanford Lost in Middle bound)."""
    budget = allocate_token_budget(
        model_name="gemini-1.5-pro",
        system_prompt="System instructions.",
        user_query="Summarize findings.",
    )
    assert budget.max_context == 1_000_000
    assert budget.reserved_output == 4_096
    # In large context, RAG is deliberately capped at high-density bounds (6,000 tokens)
    # to prevent Stanford 'Lost in the Middle' retrieval degradation
    assert budget.max_rag_tokens == 6_000
    assert budget.max_history_tokens > 10_000


def test_pack_text_into_token_budget():
    """Verify packing text truncates gracefully without exceeding token cap."""
    long_text = "Sentence one. " * 500
    budget_tokens = 50
    packed = pack_text_into_token_budget(long_text, budget_tokens=budget_tokens)
    
    assert count_tokens(packed) <= budget_tokens + 2  # within boundary
    assert len(packed) < len(long_text)


@pytest.mark.asyncio
async def test_workspace_pipeline_respects_token_budget():
    """Verify handle_workspace_analysis_pipeline executes with dynamic budget packing."""
    from unittest.mock import AsyncMock, MagicMock
    from rag.pipelines.workspace_pipeline import handle_workspace_analysis_pipeline
    from database import SessionLocal, Document as DBDocument

    dummy_chat = "test_budget_ws_chat"
    db = SessionLocal()
    try:
        doc = DBDocument(
            chat_id=dummy_chat,
            filename="massive_paper.pdf",
            title="Massive Long Research Paper on Transformers",
            year=2024,
            abstract="Abstract: " + ("Detailed findings. " * 300),
            is_oa=True
        )
        db.add(doc)
        db.commit()
    finally:
        db.close()

    mock_llm = MagicMock()
    mock_llm.model = "llama-3-8b"
    mock_response = MagicMock()
    mock_response.message.content = "Analysis completed [1]."
    mock_llm.achat = AsyncMock(return_value=mock_response)

    captured_status = []
    async def mock_status(text):
        captured_status.append(text)

    try:
        res = await handle_workspace_analysis_pipeline(
            chat_id=dummy_chat,
            query="Summarize paper methodology",
            local_docs=["massive_paper.pdf"],
            formatted_history=[],
            target_llm=mock_llm,
            report_status=mock_status
        )
        assert "Analysis completed [1]." in res
        # Ensure LLM achat was called with chat messages
        assert mock_llm.achat.called
        call_args = mock_llm.achat.call_args[0][0]
        # Total prompt tokens sent to LLM must not exceed prompt budget
        prompt_tokens = count_messages_tokens(call_args, model_name="llama-3-8b")
        assert prompt_tokens < 8_192 - 2_048  # strictly under limit with output reserve
    finally:
        db = SessionLocal()
        db.query(DBDocument).filter(DBDocument.chat_id == dummy_chat).delete()
        db.commit()
        db.close()


def test_compact_chat_history_under_budget():
    """Verify history remains unchanged when comfortably within token budget."""
    from rag.token_budget import compact_chat_history
    messages = [
        ChatMessage(role=MessageRole.USER, content="Hello"),
        ChatMessage(role=MessageRole.ASSISTANT, content="Hi, how can I assist your research?"),
    ]
    result = compact_chat_history(messages, max_history_tokens=1000)
    assert len(result) == 2
    assert result[0].content == "Hello"


def test_compact_chat_history_over_budget_synthesizes_summary_bridge():
    """Verify smart compaction synthesizes a rolling summary bridge before pruning old turns."""
    from rag.token_budget import compact_chat_history
    # Build 10 turns of conversation
    messages = []
    for i in range(10):
        messages.append(ChatMessage(role=MessageRole.USER, content=f"Research inquiry {i}: Explain methodology aspect {i} in detail with data."))
        messages.append(ChatMessage(role=MessageRole.ASSISTANT, content=f"Response {i}: Here is the extensive scientific analysis for aspect {i}."))

    # Restrict budget so only the last ~2-3 turns can fit
    compacted = compact_chat_history(messages, max_history_tokens=180)
    assert len(compacted) < len(messages)
    # First message MUST be the synthetic context summary bridge
    assert compacted[0].role == MessageRole.SYSTEM
    assert "[Context Summary of Earlier Conversation:" in compacted[0].content
    # The latest user turn must be preserved
    assert compacted[-1].role == MessageRole.ASSISTANT
    assert "Response 9" in compacted[-1].content
    # Total tokens of compacted messages must satisfy the max_history_tokens constraint
    total_compacted_tokens = count_messages_tokens(compacted)
    assert total_compacted_tokens <= 180 + 30  # within margin of safety


@pytest.mark.asyncio
async def test_acompact_chat_history_with_custom_summarizer():
    """Verify async compaction invokes custom summarizer when available."""
    from rag.token_budget import acompact_chat_history

    messages = [
        ChatMessage(role=MessageRole.USER, content="Explain dataset parameters 1" * 30),
        ChatMessage(role=MessageRole.ASSISTANT, content="Parameters explained 1" * 30),
        ChatMessage(role=MessageRole.USER, content="Explain dataset parameters 2" * 30),
        ChatMessage(role=MessageRole.ASSISTANT, content="Parameters explained 2" * 30),
        ChatMessage(role=MessageRole.USER, content="Final active question: What is the learning rate?"),
    ]

    async def mock_summarizer(evicted_text):
        return "Earlier turns investigated dataset parameters."

    compacted = await acompact_chat_history(
        messages=messages,
        max_history_tokens=80,
        summarizer_func=mock_summarizer
    )

    assert compacted[0].role == MessageRole.SYSTEM
    assert "Earlier turns investigated dataset parameters." in compacted[0].content
    assert "What is the learning rate?" in compacted[-1].content


@pytest.mark.asyncio
async def test_query_chat_end_to_end_8k_compaction(monkeypatch):
    """Verify end-to-end query_chat on an 8k model compacts 20-turn history into safe prompt boundaries."""
    from unittest.mock import AsyncMock, MagicMock
    from rag.engine import query_chat

    mock_llm = MagicMock()
    mock_llm.model = "llama-3-8b"
    mock_response = MagicMock()
    mock_response.message.content = "Final response under safe 8k budget."
    mock_llm.achat = AsyncMock(return_value=mock_response)
    mock_llm.astream_chat = AsyncMock()

    # Mock candidate chain to return our 8k mock LLM
    monkeypatch.setattr("rag.engine.get_candidate_llm_chain", lambda: [(mock_llm, "Llama-3-8B")])
    # Mock fast LLM fallback for intent classification
    monkeypatch.setattr("rag.engine.acall_fast_with_fallback", AsyncMock(return_value="GENERAL_CHAT"))

    # Generate 20 turns of heavy history (~6,000 tokens)
    heavy_history = []
    for i in range(20):
        heavy_history.append({"role": "user", "content": f"User query {i}: " + ("Explain deeper details of ML. " * 25)})
        heavy_history.append({"role": "assistant", "content": f"Assistant reply {i}: " + ("Comprehensive explanation provided. " * 25)})

    collected_deltas = []
    def on_delta(d):
        collected_deltas.append(d)

    result = await query_chat(
        chat_id="test_8k_chat_session",
        query="What is the conclusion from our previous discussion?",
        chat_history=heavy_history,
        delta_callback=on_delta,
    )

    assert "Final response" in result
    # Verify the chat call was made
    assert mock_llm.achat.called or mock_llm.astream_chat.called
    call_args = (mock_llm.achat.call_args or mock_llm.astream_chat.call_args)[0][0]
    
    # Prompt tokens passed to the 8k LLM must stay strictly below 8k minus output reserve
    total_tokens = count_messages_tokens(call_args, model_name="llama-3-8b")
    assert total_tokens < 8_192 - 2_048
    # The first message in the history portion must be the synthetic context summary bridge
    bridge_found = any("[Context Summary of Earlier Conversation:" in str(getattr(m, "content", "")) for m in call_args)
    assert bridge_found



