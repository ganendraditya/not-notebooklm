"""
Response formatting and structured citation parser utilities for NotbookLM.
Deterministic payload handling without fragile regex heuristics.
"""

import json
from typing import Tuple, Dict, Any


def format_clean_response(text: str) -> str:
    """Normalizes LLM response whitespace and standardizes structured citation blocks."""
    if not text:
        return ""
    text = text.strip()
    if "<!-- CITATION_MAP:" in text:
        parts = text.split("<!-- CITATION_MAP:", 1)
        body = parts[0].rstrip()
        citation_data = parts[1].split("-->", 1)[0].strip()
        return f"{body}\n\n<!-- CITATION_MAP: {citation_data} -->"
    return text


def extract_structured_citations(text: str) -> Tuple[str, Dict[str, Any]]:
    """Extracts citation map dictionary and clean markdown content deterministically."""
    if not text:
        return "", {}
    clean_text = text.strip()
    citations = {}
    if "<!-- CITATION_MAP:" in clean_text:
        parts = clean_text.split("<!-- CITATION_MAP:", 1)
        clean_text = parts[0].rstrip()
        raw_json = parts[1].split("-->", 1)[0].strip()
        try:
            citations = json.loads(raw_json)
        except Exception:
            pass
    return clean_text, citations
