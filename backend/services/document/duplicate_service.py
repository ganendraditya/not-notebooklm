import os
import re
import json
import logging
import asyncio
from typing import Dict, Any, Tuple, List
from sqlalchemy.orm import Session

from database import Document
from utils.file_utils import get_doc_file_path
from utils.pdf_utils import is_binary_pdf
from utils.text_processing import clean_doi, is_matching_academic_paper
import rag

logger = logging.getLogger("uvicorn.error")

def calculate_doc_quality(chat_id: str, d: Document) -> Tuple[int, bool, int]:
    """Calculates quality score for duplicate cleanup (prefers authentic full PDF > metadata brief)."""
    fp = get_doc_file_path(chat_id, d.filename)
    sz = os.path.getsize(fp) if os.path.exists(fp) else 0
    has_full_pdf = is_binary_pdf(fp)
            
    score = 0
    if has_full_pdf:
        score += 10000 + min(sz // 1024, 5000)
    if d.doi:
        score += 500
    if d.authors and d.authors != "[]" and "Academic Researchers" not in d.authors:
        score += 300
    if d.journal and "Academic Publication" not in d.journal:
        score += 200
    if d.abstract and len(d.abstract) > 100:
        score += min(len(d.abstract), 500)
        
    return (score, has_full_pdf, d.id)

async def clean_chat_duplicates(chat_id: str, db: Session) -> Dict[str, Any]:
    """
    Groups chat documents by DOI and title similarity, keeps highest quality version,
    enriches with official registry, and removes lower-quality duplicates.
    """
    docs = db.query(Document).filter(Document.chat_id == chat_id).all()
    if not docs or len(docs) <= 1:
        return {
            "status": "success",
            "cleaned_count": 0,
            "deleted_count": 0,
            "remaining_count": len(docs),
            "cleaned_doc_ids": [],
            "deleted_ids": []
        }

    groups: List[List[Document]] = []

    for doc in docs:
        fp = get_doc_file_path(chat_id, doc.filename)
        full_title = (doc.title or doc.filename).replace(".pdf", "").replace(".docx", "").replace(".txt", "").replace(".md", "").strip()
        extracted_doi = clean_doi(doc.doi).lower() if doc.doi else ""
        
        if os.path.exists(fp) and (not doc.title or not extracted_doi):
            try:
                with open(fp, "r", encoding="utf-8", errors="ignore") as fp_r:
                    first_lines = "".join([fp_r.readline() for _ in range(4)])
                    m_title = re.search(r'^\#\s*([^\n]+)', first_lines)
                    if m_title and not doc.title:
                        full_title = re.sub(r'\s*\(\d{4}\)$', '', m_title.group(1)).strip()
                    m_doi = re.search(r'(?:DOI:|\*\*DOI:\*\*|doi\.org/)\s*(10\.\d{4,9}/[^\s\)]+)', first_lines, re.I)
                    if m_doi and not extracted_doi:
                        extracted_doi = clean_doi(m_doi.group(1)).lower()
            except Exception as e:
                logger.error(f"[CleanDuplicates] Failed to read {fp}: {e}")

        matched_group_idx = None
        for g_idx, grp in enumerate(groups):
            for member in grp:
                m_title = (member.title or member.filename).replace(".pdf", "").replace(".docx", "").replace(".txt", "").replace(".md", "").strip()
                if is_matching_academic_paper(full_title, extracted_doi, m_title, member.doi):
                    matched_group_idx = g_idx
                    break
            if matched_group_idx is not None:
                break

        if matched_group_idx is not None:
            groups[matched_group_idx].append(doc)
        else:
            groups.append([doc])

    cleaned_doc_ids: List[int] = []
    
    for grp in groups:
        if len(grp) > 1:
            sorted_grp = sorted(grp, key=lambda d: calculate_doc_quality(chat_id, d), reverse=True)
            keeper = sorted_grp[0]
            duplicates = sorted_grp[1:]

            cand_doi = ""
            for d in grp:
                if d.doi and not cand_doi:
                    clean_d = clean_doi(d.doi)
                    if re.search(r'10\.\d{4,9}/', clean_d):
                        cand_doi = clean_d
            
            cand_title = ""
            for d in grp:
                if d.title and len(d.title) > 8 and not d.title.isupper():
                    cand_title = d.title
                    break
            if not cand_title:
                for d in grp:
                    if d.title and len(d.title) > 8:
                        cand_title = d.title.title()
                        break
            if not cand_title:
                cand_title = keeper.filename.replace(".pdf", "").replace("_", " ").strip().title()

            verified_meta = None
            try:
                verified_meta = await asyncio.to_thread(
                    rag.resolve_paper_metadata_by_doi,
                    doi=cand_doi,
                    title_fallback=cand_title,
                    fast_only=False
                )
            except Exception as e:
                logger.error(f"[CleanDuplicates Registry Error]: {e}")

            needs_db_update = False
            if verified_meta and verified_meta.get("title") and len(verified_meta["title"]) > 5:
                keeper.title = verified_meta["title"].strip()
                if verified_meta.get("authors"):
                    keeper.authors = json.dumps(verified_meta["authors"], ensure_ascii=False)
                if verified_meta.get("journal"):
                    keeper.journal = verified_meta["journal"]
                if verified_meta.get("journal_metric"):
                    keeper.journal_metric = verified_meta["journal_metric"]
                if verified_meta.get("doi"):
                    keeper.doi = verified_meta["doi"]
                if verified_meta.get("year"):
                    keeper.year = str(verified_meta["year"])
                if verified_meta.get("abstract") and rag.is_valid_abstract_content(verified_meta["abstract"]):
                    keeper.abstract = verified_meta["abstract"]
                    keeper.abstract_type = verified_meta.get("abstract_type", "official")
                if verified_meta.get("url"):
                    keeper.url = verified_meta["url"]
                needs_db_update = True
            else:
                for dup in duplicates:
                    if (not keeper.title or keeper.title.isupper()) and dup.title and not dup.title.isupper():
                        keeper.title = dup.title
                        needs_db_update = True
                    if not keeper.doi and dup.doi:
                        keeper.doi = dup.doi
                        needs_db_update = True
                    if (not keeper.journal or keeper.journal == "Academic Publication") and dup.journal and dup.journal != "Academic Publication":
                        keeper.journal = dup.journal
                        needs_db_update = True
                    if (not keeper.authors or keeper.authors in ("[]", None)) and dup.authors and dup.authors not in ("[]", None):
                        keeper.authors = dup.authors
                        needs_db_update = True
                    if (not keeper.abstract or len(keeper.abstract) < 80) and dup.abstract and len(dup.abstract) > 80:
                        keeper.abstract = dup.abstract
                        keeper.abstract_type = dup.abstract_type
                        needs_db_update = True
                    if (not keeper.year or keeper.year == "N/A") and dup.year and dup.year != "N/A":
                        keeper.year = dup.year
                        needs_db_update = True

            if keeper.title and keeper.title.isupper() and len(keeper.title) > 8:
                keeper.title = keeper.title.title()
                needs_db_update = True

            for dup in duplicates:
                cleaned_doc_ids.append(dup.id)
                dup_fp = get_doc_file_path(chat_id, dup.filename)
                if os.path.exists(dup_fp) and dup_fp != get_doc_file_path(chat_id, keeper.filename):
                    try:
                        os.remove(dup_fp)
                    except Exception as e:
                        logger.error(f"[CleanDuplicates Error] Failed to delete file {dup_fp}: {e}")
                try:
                    rag.delete_document_vectors(chat_id, dup.filename)
                except Exception as ve:
                    logger.debug(f"[CleanDuplicates] Failed vector delete for {dup.filename}: {ve}")
                db.delete(dup)

            if needs_db_update:
                db.add(keeper)

    if cleaned_doc_ids:
        db.commit()

    remaining = max(0, len(docs) - len(cleaned_doc_ids))
    return {
        "status": "success",
        "cleaned_count": len(cleaned_doc_ids),
        "deleted_count": len(cleaned_doc_ids),
        "remaining_count": remaining,
        "cleaned_doc_ids": cleaned_doc_ids,
        "deleted_ids": cleaned_doc_ids
    }
