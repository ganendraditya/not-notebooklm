import json
import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from rag.pipelines import source_rename_pipeline
from rag import engine as rag_engine
from models import ChatSourceSnapshotItem


def make_session(documents):
    session = MagicMock()
    session.query.return_value.filter.return_value.order_by.return_value.all.return_value = documents
    return session


def decision_payload(**overrides):
    payload = {
        "action": "rename",
        "source_number": 2,
        "new_title": "Evaluation Dataset",
        "response": "Please clarify the requested change.",
        "success_response": "I renamed source 2 to Evaluation Dataset.",
        "conflict_response": "The source changed before I could rename it. No change was made.",
        "unchanged_response": "The source already has that title.",
        "stale_response": "I could not verify the source or exact title. No change was made.",
    }
    payload.update(overrides)
    return json.dumps(payload)


def source_docs():
    return [
        SimpleNamespace(id=901, title="Paper A", filename="paper-a.pdf"),
        SimpleNamespace(id=947, title="Paper B", filename="paper-b.pdf"),
    ]


def source_snapshot():
    return [
        ChatSourceSnapshotItem(doc_id=901, title="Paper A", filename="paper-a.pdf"),
        ChatSourceSnapshotItem(doc_id=947, title="Paper B", filename="paper-b.pdf"),
    ]


@pytest.mark.asyncio
async def test_rename_maps_source_number_through_chat_scoped_snapshot(monkeypatch):
    session = make_session(source_docs())
    monkeypatch.setattr(source_rename_pipeline, "SessionLocal", Mock(return_value=session))
    model_call = AsyncMock(return_value=SimpleNamespace(text=decision_payload()))
    monkeypatch.setattr(source_rename_pipeline, "acall_fast_with_fallback", model_call)

    result = await source_rename_pipeline.handle_source_rename_pipeline(
        "chat-1",
        'Rename paper 2 to "Evaluation Dataset"',
        None,
        AsyncMock(),
        source_snapshot(),
    )

    assert isinstance(result, source_rename_pipeline.SourceRenameCommand)
    assert result.chat_id == "chat-1"
    assert result.source_number == 2
    assert result.doc_id == 947
    assert result.expected_title == "Paper B"
    assert result.new_title == "Evaluation Dataset"
    llm = MagicMock()
    llm.acomplete = AsyncMock()
    await model_call.call_args.args[0](llm)
    prompt = llm.acomplete.call_args.args[0]
    assert '"doc_id"' not in prompt
    session.close.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("response_format", ["fenced", "extra_field"])
async def test_rename_accepts_fenced_json_and_ignores_extra_fields(monkeypatch, response_format):
    session = make_session(source_docs())
    monkeypatch.setattr(source_rename_pipeline, "SessionLocal", Mock(return_value=session))
    payload = json.loads(decision_payload(source_number=1))
    if response_format == "fenced":
        response_text = f"```json\n{json.dumps(payload)}\n```"
    else:
        payload["reason"] = "The command named one source and an exact title."
        response_text = json.dumps(payload)
    monkeypatch.setattr(
        source_rename_pipeline,
        "acall_fast_with_fallback",
        AsyncMock(return_value=SimpleNamespace(text=response_text)),
    )

    result = await source_rename_pipeline.handle_source_rename_pipeline(
        "chat-1",
        'Rename source 1 to "Evaluation Dataset"',
        None,
        AsyncMock(),
        source_snapshot(),
    )

    assert isinstance(result, source_rename_pipeline.SourceRenameCommand)
    assert result.doc_id == 901


@pytest.mark.asyncio
@pytest.mark.parametrize("snapshot_title", ["paper a", "paper_a.pdf", "", None])
async def test_rename_accepts_visible_title_variants_when_database_title_is_blank(
    monkeypatch, snapshot_title
):
    session = make_session([SimpleNamespace(id=901, title="", filename="paper_a.pdf")])
    monkeypatch.setattr(source_rename_pipeline, "SessionLocal", Mock(return_value=session))
    monkeypatch.setattr(
        source_rename_pipeline,
        "acall_fast_with_fallback",
        AsyncMock(return_value=SimpleNamespace(text=decision_payload(source_number=1))),
    )

    result = await source_rename_pipeline.handle_source_rename_pipeline(
        "chat-1",
        'Rename source 1 to "Evaluation Dataset"',
        None,
        AsyncMock(),
        [ChatSourceSnapshotItem(doc_id=901, title=snapshot_title, filename="paper_a.pdf")],
    )

    assert isinstance(result, source_rename_pipeline.SourceRenameCommand)
    assert result.expected_title == ""
    assert result.previous_title == "paper a"


