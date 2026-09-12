"""
Response formatting and structured citation parser utilities for NotbookLM.
Deterministic payload handling without fragile regex heuristics.
"""

import re
import json
from typing import Tuple, Dict, Any


def is_negative_or_empty(val: str) -> bool:
    """Checks if cell text indicates an explicit absence or negative state."""
    clean = re.sub(r'[\(\)\[\]]', '', val.lower()).strip()
    return bool(
        not clean
        or re.search(r'^(tidak\s+(disebutkan|ada|eksplisit|tersedia)|belum\s+disebutkan|n/?a|-|\s*)$', clean)
        or 'tidak disebutkan' in clean
        or 'tidak terdapat' in clean
    )


def tag_cell_content(val: str, doc_num: str) -> str:
    """Attaches [doc_num] to each bullet point, line, or claim inside a table cell."""
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
                new_items.append(f'{it.rstrip()} [{doc_num}] ')
            else:
                new_items.append(it)
        return '•'.join(new_items).rstrip()

    return f'{val.rstrip()} [{doc_num}]'


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
                    # Row-mapped document table: if leading cell identifies Document [X], ensure remaining cells have [X]
                    first_cell = cells[0] if cells else ""
                    row_doc_match = re.search(r'\[(\d{1,3})\]', first_cell)
                    if row_doc_match and len(cells) > 1:
                        doc_num = row_doc_match.group(1)
                        new_cells = [first_cell]
                        for c in cells[1:]:
                            if re.search(r'\[\d{1,3}\]', c):
                                new_cells.append(c)
                            else:
                                new_cells.append(tag_cell_content(c, doc_num))
                        result_lines.append('| ' + ' | '.join(new_cells) + ' |')
                    else:
                        result_lines.append(line)
        else:
            in_table = False
            col_doc_map = {}
            result_lines.append(line)

    return '\n'.join(result_lines)


def format_clean_response(text: str) -> str:
    """Normalizes LLM response whitespace, standardizes citations, and formats citation blocks."""
    if not text:
        return ""
    text = text.strip()
    citation_data = None
    if "<!-- CITATION_MAP:" in text:
        parts = text.split("<!-- CITATION_MAP:", 1)
        text = parts[0].rstrip()
        citation_data = parts[1].split("-->", 1)[0].strip()

    # Automatically enhance table citations so every claim has clickable evidence
    text = enhance_table_citations(text)

    if citation_data:
        return f"{text}\n\n<!-- CITATION_MAP: {citation_data} -->"
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
