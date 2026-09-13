"""
Response formatting and structured citation parser utilities for NotbookLM.
Deterministic payload handling without fragile regex heuristics.
"""

import re
import json
from typing import Tuple, Dict, Any


def is_negative_or_empty(val: str) -> bool:
    """Checks if cell text indicates an explicit absence or negative state."""
    clean = re.sub(r'[\(\)\[\]*`_]', '', val.lower()).strip()
    return bool(
        not clean
        or re.search(r'^(tidak\s+(disebutkan|dijelaskan|dibahas|tercantum|ada|eksplisit|tersedia)|belum\s+disebutkan|not\s+(explicitly\s+)?(stated|mentioned|discussed|reported)|unspecified|none\s+stated|n/?a|-|\s*)$', clean)
        or 'tidak disebutkan' in clean
        or 'tidak dijelaskan' in clean
        or 'tidak dibahas' in clean
        or 'tidak terdapat' in clean
        or 'not explicitly stated' in clean
        or 'not mentioned' in clean
    )


def attach_cite_before_period(text: str, doc_num: str) -> str:
    """Attaches [doc_num] before any trailing sentence-ending period (IEEE format)."""
    s = text.rstrip()
    if s.endswith('.'):
        return f"{s[:-1].rstrip()} [{doc_num}]."
    return f"{s} [{doc_num}]"


def tag_cell_content(val: str, doc_num: str) -> str:
    """Attaches [doc_num] to each bullet point, line, or claim inside a table cell before punctuation."""
    if not val.strip() or is_negative_or_empty(val) or f'[{doc_num}]' in val:
        return val

    # Split by HTML line breaks
    if re.search(r'<br\s*/?>', val, re.I):
        parts = re.split(r'(<br\s*/?>)', val, flags=re.I)
        new_parts = []
        for p in parts:
            if re.match(r'^<br\s*/?>$', p, re.I):
                new_parts.append(p)
            elif p.strip() and not is_negative_or_empty(p) and f'[{doc_num}]' not in p:
                new_parts.append(tag_cell_content(p, doc_num))
            else:
                new_parts.append(p)
        return ''.join(new_parts)

    # Split by bullet symbol •
    if '•' in val:
        items = val.split('•')
        new_items = []
        for it in items:
            if not it.strip():
                new_items.append(it)
            elif not is_negative_or_empty(it) and f'[{doc_num}]' not in it:
                new_items.append(f'{attach_cite_before_period(it, doc_num)} ')
            else:
                new_items.append(it)
        return '•'.join(new_items).rstrip()

    return attach_cite_before_period(val, doc_num)


def enhance_table_citations(text: str) -> str:
    """
    Intelligently injects [X] citation tags into table cells and bullet points
    if column headers or row headers specify Document [X], ensuring interactive
    evidence buttons always appear on every factual claim and metric.
    """
    if not text or '|' not in text:
        return text

    lines = text.split('\n')
    in_table = False
    col_doc_map = {}
    result_lines = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith('|') and stripped.endswith('|'):
            cells = [c.strip() for c in stripped.split('|')[1:-1]]
            if not in_table:
                in_table = True
                col_doc_map = {}
                for idx, c in enumerate(cells):
                    m = re.search(r'\[(\d{1,3})\]', c)
                    if m:
                        col_doc_map[idx] = m.group(1)
                result_lines.append(line)
            elif all(re.match(r'^:?-+:?$', c) for c in cells):
                result_lines.append(line)
            else:
                if col_doc_map:
                    # Column-mapped document table
                    new_cells = []
                    for idx, c in enumerate(cells):
                        if idx in col_doc_map:
                            if re.search(r'\[\d{1,3}\]', c):
                                new_cells.append(c)
                            else:
                                new_cells.append(tag_cell_content(c, col_doc_map[idx]))
                        else:
                            new_cells.append(c)
                    result_lines.append('| ' + ' | '.join(new_cells) + ' |')
                else:
                    result_lines.append(line)
        else:
            in_table = False
            col_doc_map = {}
            result_lines.append(line)

    return '\n'.join(result_lines)


