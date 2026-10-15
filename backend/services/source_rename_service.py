from dataclasses import dataclass

from sqlalchemy.orm import Session

from database import ChatSession, commit_with_retry
from services.chat_message_service import add_assistant_message
from services.document.title_service import (
    DocumentNotFoundError,
    DocumentTitleConflictError,
    rename_document_title,
)


@dataclass(frozen=True)
class SourceRenameEvent:
    chat_id: str
    doc_id: int
    source_number: int
    previous_title: str
    new_title: str


@dataclass(frozen=True)
class SourceRenameResult:
    response: str
    event: SourceRenameEvent | None


def persist_chat_source_rename(
    db: Session,
    *,
    chat_id: str,
    doc_id: int,
    source_number: int,
    expected_title: str | None,
    previous_title: str,
    new_title: str,
    success_response: str,
    conflict_response: str,
    unchanged_response: str,
) -> SourceRenameResult:
    chat = db.query(ChatSession).filter(ChatSession.id == chat_id).first()
    if not chat:
        raise LookupError("Chat not found.")

    try:
        _, changed = rename_document_title(
            db,
            chat_id,
            doc_id,
            new_title,
            expected_title=expected_title,
        )
    except (DocumentNotFoundError, DocumentTitleConflictError):
        db.rollback()
        add_assistant_message(db, chat_id, conflict_response)
        commit_with_retry(db)
        return SourceRenameResult(response=conflict_response, event=None)

    if not changed:
        add_assistant_message(db, chat_id, unchanged_response)
        commit_with_retry(db)
        return SourceRenameResult(response=unchanged_response, event=None)

    add_assistant_message(db, chat_id, success_response)
    try:
        commit_with_retry(db)
    except Exception:
        db.rollback()
        raise

    return SourceRenameResult(
        response=success_response,
        event=SourceRenameEvent(
            chat_id=chat_id,
            doc_id=doc_id,
            source_number=source_number,
            previous_title=previous_title,
            new_title=new_title,
        ),
    )


def persist_source_rename_reply(db: Session, chat_id: str, response: str) -> str:
    chat = db.query(ChatSession).filter(ChatSession.id == chat_id).first()
    if not chat:
        raise LookupError("Chat not found.")

    add_assistant_message(db, chat_id, response)
    try:
        commit_with_retry(db)
    except Exception:
        db.rollback()
        raise

    return response
