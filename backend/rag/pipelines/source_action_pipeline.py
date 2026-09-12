import re
import json
import logging
from typing import List
from database import SessionLocal, Document as DBDocument
from rag.prompts import get_source_deletion_prompt
from rag.llm_factory import get_fast_llm
from services.storage_service import delete_multiple_documents

logger = logging.getLogger("uvicorn.error")

async def handle_source_removal_pipeline(
    chat_id: str,
    query: str,
    target_llm,
    report_status
) -> str:
    """Evaluates and executes user requests to delete specific sources from a workspace."""
    fast_llm = get_fast_llm() or target_llm

    await report_status("Processing document deletion request...")
    db_s = SessionLocal()
    current_db_docs = []
    try:
        current_db_docs = db_s.query(DBDocument).filter(DBDocument.chat_id == chat_id).all()
    finally:
        db_s.close()

    doc_summaries = []
    for d in current_db_docs:
        t = d.title or d.filename.replace(".pdf", "")
        snippet = (d.abstract or d.snippet or "")[:200]
        doc_summaries.append(f"- ID: {d.id} | Filename: {d.filename} | Title: {t} | Abstract: {snippet}")

    eval_prompt = get_source_deletion_prompt(query, doc_summaries)
    try:
        eval_resp = await fast_llm.acomplete(eval_prompt)
        clean_json_text = eval_resp.text.strip()
        clean_json_text = re.sub(r'^```(?:json)?\s*', '', clean_json_text, flags=re.I)
        clean_json_text = re.sub(r'\s*```$', '', clean_json_text)
        eval_data = json.loads(clean_json_text)
        to_delete_ids = eval_data.get("remove_doc_ids", [])
        
        deleted_titles = []
        if to_delete_ids:
            db_del = SessionLocal()
            try:
                docs_to_del = db_del.query(DBDocument).filter(
                    DBDocument.id.in_(to_delete_ids),
                    DBDocument.chat_id == chat_id
                ).all()
                deleted_titles = [dd.title or dd.filename.replace(".pdf", "") for dd in docs_to_del]
                delete_multiple_documents(db_del, chat_id, to_delete_ids)
            finally:
                db_del.close()

        num_deleted = len(deleted_titles)
        resp_text = f"Successfully removed **{num_deleted} requested document(s)** from sources:\n\n"
        for dt in deleted_titles:
            resp_text += f"- ❌ {dt}\n"
        resp_text += f"\nYour workspace sources have been updated per your request."
        
        action_payload = json.dumps({"action": "bulk_delete", "deleted_doc_ids": to_delete_ids})
        return f"{resp_text}\n\n<!-- SOURCES_ACTION: {action_payload} -->"
    except Exception as eval_err:
        logger.error(f"[Source Clean Error]: {eval_err}")
        return f"Failed to remove requested documents: {str(eval_err)}"
