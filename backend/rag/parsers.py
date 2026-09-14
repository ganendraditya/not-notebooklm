import os
import hashlib
import logging
from collections import OrderedDict
from typing import Optional
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

logger = logging.getLogger(__name__)

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

def get_disk_cache_path(file_path: str) -> Optional[str]:
    """Generates a stable cache file path in .parsed_cache based on file content/stat fingerprint."""
    try:
        from utils.file_utils import PARSED_CACHE_DIR
        cache_key = get_file_cache_key(file_path)
        hashed_name = hashlib.sha256(cache_key.encode("utf-8")).hexdigest()
        return os.path.join(PARSED_CACHE_DIR, f"{hashed_name}.parsed.md")
    except Exception:
        return None

def parse_document_to_markdown(file_path: str) -> str:
    """
    Parses any supported document format into Markdown text with dual-tier caching:
    1. In-memory bounded LRU cache (0ms)
    2. Persistent disk cache (.parsed_cache, <5ms)
    """
    cache_key = get_file_cache_key(file_path)
    if cache_key in _PARSED_MARKDOWN_CACHE:
        _PARSED_MARKDOWN_CACHE.move_to_end(cache_key)
        return _PARSED_MARKDOWN_CACHE[cache_key]

    # Check persistent disk cache before invoking expensive CPU parsers
    disk_cache_file = get_disk_cache_path(file_path)
    if disk_cache_file and os.path.exists(disk_cache_file):
        try:
            with open(disk_cache_file, "r", encoding="utf-8", errors="replace") as cf:
                disk_text = cf.read()
            if disk_text and disk_text.strip():
                _PARSED_MARKDOWN_CACHE[cache_key] = disk_text
                if len(_PARSED_MARKDOWN_CACHE) > _MAX_PARSED_CACHE_SIZE:
                    _PARSED_MARKDOWN_CACHE.popitem(last=False)
                return disk_text
        except Exception as e:
            logger.debug(f"[Parsed Cache Disk Read Error]: {e}")

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
            # Enforce natural multi-column academic reading order (Column 1 top-to-bottom, then Column 2)
            # Prevents right-column headers (e.g. REFERENCES) from prematurely interrupting left-column sections
            pymupdf4llm.use_layout(False)
            md_text = pymupdf4llm.to_markdown(file_path)
        except Exception:
            # Fallback to plain PyMuPDF text extraction if pymupdf4llm parser fails
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
        
    # Persist parsed markdown to disk cache for instantaneous re-loads across restarts/refreshes
    if disk_cache_file:
        try:
            tmp_cache = f"{disk_cache_file}.tmp_{os.getpid()}"
            with open(tmp_cache, "w", encoding="utf-8") as cf:
                cf.write(md_text)
            os.replace(tmp_cache, disk_cache_file)
        except Exception as e:
            logger.debug(f"[Parsed Cache Disk Write Error]: {e}")

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