@pytest.mark.asyncio
async def test_rename_rejects_a_title_the_user_did_not_write(monkeypatch):
    session = make_session(source_docs())
    monkeypatch.setattr(source_rename_pipeline, "SessionLocal", Mock(return_value=session))
    monkeypatch.setattr(
        source_rename_pipeline,
        "acall_fast_with_fallback",
        AsyncMock(return_value=SimpleNamespace(text=decision_payload(new_title="Suggested Title"))),
    )

    result = await source_rename_pipeline.handle_source_rename_pipeline(
        "chat-1", "Rename paper 2 to a better title", None, AsyncMock(), source_snapshot()
    )

    assert isinstance(result, source_rename_pipeline.SourceRenameReply)
    assert "No change was made" in result.response


@pytest.mark.asyncio
async def test_rename_without_submitted_source_snapshot_fails_closed(monkeypatch):
    session_factory = Mock()
    model_call = AsyncMock()
    monkeypatch.setattr(source_rename_pipeline, "SessionLocal", session_factory)
    monkeypatch.setattr(source_rename_pipeline, "acall_fast_with_fallback", model_call)

    result = await source_rename_pipeline.handle_source_rename_pipeline(
        "chat-1", 'Rename source 1 to "Evaluation Dataset"', None, AsyncMock(), None
    )

    assert isinstance(result, source_rename_pipeline.SourceRenameReply)
    assert "Refresh the chat" in result.response
    assert "no source was changed" in result.response
    session_factory.assert_not_called()
    model_call.assert_not_called()


@pytest.mark.asyncio
async def test_stale_custom_title_is_not_accepted_as_a_filename_alias(monkeypatch):
    session = make_session([SimpleNamespace(id=901, title="Current title", filename="paper_a.pdf")])
    monkeypatch.setattr(source_rename_pipeline, "SessionLocal", Mock(return_value=session))
    model_call = AsyncMock()
    monkeypatch.setattr(source_rename_pipeline, "acall_fast_with_fallback", model_call)

    result = await source_rename_pipeline.handle_source_rename_pipeline(
        "chat-1",
        'Rename source 1 to "Evaluation Dataset"',
        None,
        AsyncMock(),
        [ChatSourceSnapshotItem(doc_id=901, title="paper_a.pdf", filename="paper_a.pdf")],
    )

    assert isinstance(result, source_rename_pipeline.SourceRenameReply)
    assert "source list changed" in result.response
    model_call.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["clarify", "no_action"])
async def test_non_rename_decisions_never_create_a_command(monkeypatch, action):
    session = make_session(source_docs())
    monkeypatch.setattr(source_rename_pipeline, "SessionLocal", Mock(return_value=session))
    monkeypatch.setattr(
        source_rename_pipeline,
        "acall_fast_with_fallback",
        AsyncMock(return_value=SimpleNamespace(text=decision_payload(
            action=action,
            source_number=None,
            new_title=None,
            response="No source was changed.",
            success_response=None,
            conflict_response=None,
            unchanged_response=None,
        ))),
    )

    result = await source_rename_pipeline.handle_source_rename_pipeline(
        "chat-1", "Should I rename paper 2?", None, AsyncMock(), source_snapshot(),
    )

    assert isinstance(result, source_rename_pipeline.SourceRenameReply)
    assert result.response == "No source was changed."


@pytest.mark.asyncio
async def test_non_rename_decision_does_not_require_stale_response(monkeypatch):
    session = make_session(source_docs())
    monkeypatch.setattr(source_rename_pipeline, "SessionLocal", Mock(return_value=session))
    payload = json.loads(
        decision_payload(
            action="clarify",
            source_number=None,
            new_title=None,
            response="Which source should I rename?",
            success_response=None,
            conflict_response=None,
            unchanged_response=None,
        )
    )
    del payload["stale_response"]
    monkeypatch.setattr(
        source_rename_pipeline,
        "acall_fast_with_fallback",
        AsyncMock(return_value=SimpleNamespace(text=json.dumps(payload))),
    )

    result = await source_rename_pipeline.handle_source_rename_pipeline(
        "chat-1", "Rename a source", None, AsyncMock(), source_snapshot()
    )

    assert isinstance(result, source_rename_pipeline.SourceRenameReply)
    assert result.response == "Which source should I rename?"


