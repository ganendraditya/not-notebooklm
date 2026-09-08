import os
import re
from typing import Dict, Any

_GENERIC_HEADERS = {
    "abstract", "abstrak", "overview", "paper", "document", "introduction", "keywords",
    "article in press", "in press", "journal pre-proof", "uncorrected proof",
    "corrected proof", "original article", "research article", "full length article",
    "short communication", "review article", "full paper", "research paper",
    "accepted manuscript", "author's copy",
}


def extract_heuristic_metadata(raw_content: str, filename: str) -> Dict[str, Any]:
    """
    Pure heuristic metadata extractor from document raw markdown text.
    Extracts title, publication year, DOI, URL, and abstract without side-effects.
    """
    clean_filename_title = re.sub(r'<[^>]+>', '', os.path.splitext(filename)[0]).replace("_", " ").strip()

    # 1. Title & Year extraction
    extracted_title = clean_filename_title
    extracted_year = ""
    title_match = re.search(r"#+\s*\**([^\n\*]+)\**", raw_content)
    if title_match:
        cand_title = title_match.group(1).strip()
        year_in_title = re.search(r"\((\d{4})\)$", cand_title)
        if year_in_title:
            extracted_year = year_in_title.group(1)
            cand_title = cand_title[:year_in_title.start()].strip()
        cand_title = re.sub(r'<[^>]+>', '', cand_title).strip()
        if cand_title and cand_title.lower() not in _GENERIC_HEADERS:
            extracted_title = cand_title

    clean_filename_title = re.sub(r'<[^>]+>', '', clean_filename_title).strip()
    if not extracted_title or extracted_title.lower() in _GENERIC_HEADERS:
        extracted_title = clean_filename_title

    # 2. DOI & URL extraction
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

    extracted_url = ""
    url_match = re.search(r"URL:\*?\*?\s*([^\s\n\*\)]+)", header_scope, re.I)
    if url_match:
        extracted_url = url_match.group(1).strip()
    elif extracted_doi:
        extracted_url = f"https://doi.org/{extracted_doi}"

    # 3. Abstract extraction
    local_abstract = ""
    try:
        from rag.parsers import split_markdown_into_academic_sections
        doc_sections = split_markdown_into_academic_sections(raw_content, filename=filename)
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

    return {
        "title": extracted_title,
        "clean_filename_title": clean_filename_title,
        "year": extracted_year,
        "doi": extracted_doi,
        "url": extracted_url,
        "abstract": local_abstract,
        "is_generic_title": extracted_title.lower() in _GENERIC_HEADERS
    }
