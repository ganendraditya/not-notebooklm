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
        raise HTTPException(status_code=400, detail=f"Batas maksimal tercapai! Percakapan ini sudah memiliki {existing_count}/250 sumber.")
        
    file_path = os.path.join(UPLOAD_DIR, f"{chat_id}_{file.filename}")
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    try:
        await asyncio.to_thread(rag.ingest_document, file_path, chat_id)
    except Exception as e:
        logger.error(f"[Upload Ingest Error]: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to parse document: {str(e)}")
        
    db_doc = Document(chat_id=chat_id, filename=file.filename)
    db.add(db_doc)
    db.commit()
    db.refresh(db_doc)
    
    total_docs_count = db.query(Document).filter(Document.chat_id == chat_id).count()
    return models.DocumentResponse(
        id=db_doc.id,
        filename=db_doc.filename,
        created_at=db_doc.created_at,
        index=total_docs_count
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

    docs = db.query(Document).filter(Document.chat_id == chat_id).order_by(Document.id.asc()).all()
    if not docs:
        return {"status": "success", "cleaned_count": 0, "remaining_count": 0, "cleaned_doc_ids": []}

    seen_signatures = []
    seen_dois = set()
    cleaned_doc_ids = []

    for doc in docs:
        file_path = get_doc_file_path(chat_id, doc.filename)
        full_title = doc.filename.replace(".pdf", "").replace(".docx", "").replace(".txt", "").replace(".md", "").strip()
        extracted_doi = ""
        
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as fp:
                    first_lines = "".join([fp.readline() for _ in range(4)])
                    m_title = re.search(r'^\#\s*([^\n]+)', first_lines)
                    if m_title:
                        full_title = re.sub(r'\s*\(\d{4}\)$', '', m_title.group(1)).strip()
                    m_doi = re.search(r'(?:DOI:|\*\*DOI:\*\*|doi\.org/)\s*(10\.\d{4,9}/[^\s\)]+)', first_lines, re.I)
                    if m_doi:
                        extracted_doi = m_doi.group(1).lower().strip()
            except Exception:
                pass

        norm_title = rag.normalize_title_str(full_title)
        tokens = set(norm_title.split())

        is_dup = False
        if extracted_doi and extracted_doi in seen_dois:
            is_dup = True
        elif norm_title:
            for ex_norm, ex_tokens in seen_signatures:
                if norm_title == ex_norm:
                    is_dup = True
                    break
                if len(ex_norm) >= 20 and (norm_title.startswith(ex_norm) or ex_norm.startswith(norm_title)):
                    is_dup = True
                    break
                intersection = tokens.intersection(ex_tokens)
                overlap = len(intersection) / min(len(tokens), len(ex_tokens)) if min(len(tokens), len(ex_tokens)) > 0 else 0
                if overlap >= 0.75 and len(intersection) >= 3:
                    is_dup = True
                    break

        if is_dup:
            cleaned_doc_ids.append(doc.id)
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception:
                    pass
            db.delete(doc)
        else:
            if norm_title:
                seen_signatures.append((norm_title, tokens))
            if extracted_doi:
                seen_dois.add(extracted_doi)

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
        
    pdf_bytes, download_filename = get_or_generate_document_pdf(chat_id, doc.filename)
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
        
    pdf_bytes, stream_filename = get_or_generate_document_pdf(chat_id, doc.filename)
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
    
    # 1. Parse Title
    res_data["title"] = clean_filename_title
    title_match = re.search(r"#+\s*\**([^\n\*]+)\**", raw_content)
    if title_match:
        cand_title = title_match.group(1).strip()
        year_in_title = re.search(r"\((\d{4})\)$", cand_title)
        if year_in_title:
            res_data["year"] = year_in_title.group(1)
            cand_title = cand_title[:year_in_title.start()].strip()
        cand_title = re.sub(r'<[^>]+>', '', cand_title).strip()
        # Reject generic non-titles extracted from markdown headers
        if cand_title and cand_title.lower() not in ("abstract", "abstrak", "overview", "paper", "document", "introduction", "keywords"):
            res_data["title"] = cand_title

    clean_filename_title = re.sub(r'<[^>]+>', '', clean_filename_title).strip()
    if not res_data["title"] or res_data["title"].lower() in ("abstract", "abstrak", "overview", "paper", "document"):
        res_data["title"] = clean_filename_title
            
    # 2. Parse and Clean DOI
    doi_match = re.search(r"DOI:\*?\*?\s*([^\s\n\*\)]+)", raw_content)
    extracted_doi = doi_match.group(1).strip() if doi_match else ""
    if not extracted_doi:
        doi_regex_match = re.search(r"10\.\d{4,9}/[^\s\n<>\"'{}|\\^`]+", raw_content)
        if doi_regex_match:
            extracted_doi = doi_regex_match.group(0).strip()

    # Clean trailing punctuation from DOI
    if extracted_doi:
        extracted_doi = re.sub(r'[;.,:)\s]+$', '', extracted_doi).strip()
    res_data["doi"] = extracted_doi
    
    # 3. Parse URL
    url_match = re.search(r"URL:\*?\*?\s*([^\s\n\*\)]+)", raw_content)
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
        
    target_lookup_title = res_data["title"] if res_data["title"].lower() not in ("abstract", "abstrak", "overview", "paper") else clean_filename_title
    if extracted_doi or target_lookup_title:
        meta = await asyncio.to_thread(
            rag.resolve_paper_metadata_by_doi,
            extracted_doi,
            title_fallback=target_lookup_title,
            fast_only=(bool(extracted_doi) and bool(res_data["abstract"]))
        )
        if meta:
            meta_title = meta.get("title", "").strip()
            if meta_title and meta_title.lower() not in ("abstract", "abstrak", "overview", "paper"):
                res_data["title"] = meta_title
            else:
                res_data["title"] = res_data["title"] or clean_filename_title
            res_data["authors"] = meta.get("authors", []) or res_data["authors"]
            res_data["publication_date"] = meta.get("publication_date", "") or res_data["publication_date"]
            res_data["year"] = meta.get("year", res_data["year"]) or res_data["year"]
            res_data["journal"] = meta.get("journal", "") or res_data["journal"]
            res_data["journal_metric"] = meta.get("journal_metric", "Peer-Reviewed")
            res_data["quality_tier"] = meta.get("quality_tier", 4)
            res_data["citations"] = meta.get("citations", 0)
            clean_meta_doi = meta.get("doi", extracted_doi)
            if clean_meta_doi:
                clean_meta_doi = re.sub(r'[;.,:)\s]+$', '', clean_meta_doi).strip()
            res_data["doi"] = clean_meta_doi
            res_data["url"] = meta.get("url", res_data["url"])
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
                    
    if os.path.exists(file_path) and os.path.getsize(file_path) >= 50000:
        res_data["is_oa"] = True
        res_data["access_status"] = "Open Access (Full PDF Available)"
    else:
        try:
            target_doi = res_data.get("doi") or extracted_doi
            target_title = res_data.get("title") or clean_filename_title
            fetched_oa = await asyncio.to_thread(
                pdf_exporter.resolve_and_fetch_authentic_pdf,
                doi=target_doi,
                title=target_title,
                candidate_pdf_url=res_data.get("pdf_url")
            )
            if fetched_oa and len(fetched_oa) >= 50000:
                with open(file_path, "wb") as f:
                    f.write(fetched_oa)
                res_data["is_oa"] = True
                res_data["access_status"] = "Open Access (Full PDF Available)"
            elif res_data.get("pdf_url"):
                res_data["is_oa"] = True
                res_data["access_status"] = "Open Access (Full PDF Available)"
            else:
                res_data["is_oa"] = False
                res_data["access_status"] = "Closed Access (Paywalled / Metadata Brief)"
        except Exception:
            res_data["is_oa"] = bool(res_data.get("pdf_url"))
            res_data["access_status"] = "Open Access (Full PDF Available)" if res_data["is_oa"] else "Closed Access (Paywalled / Metadata Brief)"

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
        pdf_bytes, download_filename = get_or_generate_document_pdf(chat_id, doc.filename)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": make_content_disposition("attachment", download_filename)}
        )
        
    import concurrent.futures
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        def fetch_doc_pdf(d):
            try:
                data, clean_name = get_or_generate_document_pdf(chat_id, d.filename)
                return data, clean_name
            except Exception as e:
                logger.error(f"[Bulk Download Fetch Error]: {e}")
                return None, d.filename

        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(docs), 8)) as executor:
            future_to_doc = {executor.submit(fetch_doc_pdf, doc): doc for doc in docs}
            seen_filenames = set()
            
            for future in concurrent.futures.as_completed(future_to_doc):
                pdf_bytes, clean_fn = future.result()
                if pdf_bytes:
                    base_name = clean_fn
                    counter = 1
                    while base_name in seen_filenames:
                        root, ext = os.path.splitext(clean_fn)
                        base_name = f"{root}_{counter}{ext}"
                        counter += 1
                    seen_filenames.add(base_name)
                    zip_file.writestr(base_name, pdf_bytes)
                    
    zip_buffer.seek(0)
    zip_filename = f"NotbookLM_Sources_{chat_id[:8]}.zip"
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

    doc_ids_and_names = [(d.id, d.filename) for d in docs]
    total_count = len(doc_ids_and_names)
    import uuid as uuid_pkg
    task_id = str(uuid_pkg.uuid4())
    zip_file_path = os.path.join(TEMP_ZIPS_DIR, f"{task_id}.zip")

    async def event_generator():
        queue = asyncio.Queue()
        
        def worker_sync():
            import concurrent.futures
            seen_names = set()
            processed_count = 0
            
            with zipfile.ZipFile(zip_file_path, "w", zipfile.ZIP_DEFLATED) as zf:
                def process_single(doc_info):
                    d_id, d_fn = doc_info
                    try:
                        pdf_data, clean_name = get_or_generate_document_pdf(chat_id, d_fn)
                        return d_fn, clean_name, pdf_data, None
                    except Exception as e:
                        logger.error(f"[Worker Sync PDF Error]: {e}")
                        return d_fn, d_fn, None, str(e)

                with concurrent.futures.ThreadPoolExecutor(max_workers=min(total_count, 6)) as executor:
                    futures = [executor.submit(process_single, info) for info in doc_ids_and_names]
                    for fut in concurrent.futures.as_completed(futures):
                        orig_fn, clean_fn, pdf_bytes, err = fut.result()
                        processed_count += 1
                        if pdf_bytes:
                            base_name = clean_fn
                            counter = 1
                            while base_name in seen_names:
                                root, ext = os.path.splitext(clean_fn)
                                base_name = f"{root}_{counter}{ext}"
                                counter += 1
                            seen_names.add(base_name)
                            zf.writestr(base_name, pdf_bytes)
                        
                        calc_percent = round((processed_count / max(1, total_count)) * 100)
                        queue.put_nowait({
                            "type": "progress",
                            "current": processed_count,
                            "total": total_count,
                            "percent": calc_percent,
                            "filename": orig_fn
                        })
            
            queue.put_nowait({
                "type": "complete",
                "task_id": task_id,
                "total": total_count,
                "percent": 100,
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
