import os
from collections import OrderedDict
import pymupdf4llm

from .format_parsers import (
    parse_docx_file,
    parse_bibtex_text,
    parse_ris_text,
    parse_csv_file,
)
from .academic_chunker import (
    CANONICAL_SECTION_PATTERNS,
    CANONICAL_SEMANTIC_ANCHORS,
    classify_canonical_section,
    split_markdown_into_academic_sections,
)

# Bounded LRU cache for parsed markdown content (prevents unbounded memory leak)
_MAX_PARSED_CACHE_SIZE = 200
_PARSED_MARKDOWN_CACHE: OrderedDict = OrderedDict()

def get_file_cache_key(file_path: str) -> str:
    try:
        mtime = os.path.getmtime(file_path)
        fsize = os.path.getsize(file_path)
        return f"{file_path}_{mtime}_{fsize}"
    except Exception:
        return file_path

def parse_document_to_markdown(file_path: str) -> str:
    """Parses any supported document format into Markdown text with in-memory bounded LRU caching."""
    cache_key = get_file_cache_key(file_path)
    if cache_key in _PARSED_MARKDOWN_CACHE:
        _PARSED_MARKDOWN_CACHE.move_to_end(cache_key)
        return _PARSED_MARKDOWN_CACHE[cache_key]

    ext = os.path.splitext(file_path)[1].lower()
    filename = os.path.basename(file_path)
    
    # Check if the file is secretly a binary PDF regardless of its extension (.txt, .tmp, etc.)
    is_binary_pdf = False
    if os.path.exists(file_path) and os.path.getsize(file_path) >= 10:
        try:
            with open(file_path, "rb") as f:
                magic_bytes = f.read(1024)
                if magic_bytes.startswith(b"%PDF-") or b"%PDF-" in magic_bytes[:1024]:
                    is_binary_pdf = True
        except Exception:
            pass

    md_text = ""
    if ext == ".pdf" or is_binary_pdf:
        try:
            md_text = pymupdf4llm.to_markdown(file_path)
        except Exception:
            # Fallback to plain PyMuPDF text extraction if pymupdf4llm layout parser fails
            try:
                import pymupdf
                doc = pymupdf.open(file_path)
                if len(doc) > 0:
                    pages_text = [page.get_text() for page in doc]
                    doc.close()
                    md_text = "\n\n".join(pages_text)
                else:
                    md_text = ""
            except Exception:
                md_text = ""
                
        # If PyMuPDF fails completely on a binary PDF, do NOT fallback to reading it as text
        if is_binary_pdf and not md_text:
            md_text = ""
             
    elif ext in (".docx", ".doc"):
        md_text = parse_docx_file(file_path)
    elif ext in (".bib", ".bibtex"):
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            md_text = parse_bibtex_text(f.read())
    elif ext == ".ris":
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            md_text = parse_ris_text(f.read())
    elif ext in (".csv", ".tsv"):
        md_text = parse_csv_file(file_path)
    else:
        # If it wasn't a known binary format or secretly a binary PDF, try text
        if not is_binary_pdf:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                md_text = f.read()
        else:
            md_text = ""
            
    if not md_text or not md_text.strip():
        raise ValueError(f"Could not extract readable text from {filename}")
        
    _PARSED_MARKDOWN_CACHE[cache_key] = md_text
    if len(_PARSED_MARKDOWN_CACHE) > _MAX_PARSED_CACHE_SIZE:
        _PARSED_MARKDOWN_CACHE.popitem(last=False)
    return md_text

__all__ = [
    "parse_docx_file",
    "parse_bibtex_text",
    "parse_ris_text",
    "parse_csv_file",
    "CANONICAL_SECTION_PATTERNS",
    "CANONICAL_SEMANTIC_ANCHORS",
    "classify_canonical_section",
    "split_markdown_into_academic_sections",
    "get_file_cache_key",
    "parse_document_to_markdown",
]