@pytest.mark.asyncio
async def test_regeneration_of_a_rename_reply_is_blocked_without_model_call(monkeypatch):
    model_call = AsyncMock()
    monkeypatch.setattr(source_rename_pipeline, "acall_fast_with_fallback", model_call)
    report_status = AsyncMock()

    result = await source_rename_pipeline.handle_source_rename_pipeline(
        "chat-1",
        'Rename paper 2 to "Evaluation Dataset"',
        None,
        report_status,
        source_snapshot(),
        execution_allowed=False,
    )

    assert result.response == "Regenerating a response does not repeat source changes. Send the rename command as a new message."
    model_call.assert_not_called()


@pytest.mark.asyncio
async def test_stale_source_snapshot_stops_before_model_call(monkeypatch):
    session = make_session(source_docs())
    monkeypatch.setattr(source_rename_pipeline, "SessionLocal", Mock(return_value=session))
    model_call = AsyncMock()
    monkeypatch.setattr(source_rename_pipeline, "acall_fast_with_fallback", model_call)

    result = await source_rename_pipeline.handle_source_rename_pipeline(
        "chat-1",
        "Rename paper 2 to Evaluation Dataset",
        None,
        AsyncMock(),
        [source_snapshot()[0], ChatSourceSnapshotItem(doc_id=999, title="Paper C", filename="paper-c.pdf")],
    )

    assert "source list changed" in result.response
    assert "no source was changed" in result.response
    model_call.assert_not_called()


@pytest.mark.asyncio
async def test_stale_source_title_snapshot_stops_before_model_call(monkeypatch):
    session = make_session(source_docs())
    monkeypatch.setattr(source_rename_pipeline, "SessionLocal", Mock(return_value=session))
    model_call = AsyncMock()
    monkeypatch.setattr(source_rename_pipeline, "acall_fast_with_fallback", model_call)

    stale_snapshot = source_snapshot()
    stale_snapshot[1] = ChatSourceSnapshotItem(
        doc_id=947,
        title="A different visible title",
        filename="paper-b.pdf",
    )
    result = await source_rename_pipeline.handle_source_rename_pipeline(
        "chat-1",
        'Rename "Paper B" to "Evaluation Dataset"',
        None,
        AsyncMock(),
        stale_snapshot,
    )

    assert "source list changed" in result.response
    model_call.assert_not_called()


@pytest.mark.asyncio
async def test_query_chat_passes_raw_user_query_to_source_rename_pipeline(monkeypatch):
    import database

    session = MagicMock()
    session.query.return_value.filter.return_value.first.return_value = None
    session.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
        SimpleNamespace(filename="paper.pdf")
    ]
    monkeypatch.setattr(database, "SessionLocal", Mock(return_value=session))
    monkeypatch.setattr(
        rag_engine,
        "get_candidate_llm_chain",
        Mock(return_value=[(SimpleNamespace(model="test-model"), "test-model")]),
    )
    monkeypatch.setattr(
        rag_engine,
        "allocate_token_budget",
        Mock(return_value=SimpleNamespace(max_history_tokens=100)),
    )
    monkeypatch.setattr(rag_engine, "acompact_chat_history", AsyncMock(return_value=[]))
    monkeypatch.setattr(
        rag_engine,
        "prepare_query_attachments",
        Mock(return_value="Rename source 1 to the title in the attached paper\nEvaluation Dataset"),
    )
    monkeypatch.setattr(
        rag_engine,
        "acall_fast_with_fallback",
        AsyncMock(return_value="RENAME_SOURCE"),
    )
    rename_handler = AsyncMock(return_value=source_rename_pipeline.SourceRenameReply(response="No change."))
    monkeypatch.setattr(source_rename_pipeline, "handle_source_rename_pipeline", rename_handler)
    raw_query = "Rename source 1 to the title in the attached paper"

    await rag_engine.query_chat(
        "chat-1",
        raw_query,
        chat_history=[
            {
                "role": "user",
                "content": raw_query,
                "attachments": [{"filename": "paper.pdf", "type": "document", "url": "paper.pdf"}],
            }
        ],
        source_snapshot=source_snapshot(),
    )

    assert rename_handler.await_args.args[1] == raw_query