def deduplicate_line_citations(text: str) -> str:
    """
    Standardizes academic citations by removing redundant duplicate citations on the same line
    (e.g. '1. **[5]** Title (2023) [5]' -> '1. Title (2023) [5]' or '[1] Text... [1]' -> 'Text... [1]').
    """
    if not text:
        return ""
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        # Match leading bullet/number followed by bracketed citation like '1. **[5]**' or '- [5]' or '[5]'
        m = re.match(r'^(\s*(?:\d+[\.\)]|\*|-)?\s*)\*{0,2}\[(\d{1,3})\]\*{0,2}\s*(.*)$', line)
        if m:
            prefix, doc_num, rest = m.groups()
            # If the rest of the line already contains [doc_num], remove the leading duplicate tag
            if f'[{doc_num}]' in rest:
                line = f"{prefix}{rest.lstrip('-: ')}"
        cleaned_lines.append(line)
    return '\n'.join(cleaned_lines)


def format_clean_response(text: str) -> str:
    """Normalizes LLM response whitespace, standardizes citations, and formats citation blocks."""
    if not text:
        return ""
    text = text.strip()
    
    # Ensure separator rows concatenated with header row on the same line (e.g. '... || --- |') are split cleanly
    text = re.sub(r'\|\s*\|(\s*:?-+:?\s*\|)', r'|\n|\1', text)

    citation_data = None
    
    # Match CITATION_MAP with or without colon and flexible whitespace
    m = re.search(r'<!--\s*CITATION_MAP(?::|\s)([\s\S]*?)(?:-->|$)', text, re.IGNORECASE)
    if m:
        raw_data = m.group(1).strip().lstrip(":").strip()
        # Clean markdown code fences like ```json ... ``` or ``` ... ```
        cleaned_json = re.sub(r'^```(?:json)?\s*', '', raw_data, flags=re.IGNORECASE)
        cleaned_json = re.sub(r'\s*```$', '', cleaned_json).strip()
        first_brace = cleaned_json.find('{')
        last_brace = cleaned_json.rfind('}')
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            citation_data = cleaned_json[first_brace:last_brace+1]
        text = text[:m.start()].rstrip()

    # Strip any malformed or non-JSON CITATION_MAP comment blocks completely
    text = re.sub(r'<!--\s*CITATION_MAP[\s\S]*?(?:-->|$)', '', text, flags=re.IGNORECASE).rstrip()

    # Automatically enhance table citations so every claim has clickable evidence
    text = enhance_table_citations(text)

    # Clean double citations on the same line (e.g. [1] Text... [1] -> Text... [1])
    text = deduplicate_line_citations(text)

    # IEEE citation placement rule: ensure citations appear BEFORE the period, not after!
    # e.g. 'terjadi). [20]' -> 'terjadi) [20].' and 'metode. [1]' -> 'metode [1].'
    text = re.sub(r'\.(\s*)(\[{1,2}\d{1,3}(?:\s*,\s*\d{1,3})*\]{1,2})', r' \2.', text)
    text = re.sub(r'(\[{1,2}\d{1,3}(?:\s*,\s*\d{1,3})*\]{1,2})\s*\.{2,}', r'\1.', text)

    if citation_data:
        return f"{text}\n\n<!-- CITATION_MAP: {citation_data} -->"
    return text


def extract_structured_citations(text: str) -> Tuple[str, Dict[str, Any]]:
    """Extracts citation map dictionary and clean markdown content deterministically."""
    if not text:
        return "", {}
    clean_text = text.strip()
    citations = {}
    m = re.search(r'<!--\s*CITATION_MAP(?::|\s)([\s\S]*?)(?:-->|$)', clean_text, re.IGNORECASE)
    if m:
        raw_json = m.group(1).strip().lstrip(":").strip()
        clean_text = clean_text[:m.start()].rstrip()
        try:
            cleaned = re.sub(r'^```(?:json)?\s*', '', raw_json, flags=re.IGNORECASE)
            cleaned = re.sub(r'\s*```$', '', cleaned).strip()
            first_brace = cleaned.find('{')
            last_brace = cleaned.rfind('}')
            if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                cleaned = cleaned[first_brace:last_brace+1]
            citations = json.loads(cleaned)
        except Exception:
            pass
    clean_text = re.sub(r'<!--\s*CITATION_MAP[\s\S]*?(?:-->|$)', '', clean_text, flags=re.IGNORECASE).rstrip()
    return clean_text, citations
