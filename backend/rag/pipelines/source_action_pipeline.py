import re
import json
import logging
from typing import List

from pydantic import BaseModel, StrictInt

from database import SessionLocal, Document as DBDocument
from rag.prompts import get_source_deletion_prompt
from rag.llm_factory import acall_fast_with_fallback

logger = logging.getLogger("uvicorn.error")


class SourceDeletionDecision(BaseModel):
    remove_doc_ids: List[StrictInt]


async def handle_source_removal_pipeline(
    chat_id: str,
    query: str,
    target_llm,
    report_status
) -> str:
    """Builds a chat-scoped deletion proposal without mutating workspace sources."""
    await report_status("Processing document deletion request...")
    db_s = SessionLocal()
    try:
        current_db_docs = db_s.query(DBDocument).filter(DBDocument.chat_id == chat_id).all()
    finally:
        db_s.close()

    if not current_db_docs:
        return "There are no sources in this workspace to remove. No changes were made."

    doc_summaries = []
    for d in current_db_docs:
        t = d.title or d.filename.replace(".pdf", "")
        snippet = (d.abstract or d.snippet or "")[:200]
        doc_summaries.append(f"- ID: {d.id} | Filename: {d.filename} | Title: {t} | Abstract: {snippet}")

    eval_prompt = get_source_deletion_prompt(query, doc_summaries)
    try:
        eval_resp = await acall_fast_with_fallback(lambda llm: llm.acomplete(eval_prompt))
        clean_json_text = eval_resp.text.strip()
        clean_json_text = re.sub(r'^```(?:json)?\s*', '', clean_json_text, flags=re.I)
        clean_json_text = re.sub(r'\s*```$', '', clean_json_text)
        decision = SourceDeletionDecision.model_validate_json(clean_json_text)
        available_ids = {doc.id for doc in current_db_docs}
        requested_ids = list(dict.fromkeys(decision.remove_doc_ids))
        proposal_ids = [doc_id for doc_id in requested_ids if doc_id in available_ids]

        if not proposal_ids:
            return "I couldn't match your request to any source in this workspace. No changes were made."

        count_label = "source" if len(proposal_ids) == 1 else "sources"
        resp_text = (
            f"I found **{len(proposal_ids)} {count_label}** matching your request. "
            "Nothing has been deleted yet. Review the confirmation dialog to continue."
        )

        action_payload = json.dumps({
            "action": "confirm_delete",
            "chat_id": chat_id,
            "doc_ids": proposal_ids,
        })
        return f"{resp_text}\n\n<!-- SOURCES_ACTION: {action_payload} -->"
    except Exception as eval_err:
        logger.error(f"[Source Deletion Proposal Error]: {eval_err}")
        return "I couldn't prepare a deletion proposal. No sources were changed. Please try again."
