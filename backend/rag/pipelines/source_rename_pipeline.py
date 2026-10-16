import logging
import re
import unicodedata
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, model_validator

from database import Document as DBDocument, SessionLocal
from models import ChatSourceSnapshotItem
from rag.llm_factory import acall_fast_with_fallback
from rag.prompts import get_source_rename_prompt

logger = logging.getLogger("uvicorn.error")
MAX_SOURCE_RENAME_TITLE_LENGTH = 500


class SourceRenameDecision(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    action: Literal["rename", "clarify", "no_action", "blocked"]
    source_number: StrictInt | None = None
    new_title: StrictStr | None = Field(default=None, max_length=MAX_SOURCE_RENAME_TITLE_LENGTH)
    response: StrictStr = Field(min_length=1, max_length=1200)
    success_response: StrictStr | None = Field(default=None, max_length=1200)
    conflict_response: StrictStr | None = Field(default=None, max_length=1200)
    unchanged_response: StrictStr | None = Field(default=None, max_length=1200)
    stale_response: StrictStr = Field(
        default="I couldn't verify the source or exact title. No change was made.",
        min_length=1,
        max_length=1200,
    )

    @model_validator(mode="after")
    def validate_action_fields(self):
        if self.action == "rename":
            if self.source_number is None or self.source_number <= 0 or not self.new_title:
                raise ValueError("Rename decisions require one positive source number and a title.")
            if not all((self.success_response, self.conflict_response, self.unchanged_response)):
                raise ValueError("Rename decisions require responses for success, conflict, and no-op outcomes.")
        elif self.source_number is not None or self.new_title is not None:
            raise ValueError("Non-rename decisions cannot include a source or title.")
        return self


class SourceRenameCommand(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    chat_id: str
    source_number: int
    doc_id: int
    expected_title: str | None
    previous_title: str
    new_title: str
    success_response: str
    conflict_response: str
    unchanged_response: str


class SourceRenameReply(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    response: str


def _safe_response(response: str | None, fallback: str) -> str:
    if not response:
        return fallback
    clean = re.sub(r"<!--[\s\S]*?(?:-->|$)", "", response).strip()
    return clean[:1200] or fallback


def _display_source_title(document: DBDocument) -> str:
    return document.title or document.filename.replace(".pdf", "").replace("_", " ").strip()


def _snapshot_title_matches(document: DBDocument, snapshot_title: str | None) -> bool:
    if document.title:
        return snapshot_title == document.title
    return snapshot_title in {None, "", _display_source_title(document), document.filename}


def _parse_source_rename_decision(response_text: str) -> SourceRenameDecision:
    clean_response = response_text.strip()
    if clean_response.startswith("```"):
        clean_response = re.sub(r"^```(?:json)?\s*", "", clean_response, flags=re.IGNORECASE)
        clean_response = re.sub(r"\s*```$", "", clean_response)
    return SourceRenameDecision.model_validate_json(clean_response)


def _load_source_snapshot(
    chat_id: str,
    source_snapshot: list[ChatSourceSnapshotItem] | None,
):
    if source_snapshot is None:
        return None

    db = SessionLocal()
    try:
        documents = (
            db.query(DBDocument)
            .filter(DBDocument.chat_id == chat_id)
            .order_by(DBDocument.id.asc())
            .all()
        )
        documents_by_id = {document.id: document for document in documents}

        source_ids = [source.doc_id for source in source_snapshot]
        if any(source_id <= 0 for source_id in source_ids):
            return None
        if len(source_ids) != len(set(source_ids)):
            return None
        selected_documents = [documents_by_id.get(source_id) for source_id in source_ids]
        if any(document is None for document in selected_documents):
            return None
        if any(
            not _snapshot_title_matches(document, source.title)
            or document.filename != source.filename
            for document, source in zip(selected_documents, source_snapshot)
        ):
            return None

        return [
            {
                "source_number": source_number,
                "doc_id": document.id,
                "expected_title": document.title,
                "title": _display_source_title(document),
                "filename": document.filename,
            }
            for source_number, document in enumerate(selected_documents, start=1)
        ]
    finally:
        db.close()


def _title_is_literal_in_query(title: str, query: str) -> bool:
    normalized_title = unicodedata.normalize("NFC", title.strip())
    normalized_query = unicodedata.normalize("NFC", query)
    return bool(normalized_title) and normalized_title in normalized_query


async def handle_source_rename_pipeline(
    chat_id: str,
    query: str,
    target_llm,
    report_status,
    source_snapshot: list[ChatSourceSnapshotItem] | None = None,
    *,
    execution_allowed: bool = True,
) -> SourceRenameReply | SourceRenameCommand:
    await report_status("Checking the source rename request...")
    if not execution_allowed:
        return SourceRenameReply(
            response="Regenerating a response does not repeat source changes. Send the rename command as a new message."
        )

    if source_snapshot is None:
        return SourceRenameReply(
            response="I couldn't verify the original rename request. Refresh the chat and send the command again; no source was changed."
        )

    source_catalog = _load_source_snapshot(chat_id, source_snapshot)
    if source_catalog is None:
        return SourceRenameReply(
            response="The source list changed while this request was waiting. Send the rename command again from the current chat; no source was changed."
        )
    if not source_catalog:
        return SourceRenameReply(response="There are no sources in this chat to rename. No changes were made.")

    prompt_sources = [
        {
            "source_number": source["source_number"],
            "title": source["title"],
            "filename": source["filename"],
        }
        for source in source_catalog
    ]
    prompt = get_source_rename_prompt(query, prompt_sources)

    try:
        response = await acall_fast_with_fallback(lambda llm: llm.acomplete(prompt))
        decision = _parse_source_rename_decision(response.text)
    except Exception as error:
        logger.info("[Source Rename Parser] No rename action was produced: %s", error)
        return SourceRenameReply(
            response="I couldn't verify the rename request. No source was changed. Please state one source and its exact new title."
        )

    if decision.action != "rename":
        return SourceRenameReply(response=_safe_response(decision.response, "No source was changed."))

    source_number = decision.source_number
    if source_number is None or source_number > len(source_catalog):
        return SourceRenameReply(
            response=_safe_response(
                decision.stale_response,
                "I couldn't match that source to the current chat. No source was changed.",
            )
        )

    new_title = decision.new_title.strip() if decision.new_title else ""
    if (
        not new_title
        or len(new_title) > MAX_SOURCE_RENAME_TITLE_LENGTH
        or any(unicodedata.category(char) in {"Cc", "Cs"} for char in new_title)
        or not _title_is_literal_in_query(new_title, query)
    ):
        return SourceRenameReply(
            response=_safe_response(
                decision.stale_response,
                "Please repeat the exact title you want to use. No source was changed.",
            )
        )

    source = source_catalog[source_number - 1]
    return SourceRenameCommand(
        chat_id=chat_id,
        source_number=source_number,
        doc_id=source["doc_id"],
        expected_title=source["expected_title"],
        previous_title=source["title"],
        new_title=new_title,
        success_response=_safe_response(decision.success_response, "The source title was updated."),
        conflict_response=_safe_response(decision.conflict_response, "The source changed before it could be renamed. No changes were made."),
        unchanged_response=_safe_response(decision.unchanged_response, "The source already has that title."),
    )
