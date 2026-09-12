import os
import re
import json
import logging
import asyncio
from typing import Dict, Any, Tuple
from sqlalchemy.orm import Session

from database import Document, commit_with_retry
from utils.file_utils import get_doc_file_path
from utils.pdf_utils import is_authentic_pdf_bytes, is_binary_pdf
from utils.text_processing import clean_doi
from providers.academic import resolve_and_fetch_authentic_pdf
import rag

logger = logging.getLogger("uvicorn.error")

def inspect_document_file_status(chat_id: str, filename: str) -> bool:
    """Checks if a document file exists on disk and is an authentic binary PDF."""
    fp = get_doc_file_path(chat_id, filename)
    return is_binary_pdf(fp)

async def check_and_fetch_authentic_pdf_on_demand(doc: Any, file_path: str) -> Tuple[bool, str]:
    """
    Validates if local file is authentic PDF. If not, but document has OA metadata,
    it attempts an on-demand background fetch from open-access repositories.
    
    Returns (is_authentic_pdf, content_markdown)
    """
    is_authentic_pdf = is_binary_pdf(file_path)
    new_content = ""

    # Helper getters to support both SQLAlchemy Document and plain DTO dicts
    doc_is_oa = doc.get("is_oa") if isinstance(doc, dict) else getattr(doc, "is_oa", False)
    doc_pdf_url = doc.get("pdf_url") if isinstance(doc, dict) else getattr(doc, "pdf_url", None)
    doc_doi = doc.get("doi") if isinstance(doc, dict) else getattr(doc, "doi", None)
    doc_title = doc.get("title") if isinstance(doc, dict) else getattr(doc, "title", "")
    doc_url = doc.get("url") if isinstance(doc, dict) else getattr(doc, "url", "")
    doc_id = doc.get("id") if isinstance(doc, dict) else getattr(doc, "id", None)

    # 2. On-demand fallback: if doc is OA or has PDF link but local file is not PDF, try fast download
    if not is_authentic_pdf and (doc_is_oa or doc_pdf_url or doc_doi):
        db_doi = clean_doi(doc_doi)
        try:
            fetched_oa = await asyncio.to_thread(
                resolve_and_fetch_authentic_pdf,
                doi=db_doi,
                title=doc_title,
                direct_url=doc_url or "",
                candidate_pdf_url=doc_pdf_url or ""
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
                        db_doc = db.query(DBDocument).filter(DBDocument.id == doc_id).first()
                        if db_doc:
                            db_doc.filename = pdf_base_name
                            db_doc.access_status = "Open Access (Full PDF Available)"
                            db_doc.is_oa = True
                            if isinstance(doc, dict):
                                doc["filename"] = pdf_base_name
                            else:
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
        
        # If document has missing DOI or authors in DB, opportunistically run 3-tier hybrid metadata extraction
        if (not db_doi or not db_authors) and os.path.exists(file_path):
            try:
                from services.document.metadata_extractor import extract_hybrid_document_metadata
                enriched = await extract_hybrid_document_metadata(file_path, doc.filename)
                if enriched and (enriched.get("doi") or enriched.get("authors")):
                    if enriched.get("doi"):
                        db_doi = enriched["doi"]
                        doc.doi = enriched["doi"]
                        doc.url = enriched.get("url") or f"https://doi.org/{db_doi}"
                    if enriched.get("title") and (not doc.title or doc.title == doc.filename.replace(".pdf", "")):
                        doc.title = enriched["title"]
                    if enriched.get("authors"):
                        doc.authors = json.dumps(enriched["authors"], ensure_ascii=False)
                        db_authors = enriched["authors"]
                    if enriched.get("year"):
                        doc.year = str(enriched["year"])
                    if enriched.get("journal"):
                        doc.journal = enriched["journal"]
                    if enriched.get("abstract") and not doc.abstract:
                        doc.abstract = enriched["abstract"]
                    if enriched.get("journal_metric"):
                        doc.journal_metric = enriched["journal_metric"]
                    if enriched.get("access_status"):
                        doc.access_status = enriched["access_status"]
                    commit_with_retry(db)
            except Exception as e:
                logger.debug(f"[On-demand hybrid metadata enrichment error]: {e}")

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
            try:
                ext = os.path.splitext(doc.filename)[1].lower()
                if ext == ".pdf" and not is_authentic_pdf:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        res_data["content"] = f.read()
                else:
                    from rag.parsers import parse_document_to_markdown
                    res_data["content"] = await asyncio.to_thread(parse_document_to_markdown, file_path)
            except Exception as e:
                res_data["content"] = f"Error reading document: {str(e)}"
        else:
            res_data["content"] = f"# {doc.title}\n\n*Document file is registered as a reference source.*"

        is_user_upload = (doc.journal_metric == "Uploaded Document" or doc.access_status == "Uploaded Document")
        res_data["is_uploaded"] = is_user_upload

        if is_user_upload:
            res_data["is_oa"] = False
            res_data["access_status"] = "Uploaded Document"
            res_data["has_full_pdf"] = is_authentic_pdf
            res_data["is_abstract_only"] = False
        elif is_authentic_pdf:
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
        
    raw_content = ""
    try:
        from rag.parsers import parse_document_to_markdown
        raw_content = await asyncio.to_thread(parse_document_to_markdown, file_path)
    except Exception as e:
        raw_content = f"Error reading document: {str(e)}"
        
    res_data["content"] = raw_content
    
    from utils.metadata_extractor import extract_heuristic_metadata, _GENERIC_HEADERS
    heuristics = extract_heuristic_metadata(raw_content, doc.filename)
    res_data["title"] = heuristics["title"]
    res_data["year"] = heuristics["year"]
    extracted_doi = heuristics["doi"]
    res_data["doi"] = extracted_doi
    res_data["url"] = heuristics["url"]
    local_abstract = heuristics["abstract"]
    clean_filename_title = heuristics["clean_filename_title"]

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
                    
    is_authentic_pdf = is_binary_pdf(file_path)

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
