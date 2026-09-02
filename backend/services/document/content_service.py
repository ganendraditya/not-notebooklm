import os
import re
import json
import logging
import asyncio
from typing import Dict, Any, Tuple
from sqlalchemy.orm import Session

from database import Document
from utils.file_utils import get_doc_file_path
from utils.pdf_utils import is_authentic_pdf_bytes
from utils.text_processing import clean_doi
import rag
import pdf_exporter

logger = logging.getLogger("uvicorn.error")

async def check_and_fetch_authentic_pdf_on_demand(doc: Document, file_path: str) -> Tuple[bool, str]:
    """
    Validates if local file is authentic PDF. If not, but document has OA metadata,
    it attempts an on-demand background fetch from open-access repositories.
    
    Returns (is_authentic_pdf, content_markdown)
    """
    file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
    is_authentic_pdf = False
    
    # 1. Local Disk Validation
    if os.path.exists(file_path) and file_size >= 1000:
        try:
            with open(file_path, "rb") as f:
                first_bytes = f.read(2048)
                is_authentic_pdf = is_authentic_pdf_bytes(first_bytes, min_size=500)
        except Exception:
            is_authentic_pdf = False

    new_content = ""

    # 2. On-demand fallback: if doc is OA or has PDF link but local file is not PDF, try fast download
    if not is_authentic_pdf and (doc.is_oa or doc.pdf_url or doc.doi):
        db_doi = clean_doi(doc.doi)
        try:
            fetched_oa = await asyncio.to_thread(
                pdf_exporter.resolve_and_fetch_authentic_pdf,
                doi=db_doi,
                title=doc.title,
                direct_url=doc.url or "",
                candidate_pdf_url=doc.pdf_url or ""
            )
            if fetched_oa and is_authentic_pdf_bytes(fetched_oa, min_size=1000):
                dir_name = os.path.dirname(file_path)
                base_name = os.path.basename(file_path)
                target_path = file_path

                if base_name.lower().endswith(".txt"):
                    pdf_base_name = base_name[:-4] + ".pdf"
                    target_path = os.path.join(dir_name, pdf_base_name)
                    try:
                        from database import SessionLocal, Document as DBDocument
                        db = SessionLocal()
                        db_doc = db.query(DBDocument).filter(DBDocument.id == doc.id).first()
                        if db_doc:
                            db_doc.filename = pdf_base_name
                            db_doc.access_status = "Open Access (Full PDF Available)"
                            db_doc.is_oa = True
                            doc.filename = pdf_base_name
                            db.commit()
                        db.close()
                    except Exception as db_err:
                        logger.debug(f"[DB filename update warning]: {db_err}")

                with open(target_path, "wb") as f:
                    f.write(fetched_oa)

                if target_path != file_path and os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except Exception:
                        pass

                file_path = target_path
                is_authentic_pdf = True
                
                try:
                    import pymupdf4llm
                    new_content = await asyncio.to_thread(pymupdf4llm.to_markdown, file_path)
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"[On-demand OA Fetch Warning]: {e}")
            
    return is_authentic_pdf, new_content

