import re
import json
import logging
from typing import Dict, List, Optional, Tuple, Any
from pydantic import BaseModel, Field
from difflib import SequenceMatcher

logger = logging.getLogger("uvicorn.error")


class CitationFidelityReport(BaseModel):
    """
    Deterministic evaluation report of interactive citation fidelity.
    Calculated purely via Python mathematics and string matching (0 LLM tokens).
    """
    ieee_syntax_score: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Ratio of citation tags properly placed BEFORE sentence periods (e.g. 'fakta [1].' vs 'fakta. [1]')."
    )
    citation_map_present: bool = Field(
        default=True,
        description="True if the mandatory <!-- CITATION_MAP --> payload is present and parseable."
    )
    total_tags_found: int = Field(
        default=0,
        description="Total distinct document citation tags found in draft body (e.g. [1], [2])."
    )
    total_quotes_checked: int = Field(
        default=0,
        description="Total verbatim sentence quotes extracted from CITATION_MAP for audit."
    )
    quotes_verified: int = Field(
        default=0,
        description="Number of quotes confirmed to exist authentically in the physical source document text."
    )
    verbatim_fidelity_score: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Fidelity ratio = quotes_verified / total_quotes_checked (1.0 = 100% authentic quotes)."
    )
    syntax_violations: List[str] = Field(
        default_factory=list,
        description="Specific sentences where citation tag was improperly placed after period."
    )
    unmatched_quotes: List[str] = Field(
        default_factory=list,
        description="Quotes claimed in CITATION_MAP that could NOT be located in the source documents."
    )


def _normalize_text_for_search(text: str) -> str:
    """Normalizes whitespace, line breaks, and common ligatures for robust string matching."""
    cleaned = re.sub(r'[\r\n\t]+', ' ', text)
    cleaned = re.sub(r'\s+', ' ', cleaned)
    # Remove soft hyphens and normalize quotes
    cleaned = cleaned.replace('\xad', '').replace('“', '"').replace('”', '"').replace('’', "'")
    return cleaned.strip().lower()


def is_quote_in_document(quote: str, doc_text: str, fuzzy_threshold: float = 0.85) -> bool:
    """
    Checks if a quote exists in the source document.
    Uses fast exact normalized substring search first, then token-based sliding fuzzy match if needed.
    """
    clean_quote = _normalize_text_for_search(quote)
    if not clean_quote or len(clean_quote) < 15:
        return True  # Ignore trivially short phrases

    clean_doc = _normalize_text_for_search(doc_text)
    
    # 1. Exact normalized substring match (covers ~90% of authentic extracts)
    if clean_quote in clean_doc:
        return True

    # 2. Key phrases anchor match (handles minor OCR line break discrepancies)
    words = clean_quote.split()
    if len(words) >= 6:
        anchor_prefix = " ".join(words[:4])
        anchor_suffix = " ".join(words[-4:])
        if anchor_prefix in clean_doc and anchor_suffix in clean_doc:
            return True

    # 3. Token-ratio sliding window fuzzy match for tricky PDF column wraps
    quote_len = len(clean_quote)
    step = max(50, quote_len // 2)
    for i in range(0, max(1, len(clean_doc) - quote_len), step):
        window = clean_doc[i : i + quote_len + 50]
        ratio = SequenceMatcher(None, clean_quote, window).quick_ratio()
        if ratio >= fuzzy_threshold:
            return True

    return False


def verify_citation_fidelity(
    generated_text: str,
    source_documents_map: Dict[str, str]
) -> CitationFidelityReport:
    """
    Performs deterministic audit of citations in generated response against source document contents.
    
    Args:
        generated_text: Full response string from LLM, possibly containing <!-- CITATION_MAP: ... -->
        source_documents_map: Dictionary mapping document index key (e.g. "1", "2") to raw document text.
    
    Returns:
        CitationFidelityReport containing exact scores and violation lists.
    """
    report = CitationFidelityReport()

    # 1. Extract raw body and CITATION_MAP payload
    map_match = re.search(r'<!--\s*CITATION_MAP:\s*(\{.*?\})\s*-->', generated_text, re.DOTALL)
    body_text = generated_text
    citation_map_dict = {}

    if map_match:
        body_text = generated_text[:map_match.start()].strip()
        raw_json_str = map_match.group(1).strip()
        try:
            citation_map_dict = json.loads(raw_json_str)
            report.citation_map_present = True
        except Exception as e:
            logger.warning(f"[CitationVerifier] Failed to parse CITATION_MAP JSON: {e}")
            report.citation_map_present = False
    else:
        # Check if citations were present in body without map
        has_citations_in_body = bool(re.search(r'\[\d+\]', generated_text))
        report.citation_map_present = not has_citations_in_body

    # 2. Audit IEEE Syntax: check for citations placed AFTER period (e.g. "kalimat. [1]")
    # Bad pattern: a period immediately followed by optional space then [digit]
    bad_syntax_matches = re.findall(r'(\b\w+\.\s*\[\d+\])', body_text)
    total_tag_instances = len(re.findall(r'\[\d+\]', body_text))
    
    if total_tag_instances > 0:
        bad_count = len(bad_syntax_matches)
        valid_count = max(0, total_tag_instances - bad_count)
        report.ieee_syntax_score = round(valid_count / total_tag_instances, 3)
        report.syntax_violations = bad_syntax_matches[:5]
    else:
        report.ieee_syntax_score = 1.0

    # 3. Collect all declared distinct citation tags
    distinct_tags = set(re.findall(r'\[(\d+)\]', body_text))
    report.total_tags_found = len(distinct_tags)

    # 4. Audit verbatim sentence fidelity against source documents
    total_quotes = 0
    verified_quotes = 0
    unmatched_list = []

    for doc_key, quotes in citation_map_dict.items():
        doc_key_clean = str(doc_key).strip("[]")
        doc_raw_text = source_documents_map.get(doc_key_clean, "")
        
        quote_items = quotes if isinstance(quotes, list) else [quotes]
        for q in quote_items:
            if not isinstance(q, str) or not q.strip():
                continue
            total_quotes += 1
            if doc_raw_text and is_quote_in_document(q, doc_raw_text):
                verified_quotes += 1
            else:
                unmatched_list.append(f"Doc [{doc_key_clean}]: \"{q[:100]}...\"")

    report.total_quotes_checked = total_quotes
    report.quotes_verified = verified_quotes
    report.unmatched_quotes = unmatched_list

    if total_quotes > 0:
        report.verbatim_fidelity_score = round(verified_quotes / total_quotes, 3)
    else:
        # If no citations were needed / declared and no quotes given, default to 1.0
        report.verbatim_fidelity_score = 1.0 if not distinct_tags else 0.0

    return report
