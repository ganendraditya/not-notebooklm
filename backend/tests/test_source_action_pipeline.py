import asyncio
import json
import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from rag.pipelines import source_action_pipeline


def make_session(documents):
    session = MagicMock()
    session.query.return_value.filter.return_value.all.return_value = documents
    return session


@pytest.mark.asyncio
async def test_source_removal_returns_chat_scoped_proposal_without_deleting(monkeypatch):
    documents = [
        SimpleNamespace(id=7, title="Paper A", filename="paper-a.pdf", abstract="", snippet=""),
        SimpleNamespace(id=8, title="Paper B", filename="paper-b.pdf", abstract="", snippet=""),
    ]
    session = make_session(documents)
    monkeypatch.setattr(source_action_pipeline, "SessionLocal", Mock(return_value=session))
    monkeypatch.setattr(
        source_action_pipeline,
        "acall_fast_with_fallback",
        AsyncMock(return_value=SimpleNamespace(text='{"remove_doc_ids": [7, 7, 999]}')),
    )

    response = await source_action_pipeline.handle_source_removal_pipeline(
        "chat-1", "remove Paper A", None, AsyncMock()
    )

    action_json = response.split("<!-- SOURCES_ACTION: ", 1)[1].split(" -->", 1)[0]
    assert json.loads(action_json) == {
        "action": "confirm_delete",
        "chat_id": "chat-1",
        "doc_ids": [7],
    }
    assert "Nothing has been deleted yet" in response
    session.close.assert_called_once()


@pytest.mark.asyncio
async def test_source_removal_rejects_non_integer_ids_without_proposal(monkeypatch):
    session = make_session([
        SimpleNamespace(id=7, title="Paper A", filename="paper-a.pdf", abstract="", snippet="")
    ])
    monkeypatch.setattr(source_action_pipeline, "SessionLocal", Mock(return_value=session))
    monkeypatch.setattr(
        source_action_pipeline,
        "acall_fast_with_fallback",
        AsyncMock(return_value=SimpleNamespace(text='{"remove_doc_ids": ["7"]}')),
    )

    response = await source_action_pipeline.handle_source_removal_pipeline(
        "chat-1", "remove Paper A", None, AsyncMock()
    )

    assert "No sources were changed" in response
    assert "SOURCES_ACTION" not in response