async def get_document_full_content(chat_id: str, doc: Document, db: Session) -> Dict[str, Any]:
    """
    Retrieves full markdown content, metadata, and performs AI audits/registry enrichment if necessary.
    """
    file_path = get_doc_file_path(chat_id, doc.filename)
    has_db_metadata = bool(doc.title)
    
    if has_db_metadata:
        try:
            db_authors = json.loads(doc.authors) if doc.authors else []
        except Exception:
            db_authors = []
        
        db_doi = clean_doi(doc.doi)
        
        res_data = {
            "id": doc.id,
            "filename": doc.filename,
            "created_at": doc.created_at,
            "type": os.path.splitext(doc.filename)[1].lower().replace(".", "") or "pdf",
            "title": doc.title,
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
        
        is_authentic_pdf, new_md_content = await check_and_fetch_authentic_pdf_on_demand(doc, file_path)

        if new_md_content:
            res_data["content"] = new_md_content
        elif os.path.exists(file_path):
            ext = os.path.splitext(doc.filename)[1].lower()
            try:
                if ext == ".pdf":
                    if is_authentic_pdf:
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

        if is_authentic_pdf:
            res_data["is_oa"] = True
            res_data["access_status"] = "Open Access (Full PDF Available)"
            res_data["has_full_pdf"] = True
            res_data["is_abstract_only"] = False
        else:
            res_data["has_full_pdf"] = False
            res_data["is_abstract_only"] = True
            res_data["access_status"] = "Publication Brief & Abstract (Direct Download Restricted)" if doc.is_oa else "Closed Access (Paywalled)"
            if res_data["content"].startswith("%PDF-") or "NOTBOOKLM SCHOLARARCHIVE" in res_data["content"] or "OFFICIAL PUBLICATION ARCHIVE RECORD" in res_data["content"]:
                res_data["content"] = f"# {doc.title} ({doc.year or 'N/A'})\n\n"
                if db_doi:
                    res_data["content"] += f"**DOI:** {db_doi}  \n"
                if res_data["url"]:
                    res_data["content"] += f"**URL:** {res_data['url']}  \n\n"
                res_data["content"] += f"## Abstract & Overview\n\n{res_data['abstract']}\n"
                
        return res_data
    
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
    
    _GENERIC_HEADERS = {
        "abstract", "abstrak", "overview", "paper", "document", "introduction", "keywords",
        "article in press", "in press", "journal pre-proof", "uncorrected proof",
        "corrected proof", "original article", "research article", "full length article",
        "short communication", "review article", "full paper", "research paper",
        "accepted manuscript", "author's copy",
    }
    
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
            
    header_scope = raw_content[:2500] if len(raw_content) > 2500 else raw_content
    doi_match = re.search(r"DOI:\*?\*?\s*([^\s\n\*\)]+)", header_scope, re.I)
    extracted_doi = doi_match.group(1).strip() if doi_match else ""
    if not extracted_doi:
        doi_regex_match = re.search(r"10\.\d{4,9}/[^\s\n<>\"'{}|\\^`]+", header_scope)
        if doi_regex_match:
            extracted_doi = doi_regex_match.group(0).strip()

    if extracted_doi:
        extracted_doi = extracted_doi.replace("**", "").replace("*", "").replace("__", "")
        extracted_doi = re.sub(r'[;.,:)\s]+$', '', extracted_doi).strip()
    res_data["doi"] = extracted_doi
    
    url_match = re.search(r"URL:\*?\*?\s*([^\s\n\*\)]+)", header_scope, re.I)
    if url_match:
        res_data["url"] = url_match.group(1).strip()
    elif extracted_doi:
        res_data["url"] = f"https://doi.org/{extracted_doi}"
        
    local_abstract = ""
    try:
        doc_sections = rag.split_markdown_into_academic_sections(raw_content, filename=doc.filename)
        abs_sec = next((s for s in doc_sections if s.get("canonical_section") == "abstract"), None)
        if abs_sec and abs_sec.get("raw_text"):
            local_abstract = abs_sec.get("raw_text").strip()
    except Exception:
        local_abstract = ""

    if not local_abstract:
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
    elif raw_content and len(raw_content.strip()) > 300:
        try:
            ai_audit = await asyncio.to_thread(
                rag.audit_paper_metadata_with_ai,
                paper_title=res_data["title"],
                raw_authors=res_data["authors"],
                raw_journal=res_data["journal"],
                raw_year=res_data["year"],
                raw_doi=extracted_doi,
                raw_citations=res_data["citations"],
                raw_abstract_or_html=raw_content[:4000],
                is_oa=True
            )
            if ai_audit:
                if ai_audit.get("abstract") and len(ai_audit["abstract"]) > 40:
                    res_data["abstract"] = ai_audit["abstract"]
                    res_data["abstract_type"] = ai_audit.get("abstract_type", "official")
                if ai_audit.get("title") and len(ai_audit["title"]) > 5 and ai_audit["title"].lower() not in _GENERIC_HEADERS:
                    res_data["title"] = ai_audit["title"]
                if ai_audit.get("authors"):
                    res_data["authors"] = ai_audit["authors"]
                if ai_audit.get("year"):
                    res_data["year"] = ai_audit["year"]
                if ai_audit.get("journal"):
                    res_data["journal"] = ai_audit["journal"]
                if ai_audit.get("journal_metric"):
                    res_data["journal_metric"] = ai_audit["journal_metric"]
        except Exception as audit_err:
            logger.debug(f"[Document Content AI Audit Warning]: {audit_err}")
        
    target_lookup_title = res_data["title"] if res_data["title"].lower() not in _GENERIC_HEADERS else clean_filename_title
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
            
            try:
                doc.title = res_data["title"]
                doc.authors = json.dumps(res_data["authors"], ensure_ascii=False) if res_data["authors"] else None
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
    if os.path.exists(file_path) and os.path.getsize(file_path) >= 1000:
        try:
            with open(file_path, "rb") as f:
                first_bytes = f.read(2048)
                is_authentic_pdf = is_authentic_pdf_bytes(first_bytes, min_size=500)
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
        res_data["access_status"] = "Publication Brief & Abstract (Direct Download Restricted)" if res_data["is_oa"] else "Closed Access (Paywalled)"

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
