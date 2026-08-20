import os
import re
import io
import shutil
import zipfile
import asyncio
import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, Response, StreamingResponse
from sqlalchemy.orm import Session

from database import get_db, ChatSession, Document
import models
import rag
import pdf_exporter
from helpers import (
    UPLOAD_DIR,
    TEMP_ZIPS_DIR,
    MAX_SOURCES_PER_CHAT,
    make_content_disposition,
    sanitize_paper_filename,
    get_doc_file_path,
    get_or_generate_document_pdf,
)

router = APIRouter(tags=["documents"])
logger = logging.getLogger("uvicorn.error")

@router.post("/chats/{chat_id}/upload", response_model=models.DocumentResponse)
async def upload_document(chat_id: str, file: UploadFile = File(...), db: Session = Depends(get_db)):
    db_chat = db.query(ChatSession).filter(ChatSession.id == chat_id).first()
    if not db_chat:
        raise HTTPException(status_code=404, detail="Chat not found")
        
    existing_count = db.query(Document).filter(Document.chat_id == chat_id).count()
    if existing_count >= MAX_SOURCES_PER_CHAT:
        raise HTTPException(status_code=400, detail=f"Source limit reached! This conversation already contains {existing_count}/{MAX_SOURCES_PER_CHAT} sources.")
        
    file_path = os.path.join(UPLOAD_DIR, f"{chat_id}_{file.filename}")
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    try:
        await asyncio.to_thread(rag.ingest_document, file_path, chat_id)
    except Exception as e:
        logger.error(f"[Upload Ingest Error]: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to parse document: {str(e)}")

    # Auto-extract & enrich metadata from uploaded PDF / document
    clean_fn_title = re.sub(r'<[^>]+>', '', os.path.splitext(file.filename)[0]).replace("_", " ").strip()
    # Normalize ALL CAPS title to readable Title Case if applicable
    if clean_fn_title.isupper() and len(clean_fn_title) > 8:
        clean_fn_title = clean_fn_title.title()
        
    extracted_doi = ""
    raw_header = ""
    try:
        if file.filename.lower().endswith(".pdf"):
            import pymupdf
            pdoc = pymupdf.open(file_path)
            if len(pdoc) > 0:
                raw_header = pdoc[0].get_text()[:3000]
            pdoc.close()
        else:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                raw_header = f.read(3000)
    except Exception:
        raw_header = ""

    if raw_header:
        doi_m = re.search(r'10\.\d{4,9}/[^\s\n<>\"\'{}|\\^`]+', raw_header)
        if doi_m:
            extracted_doi = doi_m.group(0).strip().rstrip(".")
            extracted_doi = re.sub(r'[;.,:)\s]+$', '', extracted_doi).strip()

    # Query academic APIs for verified metadata (Crossref / OpenAlex)
    resolved_title = clean_fn_title
    resolved_authors = []
    resolved_year = ""
    resolved_journal = ""
    resolved_metric = "Peer-Reviewed"
    resolved_abstract = ""
    resolved_url = ""
    resolved_doi = extracted_doi

    if extracted_doi or clean_fn_title:
        try:
            meta = await asyncio.to_thread(
                rag.resolve_paper_metadata_by_doi,
                doi=extracted_doi,
                title_fallback=clean_fn_title,
                fast_only=False
            )
            if meta:
                if meta.get("title") and len(meta["title"]) > 5:
                    resolved_title = meta["title"].strip()
                resolved_authors = meta.get("authors") or []
                resolved_year = str(meta.get("year") or "")
                resolved_journal = meta.get("journal") or meta.get("venue") or ""
                resolved_metric = meta.get("journal_metric") or "Peer-Reviewed"
                resolved_abstract = meta.get("abstract") or ""
                resolved_url = meta.get("url") or (f"https://doi.org/{meta.get('doi')}" if meta.get("doi") else "")
                resolved_doi = meta.get("doi") or extracted_doi
        except Exception as e:
            logger.debug(f"[Upload Metadata Resolution Warning]: {e}")

    # Check if authentic binary PDF
    is_valid_pdf = False
    if os.path.exists(file_path) and os.path.getsize(file_path) >= 35000:
        try:
            with open(file_path, "rb") as f:
                fb = f.read(2048)
                if fb.startswith(b"%PDF-"):
                    is_valid_pdf = True
        except Exception:
            is_valid_pdf = False

    authors_json = json.dumps(resolved_authors, ensure_ascii=False) if resolved_authors else None
    db_doc = Document(
        chat_id=chat_id,
        filename=file.filename,
        title=resolved_title,
        authors=authors_json,
        year=resolved_year,
        journal=resolved_journal,
        journal_metric=resolved_metric,
        doi=resolved_doi,
        url=resolved_url,
        abstract=resolved_abstract,
        abstract_type="official" if resolved_abstract and len(resolved_abstract) > 80 else "ai_summary",
        is_oa=True if is_valid_pdf else False,
        access_status="Open Access (Full PDF Available)" if is_valid_pdf else "Uploaded Document",
        quality_tier=4
    )
    db.add(db_doc)
    db.commit()
    db.refresh(db_doc)
    
    total_docs_count = db.query(Document).filter(Document.chat_id == chat_id).count()
    return models.DocumentResponse(
        id=db_doc.id,
        filename=db_doc.filename,
        title=db_doc.title or db_doc.filename.replace(".pdf", "").replace("_", " ").strip(),
        created_at=db_doc.created_at,
        index=total_docs_count,
        has_full_pdf=is_valid_pdf,
        is_oa=True if is_valid_pdf else False
    )

