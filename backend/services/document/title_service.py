import unicodedata

from sqlalchemy.orm import Session

from database import Document

MAX_DOCUMENT_TITLE_LENGTH = 500
_UNSET = object()


class DocumentTitleValidationError(ValueError):
    pass


class DocumentNotFoundError(LookupError):
    pass


class DocumentTitleConflictError(RuntimeError):
    pass


def normalize_document_title(title: str) -> str:
    if not isinstance(title, str):
        raise DocumentTitleValidationError("Document title must be text.")

    clean_title = title.strip()
    if not clean_title:
        raise DocumentTitleValidationError("Document title cannot be empty.")
    if len(clean_title) > MAX_DOCUMENT_TITLE_LENGTH:
        raise DocumentTitleValidationError(
            f"Document title cannot exceed {MAX_DOCUMENT_TITLE_LENGTH} characters."
        )
    if any(unicodedata.category(char) in {"Cc", "Cs"} for char in clean_title):
        raise DocumentTitleValidationError("Document title contains unsupported control characters.")

    return clean_title


def rename_document_title(
    db: Session,
    chat_id: str,
    doc_id: int,
    title: str,
    *,
    expected_title: str | None | object = _UNSET,
) -> tuple[Document, bool]:
    clean_title = normalize_document_title(title)
    scoped_query = db.query(Document).filter(
        Document.id == doc_id,
        Document.chat_id == chat_id,
    )
    query = scoped_query
    if expected_title is not _UNSET:
        if expected_title is None:
            query = query.filter(Document.title.is_(None))
        else:
            query = query.filter(Document.title == expected_title)

    document = query.first()
    if document is None:
        exists_in_chat = scoped_query.with_entities(Document.id).first()
        if exists_in_chat:
            raise DocumentTitleConflictError("Document title changed while the rename was being prepared.")
        raise DocumentNotFoundError("Document not found in this chat.")

    if document.title == clean_title:
        return document, False

    if expected_title is not _UNSET:
        update_query = scoped_query
        if expected_title is None:
            update_query = update_query.filter(Document.title.is_(None))
        else:
            update_query = update_query.filter(Document.title == expected_title)
        updated_count = update_query.update({Document.title: clean_title}, synchronize_session=False)
        if updated_count != 1:
            raise DocumentTitleConflictError("Document title changed while the rename was being prepared.")
        db.expire_all()
        document = scoped_query.first()
        if document is None:
            raise DocumentNotFoundError("Document not found in this chat.")
    else:
        document.title = clean_title

    return document, True
