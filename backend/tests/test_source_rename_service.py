import os
import sys
from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import services.source_rename_service as source_rename_service
from rag.pipelines.source_rename_pipeline import SourceRenameReply
import routers.messages as messages_router
from routers.messages import persist_rag_response
from database import Base, ChatMessage, ChatSession, Document
from services.source_rename_service import persist_source_rename_reply
from services.document.title_service import (
    DocumentTitleConflictError,
    DocumentTitleValidationError,
    rename_document_title,
)


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    db = session_factory()
    db.add_all([
        ChatSession(id="chat-1", title="Chat 1"),
        ChatSession(id="chat-2", title="Chat 2"),
        Document(id=947, chat_id="chat-1", filename="paper-b.pdf", title="Paper B"),
        Document(id=948, chat_id="chat-2", filename="paper-c.pdf", title="Paper C"),
    ])
    db.commit()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def persist_rename(db, **overrides):
    values = {
        "chat_id": "chat-1",
        "doc_id": 947,
        "source_number": 2,
        "expected_title": "Paper B",
        "previous_title": "Paper B",
        "new_title": "Evaluation Dataset",
        "success_response": "I renamed source 2 to Evaluation Dataset.",
        "conflict_response": "The source changed before I could rename it. No change was made.",
        "unchanged_response": "The source already has that title.",
    }
    values.update(overrides)
    return source_rename_service.persist_chat_source_rename(db, **values)


def test_rename_and_assistant_response_commit_together(db_session):
    result = persist_rename(db_session)

    document = db_session.query(Document).filter(Document.id == 947).one()
    message = db_session.query(ChatMessage).filter(ChatMessage.chat_id == "chat-1").one()
    assert document.title == "Evaluation Dataset"
    assert message.content == result.response
    assert message.variants_json == '["I renamed source 2 to Evaluation Dataset."]'
    assert result.event is not None
    assert result.event.doc_id == 947
    assert result.event.source_number == 2
    assert result.event.previous_title == "Paper B"
    assert result.event.new_title == "Evaluation Dataset"


def test_compare_and_set_conflict_keeps_concurrent_title(db_session):
    document = db_session.query(Document).filter(Document.id == 947).one()
    document.title = "Manual title"
    db_session.commit()

    result = persist_rename(db_session)

    assert result.event is None
    assert result.response == "The source changed before I could rename it. No change was made."
    assert db_session.query(Document).filter(Document.id == 947).one().title == "Manual title"
    assert db_session.query(ChatMessage).filter(ChatMessage.chat_id == "chat-1").count() == 1


def test_compare_and_set_renames_document_with_blank_title(db_session):
    document = db_session.query(Document).filter(Document.id == 947).one()
    document.title = ""
    db_session.commit()

    result = persist_rename(
        db_session,
        expected_title="",
        previous_title="paper b",
    )

    assert result.event is not None
    assert db_session.query(Document).filter(Document.id == 947).one().title == "Evaluation Dataset"


def test_wrong_chat_document_id_cannot_be_renamed(db_session):
    result = persist_rename(db_session, doc_id=948)

    assert result.event is None
    assert db_session.query(Document).filter(Document.id == 948).one().title == "Paper C"
    assert db_session.query(Document).filter(Document.id == 947).one().title == "Paper B"


def test_existing_title_is_a_noop_without_rename_event(db_session):
    result = persist_rename(
        db_session,
        new_title="Paper B",
        unchanged_response="Source 2 already has that title.",
    )

    assert result.event is None
    assert result.response == "Source 2 already has that title."
    assert db_session.query(Document).filter(Document.id == 947).one().title == "Paper B"


def test_clarification_reply_is_saved_without_mutating_a_source(db_session):
    response = "Which source should I rename? No source was changed."

    result = persist_source_rename_reply(db_session, "chat-1", response)

    assert result == response
    assert db_session.query(Document).filter(Document.id == 947).one().title == "Paper B"
    assert db_session.query(ChatMessage).filter(ChatMessage.chat_id == "chat-1").one().content == response


def test_regenerated_rename_reply_is_not_inserted_as_a_new_message(monkeypatch):
    persist_reply = Mock()
    monkeypatch.setattr(messages_router, "persist_source_rename_reply", persist_reply)

    result = persist_rag_response(
        "chat-1",
        SourceRenameReply(response="Regeneration does not repeat source changes."),
        persist_text_response=False,
    )

    assert result == ("Regeneration does not repeat source changes.", None)
    persist_reply.assert_not_called()


def test_commit_failure_rolls_back_title_and_assistant_message(db_session, monkeypatch):
    def fail_commit(_db):
        raise OperationalError("commit", {}, RuntimeError("disk full"))

    monkeypatch.setattr(source_rename_service, "commit_with_retry", fail_commit)

    with pytest.raises(OperationalError):
        persist_rename(db_session)

    db_session.expire_all()
    assert db_session.query(Document).filter(Document.id == 947).one().title == "Paper B"
    assert db_session.query(ChatMessage).filter(ChatMessage.chat_id == "chat-1").count() == 0


@pytest.mark.parametrize("title", ["", "  ", "line\nbreak", "x" * 501])
def test_document_title_validation_rejects_invalid_titles(db_session, title):
    with pytest.raises(DocumentTitleValidationError):
        rename_document_title(db_session, "chat-1", 947, title)


def test_compare_and_set_rejects_stale_expected_title(db_session):
    with pytest.raises(DocumentTitleConflictError):
        rename_document_title(
            db_session,
            "chat-1",
            947,
            "New title",
            expected_title="Old title",
        )
