import re
from typing import List, Dict, Any

CANONICAL_SECTION_PATTERNS = {
    "abstract": [
        re.compile(r'\b(?:abstract|abstrak|resumen|resume|overview|executive\s+summary)\b', re.IGNORECASE)
    ],
    "introduction": [
        re.compile(r'\b(?:introduction|pendahuluan|background|latar\s+belakang|overview|motivation)\b', re.IGNORECASE)
    ],
    "literature_review": [
        re.compile(r'\b(?:literature\s+review|related\s+work|kajian\s+pustaka|tinjauan\s+pustaka|theoretical\s+framework|state\s+of\s+the\s+art)\b', re.IGNORECASE)
    ],
    "methodology": [
        re.compile(r'\b(?:methods?|methodology|materials?\s+and\s+methods?|metode|metodologi|experimental\s+setup|study\s+design|protocol|data\s+collection|procedures?)\b', re.IGNORECASE)
    ],
    "results": [
        re.compile(r'\b(?:results?|findings?|hasil|hasil\s+penelitian|data\s+analysis|experimental\s+results?)\b', re.IGNORECASE)
    ],
    "discussion": [
        re.compile(r'\b(?:discussion|pembahasan|interpretation|implications?)\b', re.IGNORECASE)
    ],
    "conclusion": [
        re.compile(r'\b(?:conclusions?|kesimpulan|concluding\s+remarks|summary\s+and\s+conclusion|penutup)\b', re.IGNORECASE)
    ],
    "limitations": [
        re.compile(r'\b(?:limitations?|threats\s+to\s+validity|future\s+works?|limitasi|keterbatasan)\b', re.IGNORECASE)
    ],
    "references": [
        re.compile(r'\b(?:references|bibliography|daftar\s+pustaka|works\s+cited)\b', re.IGNORECASE)
    ]
}

def classify_canonical_section(header_title: str) -> str:
    """Classifies a section header into canonical academic IMRaD taxonomy."""
    if not header_title:
        return "general"
    clean_h = header_title.strip().lower()
    for cat, compiled_patterns in CANONICAL_SECTION_PATTERNS.items():
        for pat in compiled_patterns:
            if pat.search(clean_h):
                return cat
    return "general"