@router.delete("/chats/{chat_id}/documents/{doc_id}")
def delete_document(chat_id: str, doc_id: int, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == doc_id, Document.chat_id == chat_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    file_path = get_doc_file_path(chat_id, doc.filename)
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception:
            pass
    db.delete(doc)
    db.commit()
    return {"status": "success"}

@router.post("/chats/{chat_id}/documents/bulk_delete")
def bulk_delete_documents(chat_id: str, req: models.BulkDeleteRequest, db: Session = Depends(get_db)):
    docs = db.query(Document).filter(Document.id.in_(req.doc_ids), Document.chat_id == chat_id).all()
    for doc in docs:
        file_path = get_doc_file_path(chat_id, doc.filename)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass
        db.delete(doc)
    db.commit()
    return {"status": "success", "deleted_count": len(docs)}

@router.post("/chats/{chat_id}/clean_duplicates")
def clean_duplicate_documents(chat_id: str, db: Session = Depends(get_db)):
    chat = db.query(ChatSession).filter(ChatSession.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    docs = db.query(Document).filter(Document.chat_id == chat_id).all()
    if not docs or len(docs) <= 1:
        return {"status": "success", "cleaned_count": 0, "remaining_count": len(docs), "cleaned_doc_ids": []}

    # Helper to calculate quality score for each document (prefer authentic full PDF > metadata brief)
    def calculate_doc_quality(d: Document) -> tuple:
        fp = get_doc_file_path(chat_id, d.filename)
        sz = os.path.getsize(fp) if os.path.exists(fp) else 0
        has_full_pdf = False
        if os.path.exists(fp) and sz >= 35000:
            try:
                with open(fp, "rb") as f:
                    fb = f.read(2048)
                    if fb.startswith(b"%PDF-") and b"NOTBOOKLM SCHOLARLY ARCHIVE" not in fb and b"OFFICIAL PUBLICATION ARCHIVE RECORD" not in fb:
                        has_full_pdf = True
            except Exception:
                has_full_pdf = False
                
        score = 0
        if has_full_pdf:
            score += 10000 + min(sz // 1024, 5000) # Full manuscript gets highest tier
        if d.doi:
            score += 500
        if d.authors and d.authors != "[]" and "Academic Researchers" not in d.authors:
            score += 300
        if d.journal and "Academic Publication" not in d.journal:
            score += 200
        if d.abstract and len(d.abstract) > 100:
            score += min(len(d.abstract), 500)
            
        return (score, has_full_pdf, d.id)

    # Group documents by DOI and Normalized Title
    groups = [] # list of lists: [[doc1, doc2], [doc3]]
    doc_to_group = {}

    for doc in docs:
        fp = get_doc_file_path(chat_id, doc.filename)
        full_title = (doc.title or doc.filename).replace(".pdf", "").replace(".docx", "").replace(".txt", "").replace(".md", "").strip()
        extracted_doi = (doc.doi or "").strip().lower()
        
        if os.path.exists(fp) and not doc.title:
            try:
                with open(fp, "r", encoding="utf-8", errors="ignore") as fp_r:
                    first_lines = "".join([fp_r.readline() for _ in range(4)])
                    m_title = re.search(r'^\#\s*([^\n]+)', first_lines)
                    if m_title:
                        full_title = re.sub(r'\s*\(\d{4}\)$', '', m_title.group(1)).strip()
                    m_doi = re.search(r'(?:DOI:|\*\*DOI:\*\*|doi\.org/)\s*(10\.\d{4,9}/[^\s\)]+)', first_lines, re.I)
                    if m_doi and not extracted_doi:
                        extracted_doi = m_doi.group(1).lower().strip()
            except Exception:
                pass

        norm_title = rag.normalize_title_str(full_title)
        tokens = set(norm_title.split())

        matched_group_idx = None
        for g_idx, grp in enumerate(groups):
            for member in grp:
                m_fp = get_doc_file_path(chat_id, member.filename)
                m_title = (member.title or member.filename).replace(".pdf", "").replace(".docx", "").replace(".txt", "").replace(".md", "").strip()
                m_doi = (member.doi or "").strip().lower()
                m_norm = rag.normalize_title_str(m_title)
                m_tokens = set(m_norm.split())

                if extracted_doi and m_doi and extracted_doi == m_doi:
                    matched_group_idx = g_idx
                    break
                if norm_title and m_norm:
                    if norm_title == m_norm:
                        matched_group_idx = g_idx
                        break
                    if len(m_norm) >= 20 and (norm_title.startswith(m_norm) or m_norm.startswith(norm_title)):
                        matched_group_idx = g_idx
                        break
                    intersection = tokens.intersection(m_tokens)
                    overlap = len(intersection) / min(len(tokens), len(m_tokens)) if min(len(tokens), len(m_tokens)) > 0 else 0
                    if overlap >= 0.75 and len(intersection) >= 3:
                        matched_group_idx = g_idx
                        break
            if matched_group_idx is not None:
                break

        if matched_group_idx is not None:
            groups[matched_group_idx].append(doc)
        else:
            groups.append([doc])

    cleaned_doc_ids = []
    
    # In each duplicate group with >1 documents, retain the highest quality doc (full PDF preferred) and re-verify with official registry
    for grp in groups:
        if len(grp) > 1:
            # Sort descending by quality score
            sorted_grp = sorted(grp, key=lambda d: calculate_doc_quality(d), reverse=True)
            keeper = sorted_grp[0]
            duplicates = sorted_grp[1:]

            # 1. Collect best candidate DOI and Title across the group for registry lookup
            cand_doi = ""
            for d in grp:
                if d.doi and not cand_doi:
                    clean_d = d.doi.strip().replace("https://doi.org/", "").replace("http://doi.org/", "").replace("doi:", "").strip()
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

            # 2. Query Academic Registry (Crossref / OpenAlex) for the ground-truth metadata
            verified_meta = rag.resolve_paper_metadata_by_doi(
                doi=cand_doi,
                title_fallback=cand_title,
                fast_only=False
            )

            needs_db_update = False
            if verified_meta and verified_meta.get("title") and len(verified_meta["title"]) > 5:
                # Apply verified ground truth from publisher registry
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
                # Fallback: Merge best non-empty attributes across local duplicates
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

            # Normalize title to Title Case if still ALL CAPS
            if keeper.title and keeper.title.isupper() and len(keeper.title) > 8:
                keeper.title = keeper.title.title()
                needs_db_update = True

            # Delete the duplicates
            for dup in duplicates:
                cleaned_doc_ids.append(dup.id)
                dup_fp = get_doc_file_path(chat_id, dup.filename)
                if os.path.exists(dup_fp) and dup_fp != get_doc_file_path(chat_id, keeper.filename):
                    try:
                        os.remove(dup_fp)
                    except Exception:
                        pass
                db.delete(dup)

            if needs_db_update:
                db.add(keeper)

    if cleaned_doc_ids:
        db.commit()

    remaining = db.query(Document).filter(Document.chat_id == chat_id).count()
    return {
        "status": "success",
        "cleaned_count": len(cleaned_doc_ids),
        "remaining_count": remaining,
        "cleaned_doc_ids": cleaned_doc_ids
    }

@router.get("/chats/{chat_id}/documents/{doc_id}/download")
def download_document(chat_id: str, doc_id: int, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == doc_id, Document.chat_id == chat_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    pdf_bytes, download_filename = get_authentic_document_pdf(chat_id, doc.filename)
    if not pdf_bytes:
        raise HTTPException(
            status_code=404, 
            detail="Naskah lengkap PDF tidak tersedia untuk diunduh (hanya metadata / abstrak)."
        )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": make_content_disposition("attachment", download_filename)}
    )

@router.get("/chats/{chat_id}/documents/{doc_id}/raw")
def view_document_raw(chat_id: str, doc_id: int, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == doc_id, Document.chat_id == chat_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    file_path = get_doc_file_path(chat_id, doc.filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File on disk not found")
        
    ext = os.path.splitext(doc.filename)[1].lower()
    media_types = {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".csv": "text/csv",
        ".txt": "text/plain",
        ".md": "text/markdown",
        ".bib": "text/plain",
        ".ris": "text/plain"
    }
    return FileResponse(
        file_path,
        media_type=media_types.get(ext, "application/octet-stream"),
        filename=doc.filename,
        headers={"Content-Disposition": make_content_disposition("inline", doc.filename)}
    )

@router.get("/chats/{chat_id}/documents/{doc_id}/stream")
def stream_document_pdf(chat_id: str, doc_id: int, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == doc_id, Document.chat_id == chat_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    pdf_bytes, stream_filename = get_authentic_document_pdf(chat_id, doc.filename)
    if not pdf_bytes:
        raise HTTPException(
            status_code=404, 
            detail="Naskah lengkap PDF tidak tersedia untuk dokumen ini."
        )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": make_content_disposition("inline", stream_filename)}
    )

@router.get("/chats/{chat_id}/documents/{doc_id}/content")
async def get_document_content(chat_id: str, doc_id: int, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == doc_id, Document.chat_id == chat_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    file_path = get_doc_file_path(chat_id, doc.filename)
    clean_filename_title = re.sub(r'<[^>]+>', '', os.path.splitext(doc.filename)[0]).replace("_", " ").strip()
    
    # ---------- DB metadata path (imported papers) ----------
    # If title is persisted in DB, this doc was imported via search pipeline.
    # Use DB as single source of truth for all metadata; never re-extract title.
    has_db_metadata = bool(doc.title)
    
    if has_db_metadata:
        import json as _json
        try:
            db_authors = _json.loads(doc.authors) if doc.authors else []
        except Exception:
            db_authors = []
        
        # Sanitize DOI from DB
        db_doi = (doc.doi or "").strip()
        db_doi = db_doi.replace("**", "").replace("*", "").replace("__", "")
        db_doi = re.sub(r'[;.,:)\s]+$', '', db_doi).strip()
        
        res_data = {
            "id": doc.id,
            "filename": doc.filename,
            "created_at": doc.created_at,
            "type": os.path.splitext(doc.filename)[1].lower().replace(".", "") or "pdf",
            "title": doc.title,  # ponytail: title locked from import, never re-extracted
            "authors": db_authors,
            "publication_date": doc.year or "",
            "year": doc.year or "",
            "journal": doc.journal or doc.venue or "",
            "journal_metric": doc.journal_metric or "Peer-Reviewed",
            "quality_tier": doc.quality_tier or 4,
            "citations": doc.citations or 0,
            "doi": db_doi,
            "url": doc.url or (f"https://doi.org/{db_doi}" if db_doi else ""),
            "pdf_url": doc.pdf_url or "",
            "abstract": doc.abstract or doc.snippet or "",
            "abstract_type": doc.abstract_type or "official",
            "content": "",
            "is_oa": doc.is_oa if doc.is_oa is not None else True,
            "access_status": doc.access_status or "Open Access",
        }
        
        # Read file content for Full Paper tab (read-only, no metadata mutation)
        if os.path.exists(file_path):
            ext = os.path.splitext(doc.filename)[1].lower()
            try:
                if ext == ".pdf":
                    with open(file_path, "rb") as f:
                        header = f.read(5)
                    if header.startswith(b"%PDF"):
                        import pymupdf4llm
                        res_data["content"] = await asyncio.to_thread(pymupdf4llm.to_markdown, file_path)
                    else:
                        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                            res_data["content"] = f.read()
                elif ext in (".docx", ".doc"):
                    res_data["content"] = await asyncio.to_thread(rag.parse_docx_file, file_path)
                else:
                    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                        res_data["content"] = f.read()
            except Exception as e:
                res_data["content"] = f"Error reading document: {str(e)}"
        else:
            res_data["content"] = f"# {doc.title}\n\n*Document file is registered as a reference source.*"
        
        # Check if local file is authentic full paper PDF or abstract-only metadata
        file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
        is_authentic_pdf = False
        if os.path.exists(file_path) and file_size >= 35000:
            try:
                with open(file_path, "rb") as f:
                    first_bytes = f.read(2048)
                    if first_bytes.startswith(b"%PDF-") and b"NOTBOOKLM SCHOLARLY ARCHIVE" not in first_bytes and b"OFFICIAL PUBLICATION ARCHIVE RECORD" not in first_bytes:
                        is_authentic_pdf = True
            except Exception:
                is_authentic_pdf = False

        if is_authentic_pdf:
            res_data["is_oa"] = True
            res_data["access_status"] = "Open Access (Full PDF Available)"
            res_data["has_full_pdf"] = True
            res_data["is_abstract_only"] = False
        else:
            res_data["has_full_pdf"] = False
            res_data["is_abstract_only"] = True
            res_data["access_status"] = "Closed Access (Paywalled / Metadata Brief)" if not doc.is_oa else "Publication Brief & Abstract (Direct Download Restricted / HTTP 403)"
            # For abstract-only documents, ensure content does not render legacy synthetic PDF markup
            if res_data["content"].startswith("%PDF-") or "NOTBOOKLM SCHOLARLY ARCHIVE" in res_data["content"] or "OFFICIAL PUBLICATION ARCHIVE RECORD" in res_data["content"]:
                res_data["content"] = f"# {doc.title} ({doc.year or 'N/A'})\n\n"
                if db_doi:
                    res_data["content"] += f"**DOI:** {db_doi}  \n"
                if res_data["url"]:
                    res_data["content"] += f"**URL:** {res_data['url']}  \n\n"
                res_data["content"] += f"## Abstract & Overview\n\n{res_data['abstract']}\n"
        
        return res_data
    
    # ---------- Legacy path: manually uploaded docs (no DB metadata) ----------
    res_data = {
        "id": doc.id,
        "filename": doc.filename,
        "created_at": doc.created_at,
        "type": os.path.splitext(doc.filename)[1].lower().replace(".", "") or "pdf",
        "title": clean_filename_title,
        "authors": [],
        "publication_date": "",
        "year": "",
        "journal": "",
        "journal_metric": "Peer-Reviewed",
        "quality_tier": 4,
        "citations": 0,
        "doi": "",
        "url": "",
        "pdf_url": "",
        "abstract": "",
        "content": "",
        "is_oa": False,
        "access_status": "Closed Access (Paywalled)"
    }
    
    if not os.path.exists(file_path):
        res_data["content"] = f"# {doc.filename}\n\n*Document file is registered as a reference source.*"
        res_data["abstract"] = "Document content is registered in the source index."
        return res_data
        
    ext = os.path.splitext(doc.filename)[1].lower()
    raw_content = ""
    try:
        if ext == ".pdf":
            with open(file_path, "rb") as f:
                header = f.read(5)
            if header.startswith(b"%PDF"):
                import pymupdf4llm
                raw_content = await asyncio.to_thread(pymupdf4llm.to_markdown, file_path)
            else:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    raw_content = f.read()
        elif ext in (".docx", ".doc"):
            raw_content = await asyncio.to_thread(rag.parse_docx_file, file_path)
        elif ext in (".bib", ".bibtex"):
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                raw_content = await asyncio.to_thread(rag.parse_bibtex_text, f.read())
        elif ext == ".ris":
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                raw_content = await asyncio.to_thread(rag.parse_ris_text, f.read())
        elif ext in (".csv", ".tsv"):
            raw_content = await asyncio.to_thread(rag.parse_csv_file, file_path)
        else:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                raw_content = f.read()
    except Exception as e:
        raw_content = f"Error reading document: {str(e)}"
        
    res_data["content"] = raw_content
    
    # Generic non-title blacklist
    _GENERIC_HEADERS = {
        "abstract", "abstrak", "overview", "paper", "document", "introduction", "keywords",
        "article in press", "in press", "journal pre-proof", "uncorrected proof",
        "corrected proof", "original article", "research article", "full length article",
        "short communication", "review article", "full paper", "research paper",
        "accepted manuscript", "author's copy",
    }
    
    # 1. Parse Title (for manually uploaded docs only)
    res_data["title"] = clean_filename_title
    title_match = re.search(r"#+\s*\**([^\n\*]+)\**", raw_content)
    if title_match:
        cand_title = title_match.group(1).strip()
        year_in_title = re.search(r"\((\d{4})\)$", cand_title)
        if year_in_title:
            res_data["year"] = year_in_title.group(1)
            cand_title = cand_title[:year_in_title.start()].strip()
        cand_title = re.sub(r'<[^>]+>', '', cand_title).strip()
        if cand_title and cand_title.lower() not in _GENERIC_HEADERS:
            res_data["title"] = cand_title

    clean_filename_title = re.sub(r'<[^>]+>', '', clean_filename_title).strip()
    if not res_data["title"] or res_data["title"].lower() in _GENERIC_HEADERS:
        res_data["title"] = clean_filename_title
            
    # 2. Parse and Clean DOI (restrict regex search to first 2500 chars / header area to avoid catching cited references)
    header_scope = raw_content[:2500] if len(raw_content) > 2500 else raw_content
    doi_match = re.search(r"DOI:\*?\*?\s*([^\s\n\*\)]+)", header_scope, re.I)
    extracted_doi = doi_match.group(1).strip() if doi_match else ""
    if not extracted_doi:
        doi_regex_match = re.search(r"10\.\d{4,9}/[^\s\n<>\"'{}|\\^`]+", header_scope)
        if doi_regex_match:
            extracted_doi = doi_regex_match.group(0).strip()

    # Sanitize DOI: strip markdown artifacts and trailing punctuation
    if extracted_doi:
        extracted_doi = extracted_doi.replace("**", "").replace("*", "").replace("__", "")
        extracted_doi = re.sub(r'[;.,:)\s]+$', '', extracted_doi).strip()
    res_data["doi"] = extracted_doi
    
    # 3. Parse URL
    url_match = re.search(r"URL:\*?\*?\s*([^\s\n\*\)]+)", header_scope, re.I)
    if url_match:
        res_data["url"] = url_match.group(1).strip()
    elif extracted_doi:
        res_data["url"] = f"https://doi.org/{extracted_doi}"
        
    abs_match = re.search(r'(?:##\s*Abstract|\*\*ABSTRAK\*\*|ABSTRAK|\*\*Abstract\*\*|Abstract|Ringkasan)[^\n]*\n+([\s\S]*?)(?:Kata\s*Kunci|Keywords|I\.\s*PENDAHULUAN|1\.\s*Pendahuluan|##|$)', raw_content, re.I)
    local_abstract = abs_match.group(1).strip() if abs_match else ""
    if not local_abstract:
        abs_match_fb = re.search(r'##\s*Abstract[^\n]*\n+([\s\S]+)', raw_content)
        local_abstract = abs_match_fb.group(1).strip() if abs_match_fb else ""

    if local_abstract and rag.is_valid_abstract_content(local_abstract):
        res_data["abstract"] = rag.clean_academic_abstract(local_abstract)
        if rag.is_ai_synthesized_overview(local_abstract):
            res_data["abstract_type"] = "ai_summary"
        else:
            res_data["abstract_type"] = "official"
        
    target_lookup_title = res_data["title"] if res_data["title"].lower() not in _GENERIC_HEADERS else clean_filename_title
    # Keep the original title from file before API lookup
    original_file_title = res_data["title"]
    
    if extracted_doi or target_lookup_title:
        meta = await asyncio.to_thread(
            rag.resolve_paper_metadata_by_doi,
            extracted_doi,
            title_fallback=target_lookup_title,
            fast_only=(bool(extracted_doi) and bool(res_data["abstract"]))
        )
        if meta:
            meta_title = meta.get("title", "").strip()
            # Only accept meta title if it's NOT a generic publisher header and matches the document
            if meta_title and meta_title.lower() not in _GENERIC_HEADERS:
                res_data["title"] = meta_title
            else:
                res_data["title"] = original_file_title or clean_filename_title
            res_data["authors"] = meta.get("authors", []) or res_data["authors"]
            res_data["publication_date"] = meta.get("publication_date", "") or res_data["publication_date"]
            res_data["year"] = meta.get("year", res_data["year"]) or res_data["year"]
            res_data["journal"] = meta.get("journal", "") or res_data["journal"]
            res_data["journal_metric"] = meta.get("journal_metric", "Peer-Reviewed")
            res_data["quality_tier"] = meta.get("quality_tier", 4)
            res_data["citations"] = meta.get("citations", 0)
            clean_meta_doi = meta.get("doi", extracted_doi)
            if clean_meta_doi:
                clean_meta_doi = clean_meta_doi.replace("**", "").replace("*", "")
                clean_meta_doi = re.sub(r'[;.,:)\s]+$', '', clean_meta_doi).strip()
            res_data["doi"] = clean_meta_doi
            if meta.get("url"):
                res_data["url"] = meta.get("url")
            elif clean_meta_doi:
                res_data["url"] = f"https://doi.org/{clean_meta_doi}"
            res_data["pdf_url"] = meta.get("pdf_url", "")
            if not res_data["abstract"] and meta.get("abstract"):
                res_data["abstract"] = meta.get("abstract")
                res_data["abstract_type"] = meta.get("abstract_type", "official")
                
            if meta.get("abstract") and (not rag.is_valid_abstract_content(local_abstract) or len(raw_content) < 350):
                new_saved_content = f"# {res_data['title']} ({res_data['year']})\n\n**DOI:** {res_data['doi']}  \n**URL:** {res_data['url']}  \n\n## Abstract & Overview\n\n{res_data['abstract']}\n"
                try:
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(new_saved_content)
                except Exception:
                    pass
            
            # Persist resolved metadata to DB for future fast loads
            try:
                import json as _json
                doc.title = res_data["title"]
                doc.authors = _json.dumps(res_data["authors"], ensure_ascii=False) if res_data["authors"] else None
                doc.year = res_data["year"]
                doc.journal = res_data["journal"]
                doc.journal_metric = res_data["journal_metric"]
                doc.doi = res_data["doi"]
                doc.url = res_data["url"]
                doc.pdf_url = res_data.get("pdf_url", "")
                doc.abstract = res_data["abstract"]
                doc.abstract_type = res_data.get("abstract_type")
                doc.citations = res_data.get("citations", 0)
                doc.quality_tier = res_data.get("quality_tier", 4)
                db.commit()
            except Exception:
                pass
                    
    is_authentic_pdf = False
    if os.path.exists(file_path) and os.path.getsize(file_path) >= 35000:
        try:
            with open(file_path, "rb") as f:
                first_bytes = f.read(2048)
                if first_bytes.startswith(b"%PDF-") and b"NOTBOOKLM SCHOLARLY ARCHIVE" not in first_bytes and b"OFFICIAL PUBLICATION ARCHIVE RECORD" not in first_bytes:
                    is_authentic_pdf = True
        except Exception:
            is_authentic_pdf = False

    if is_authentic_pdf:
        res_data["is_oa"] = True
        res_data["access_status"] = "Open Access (Full PDF Available)"
        res_data["has_full_pdf"] = True
        res_data["is_abstract_only"] = False
    else:
        res_data["has_full_pdf"] = False
        res_data["is_abstract_only"] = True
        res_data["is_oa"] = bool(res_data.get("pdf_url"))
        res_data["access_status"] = "Closed Access (Paywalled / Metadata Brief)" if not res_data["is_oa"] else "Publication Brief & Abstract (Direct Download Restricted / HTTP 403)"

    if res_data["abstract"]:
        if rag.is_ai_synthesized_overview(res_data["abstract"]):
            res_data["abstract_type"] = "ai_summary"
    else:
        res_data["abstract_type"] = "ai_summary"
        res_data["abstract"] = rag.clean_academic_abstract(
            f"This scholarly publication investigates '{res_data['title']}' ({res_data['year'] or 'Recent publication'}). "
            f"Published in {res_data['journal']} by {', '.join(res_data['authors'][:3]) if res_data['authors'] else 'researchers'}, "
            f"the research presents methodology, computational framework, and empirical analysis in this domain. "
            f"Indexed in international academic indexing services (DOI: {extracted_doi or 'N/A'})."
        )
            
    return res_data

@router.post("/chats/{chat_id}/documents/bulk_download")
def bulk_download_documents(chat_id: str, req: models.BulkDeleteRequest, db: Session = Depends(get_db)):
    docs = db.query(Document).filter(Document.id.in_(req.doc_ids), Document.chat_id == chat_id).all()
    if not docs:
        raise HTTPException(status_code=404, detail="No documents found for download")
        
    if len(docs) == 1:
        doc = docs[0]
        pdf_bytes, download_filename = get_authentic_document_pdf(chat_id, doc.filename)
        if not pdf_bytes:
            raise HTTPException(status_code=404, detail="Naskah lengkap PDF tidak tersedia untuk diunduh.")
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": make_content_disposition("attachment", download_filename)}
        )
        
    import concurrent.futures
    zip_buffer = io.BytesIO()
    downloaded_count = 0
    skipped_docs = []

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        def fetch_doc_pdf(d):
            try:
                data, clean_name = get_authentic_document_pdf(chat_id, d.filename)
                return d, data, clean_name
            except Exception as e:
                logger.error(f"[Bulk Download Fetch Error]: {e}")
                return d, None, d.filename

        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(docs), 8)) as executor:
            future_to_doc = {executor.submit(fetch_doc_pdf, doc): doc for doc in docs}
            seen_filenames = set()
            
            for future in concurrent.futures.as_completed(future_to_doc):
                d_obj, pdf_bytes, clean_fn = future.result()
                if pdf_bytes:
                    downloaded_count += 1
                    base_name = clean_fn
                    counter = 1
                    while base_name in seen_filenames:
                        root, ext = os.path.splitext(clean_fn)
                        base_name = f"{root}_{counter}{ext}"
                        counter += 1
                    seen_filenames.add(base_name)
                    zip_file.writestr(base_name, pdf_bytes)
                else:
                    skipped_docs.append({
                        "filename": d_obj.filename,
                        "title": d_obj.title or d_obj.filename,
                        "doi": d_obj.doi or "",
                        "url": d_obj.url or (f"https://doi.org/{d_obj.doi}" if d_obj.doi else "N/A")
                    })
                    
        if skipped_docs:
            summary_lines = [
                "================================================================================",
                "NOTBOOKLM - RINGKASAN UNDUHAN DOKUMEN",
                "================================================================================",
                f"Total Dokumen Dipilih : {len(docs)}",
                f"Naskah Lengkap PDF Berhasil Diunduh : {downloaded_count}",
                f"Dokumen Dilewati (Hanya Abstrak / Paywalled) : {len(skipped_docs)}",
                "================================================================================",
                "",
                "DAFTAR DOKUMEN YANG DILEWATI (NASKAH LENGKAP TIDAK DAPAT DIUNDUH OTOMATIS):",
                ""
            ]
            for idx, item in enumerate(skipped_docs, 1):
                summary_lines.append(f"{idx}. {item['title']}")
                summary_lines.append(f"   Status : Naskah Berbayar (Paywalled) / Proteksi Repositori (HTTP 403)")
                summary_lines.append(f"   DOI / Tautan Resmi : {item['url']}")
                summary_lines.append("")
            summary_lines.append("Silakan unduh naskah lengkap melalui tautan resmi penerbit di atas.")
            zip_file.writestr("_CATATAN_DOKUMEN_DILEWATI.txt", "\n".join(summary_lines))

    if downloaded_count == 0:
        raise HTTPException(
            status_code=404, 
            detail="Tidak ada naskah lengkap PDF yang dapat diunduh dari dokumen yang dipilih (semuanya berstatus hanya abstrak/paywalled)."
        )

    zip_buffer.seek(0)
    zip_filename = f"NotbookLM_Sources_{downloaded_count}_files.zip"
    return Response(
        content=zip_buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": make_content_disposition("attachment", zip_filename)}
    )

@router.post("/chats/{chat_id}/documents/bulk_download_stream")
async def bulk_download_stream(chat_id: str, req: models.BulkDeleteRequest, db: Session = Depends(get_db)):
    docs = db.query(Document).filter(Document.id.in_(req.doc_ids), Document.chat_id == chat_id).all()
    if not docs:
        raise HTTPException(status_code=404, detail="No documents found for download")

    doc_records = [(d.id, d.filename, d.title or d.filename, d.doi or "", d.url or "") for d in docs]
    total_count = len(doc_records)
    import uuid as uuid_pkg
    task_id = str(uuid_pkg.uuid4())
    zip_file_path = os.path.join(TEMP_ZIPS_DIR, f"{task_id}.zip")

    async def event_generator():
        queue = asyncio.Queue()
        
        def worker_sync():
            import concurrent.futures
            seen_names = set()
            processed_count = 0
            downloaded_count = 0
            skipped_docs = []
            
            with zipfile.ZipFile(zip_file_path, "w", zipfile.ZIP_DEFLATED) as zf:
                def process_single(doc_info):
                    d_id, d_fn, d_title, d_doi, d_url = doc_info
                    try:
                        pdf_data, clean_name = get_authentic_document_pdf(chat_id, d_fn)
                        return d_fn, d_title, d_doi, d_url, clean_name, pdf_data, None
                    except Exception as e:
                        logger.error(f"[Worker Sync PDF Error]: {e}")
                        return d_fn, d_title, d_doi, d_url, d_fn, None, str(e)

                with concurrent.futures.ThreadPoolExecutor(max_workers=min(total_count, 6)) as executor:
                    futures = [executor.submit(process_single, info) for info in doc_records]
                    for fut in concurrent.futures.as_completed(futures):
                        orig_fn, item_title, item_doi, item_url, clean_fn, pdf_bytes, err = fut.result()
                        processed_count += 1
                        if pdf_bytes:
                            downloaded_count += 1
                            base_name = clean_fn
                            counter = 1
                            while base_name in seen_names:
                                root, ext = os.path.splitext(clean_fn)
                                base_name = f"{root}_{counter}{ext}"
                                counter += 1
                            seen_names.add(base_name)
                            zf.writestr(base_name, pdf_bytes)
                        else:
                            skipped_docs.append({
                                "filename": orig_fn,
                                "title": item_title,
                                "doi": item_doi,
                                "url": item_url or (f"https://doi.org/{item_doi}" if item_doi else "N/A")
                            })
                        
                        calc_percent = round((processed_count / max(1, total_count)) * 100)
                        queue.put_nowait({
                            "type": "progress",
                            "current": processed_count,
                            "total": total_count,
                            "downloaded_count": downloaded_count,
                            "skipped_count": len(skipped_docs),
                            "percent": calc_percent,
                            "filename": orig_fn,
                            "is_skipped": pdf_bytes is None
                        })

                if skipped_docs:
                    summary_lines = [
                        "================================================================================",
                        "NOTBOOKLM - RINGKASAN UNDUHAN DOKUMEN",
                        "================================================================================",
                        f"Total Dokumen Dipilih : {total_count}",
                        f"Naskah Lengkap PDF Berhasil Diunduh : {downloaded_count}",
                        f"Dokumen Dilewati (Hanya Abstrak / Paywalled) : {len(skipped_docs)}",
                        "================================================================================",
                        "",
                        "DAFTAR DOKUMEN YANG DILEWATI (NASKAH LENGKAP TIDAK DAPAT DIUNDUH OTOMATIS):",
                        ""
                    ]
                    for idx, item in enumerate(skipped_docs, 1):
                        summary_lines.append(f"{idx}. {item['title']}")
                        summary_lines.append(f"   Status : Naskah Berbayar (Paywalled) / Proteksi Repositori (HTTP 403)")
                        summary_lines.append(f"   DOI / Tautan Resmi : {item['url']}")
                        summary_lines.append("")
                    summary_lines.append("Silakan unduh naskah lengkap melalui tautan resmi penerbit di atas.")
                    zf.writestr("_CATATAN_DOKUMEN_DILEWATI.txt", "\n".join(summary_lines))
            
            if downloaded_count == 0 and len(skipped_docs) > 0:
                # Cleanup empty zip
                try:
                    if os.path.exists(zip_file_path):
                        os.remove(zip_file_path)
                except Exception:
                    pass
                queue.put_nowait({
                    "type": "error",
                    "message": "Tidak ada naskah lengkap PDF yang dapat diunduh (dokumen yang dipilih hanya berstatus metadata / abstrak)."
                })
            else:
                total_size_mb = round(os.path.getsize(zip_file_path) / (1024 * 1024), 2) if os.path.exists(zip_file_path) else 0.0
                queue.put_nowait({
                    "type": "complete",
                    "task_id": task_id,
                    "total": total_count,
                    "downloaded_count": downloaded_count,
                    "skipped_count": len(skipped_docs),
                    "percent": 100,
                    "filename": f"NotbookLM_Sources_{downloaded_count}_files.zip",
                    "total_size_mb": total_size_mb,
                    "download_url": f"/chats/{chat_id}/documents/download_zip/{task_id}"
                })
            queue.put_nowait(None)

        loop = asyncio.get_event_loop()
        loop.run_in_executor(None, worker_sync)

        while True:
            item = await queue.get()
            if item is None:
                break
            import json
            yield f"data: {json.dumps(item)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.get("/chats/{chat_id}/documents/download_zip/{task_id}")
def download_prepared_zip(chat_id: str, task_id: str):
    clean_task = re.sub(r'[^a-zA-Z0-9-]', '', task_id)
    zip_path = os.path.join(TEMP_ZIPS_DIR, f"{clean_task}.zip")
    if not os.path.exists(zip_path):
        raise HTTPException(status_code=404, detail="Prepared download file not found or expired.")

    return FileResponse(
        zip_path,
        media_type="application/zip",
        headers={"Content-Disposition": make_content_disposition("attachment", f"NotbookLM_Sources_{chat_id[:8]}.zip")}
    )