def split_markdown_into_academic_sections(markdown_text: str, filename: str = "") -> List[Dict[str, Any]]:
    """
    Parses Markdown extracted from PDFs/documents into hierarchical, section-aware chunks.
    Preserves tables, LaTeX formulas, breadcrumbs (Parent > Child), and canonical IMRaD tags.
    """
    if not markdown_text or not markdown_text.strip():
        return []

    lines = markdown_text.splitlines()
    sections = []
    
    # State tracking
    current_breadcrumbs = []
    current_lines = []
    current_level = 0
    in_code_or_table = False
    
    header_regex = re.compile(r'^(#{1,6})\s+(.+)$')
    # Bold paragraph header fallback: e.g. **1. Methods** or **Metodologi Penelitian** on isolated line
    bold_header_regex = re.compile(r'^\*\*(?:[0-9IVXABCDF\.\s\-:]+)?([A-Za-z0-9\s,\-\/]{3,70})\*\*:?\s*$')

    def flush_section(header_stack, content_lines, lvl):
        text_block = "\n".join(content_lines).strip()
        if not text_block:
            return
        
        breadcrumb_str = " > ".join([h[1] for h in header_stack]) if header_stack else "General / Overview"
        primary_header = header_stack[-1][1] if header_stack else "Overview"
        
        # Check canonical tag from primary header, or inherit from ancestor breadcrumbs
        canonical_tag = classify_canonical_section(primary_header)
        if canonical_tag == "general" and header_stack:
            for ancestor in reversed(header_stack[:-1]):
                ancestor_tag = classify_canonical_section(ancestor[1])
                if ancestor_tag != "general":
                    canonical_tag = ancestor_tag
                    break
        
        # Sizing and chunking
        # If block <= 3500 chars (~700 tokens), keep whole
        if len(text_block) <= 3500 or in_code_or_table:
            sections.append({
                "breadcrumb": breadcrumb_str,
                "section": primary_header,
                "canonical_section": canonical_tag,
                "text": f"[{filename} | Section: {breadcrumb_str}]\n\n{text_block}" if filename else f"[Section: {breadcrumb_str}]\n\n{text_block}",
                "raw_text": text_block
            })
        else:
            # Paragraph-aware split for long sections
            paragraphs = re.split(r'\n\s*\n', text_block)
            curr_chunk = []
            curr_len = 0
            part_idx = 1
            
            for p in paragraphs:
                p_clean = p.strip()
                if not p_clean:
                    continue
                if curr_len + len(p_clean) > 2800 and curr_chunk:
                    chunk_body = "\n\n".join(curr_chunk)
                    prefix = f"[{filename} | Section: {breadcrumb_str} (Part {part_idx})]" if filename else f"[Section: {breadcrumb_str} (Part {part_idx})]"
                    sections.append({
                        "breadcrumb": breadcrumb_str,
                        "section": primary_header,
                        "canonical_section": canonical_tag,
                        "text": f"{prefix}\n\n{chunk_body}",
                        "raw_text": chunk_body
                    })
                    part_idx += 1
                    # Overlap: retain last paragraph if reasonable
                    if len(curr_chunk[-1]) < 600:
                        curr_chunk = [curr_chunk[-1], p_clean]
                        curr_len = len(curr_chunk[0]) + len(p_clean)
                    else:
                        curr_chunk = [p_clean]
                        curr_len = len(p_clean)
                else:
                    curr_chunk.append(p_clean)
                    curr_len += len(p_clean) + 2
                    
            if curr_chunk:
                chunk_body = "\n\n".join(curr_chunk)
                prefix = f"[{filename} | Section: {breadcrumb_str} (Part {part_idx})]" if part_idx > 1 and filename else (f"[{filename} | Section: {breadcrumb_str}]" if filename else f"[Section: {breadcrumb_str}]")
                sections.append({
                    "breadcrumb": breadcrumb_str,
                    "section": primary_header,
                    "canonical_section": canonical_tag,
                    "text": f"{prefix}\n\n{chunk_body}",
                    "raw_text": chunk_body
                })

    for line in lines:
        stripped = line.strip()
        
        # Detect table borders or code blocks to preserve them intact
        if stripped.startswith("```"):
            in_code_or_table = not in_code_or_table
            current_lines.append(line)
            continue
            
        if in_code_or_table:
            current_lines.append(line)
            continue

        h_match = header_regex.match(stripped)
        bold_match = bold_header_regex.match(stripped) if not h_match else None
        
        if h_match:
            hashes, title = h_match.group(1), h_match.group(2).strip()
            level = len(hashes)
            
            # Flush previous collected content
            if current_lines:
                flush_section(current_breadcrumbs, current_lines, current_level)
                current_lines = []
                
            # Update breadcrumbs stack according to markdown heading level
            while current_breadcrumbs and current_breadcrumbs[-1][0] >= level:
                current_breadcrumbs.pop()
            current_breadcrumbs.append((level, title))
            current_level = level
            
        elif bold_match and len(current_lines) > 0 and len(stripped) < 80:
            title = bold_match.group(1).strip()
            # If line is an isolated bold heading (e.g. **Methods** or **3. Discussion**)
            level = current_level + 1 if current_level > 0 else 2
            
            if current_lines:
                flush_section(current_breadcrumbs, current_lines, current_level)
                current_lines = []
                
            while current_breadcrumbs and current_breadcrumbs[-1][0] >= level:
                current_breadcrumbs.pop()
            current_breadcrumbs.append((level, title))
            current_level = level
        else:
            current_lines.append(line)

    if current_lines:
        flush_section(current_breadcrumbs, current_lines, current_level)

    # Fallback if no sections extracted
    if not sections:
        sections.append({
            "breadcrumb": "Document Content",
            "section": "Document Content",
            "canonical_section": "general",
            "text": f"[{filename}]\n\n{markdown_text}" if filename else markdown_text,
            "raw_text": markdown_text
        })
        
    return sections
