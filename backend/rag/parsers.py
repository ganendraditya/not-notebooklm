import os
import re
import pymupdf4llm

def parse_docx_file(file_path: str) -> str:
    """Extracts text and tables from Word (.docx/.doc) document as clean Markdown with multi-layer fallback."""
    # Method 1: Standard python-docx parser
    try:
        import docx
        doc = docx.Document(file_path)
        lines = []
        for p in doc.paragraphs:
            text = p.text.strip()
            if text:
                style_name = ""
                try:
                    style_name = p.style.name.lower() if p.style and hasattr(p.style, 'name') else ""
                except Exception:
                    style_name = ""
                if 'heading 1' in style_name:
                    lines.append(f"\n# {text}\n")
                elif 'heading 2' in style_name:
                    lines.append(f"\n## {text}\n")
                elif 'heading 3' in style_name:
                    lines.append(f"\n### {text}\n")
                else:
                    lines.append(text)
        for tbl in doc.tables:
            lines.append("\n")
            for row_idx, row in enumerate(tbl.rows):
                row_cells = [cell.text.strip().replace('\n', ' ') for cell in row.cells]
                lines.append("| " + " | ".join(row_cells) + " |")
                if row_idx == 0:
                    lines.append("| " + " | ".join(['---'] * len(row_cells)) + " |")
            lines.append("\n")
        res = "\n\n".join(lines).strip()
        if res and len(res) > 20:
            return res
    except Exception as e:
        print(f"[RAG Parsers] Warning: python-docx parser failed ({e}), attempting XML zip fallback...")

    # Method 2: Direct word/document.xml extraction from ZIP archive
    try:
        import zipfile
        import xml.etree.ElementTree as ET
        with zipfile.ZipFile(file_path) as z:
            if "word/document.xml" in z.namelist():
                xml_content = z.read("word/document.xml")
                tree = ET.fromstring(xml_content)
                text_pieces = []
                for node in tree.iter():
                    if node.tag.endswith('}t') and node.text:
                        text_pieces.append(node.text)
                    elif node.tag.endswith('}p'):
                        text_pieces.append("\n")
                res_xml = "".join(text_pieces).strip()
                if res_xml and len(res_xml) > 20:
                    return res_xml
    except Exception as e:
        print(f"[RAG Parsers] Warning: XML zip extraction failed ({e}), attempting PyMuPDF fallback...")

    # Method 3: PyMuPDF document text reader
    try:
        import pymupdf
        doc = pymupdf.open(file_path)
        pages_text = [page.get_text() for page in doc]
        doc.close()
        res_mupdf = "\n\n".join(pages_text).strip()
        if res_mupdf and len(res_mupdf) > 20:
            return res_mupdf
    except Exception as e:
        print(f"[RAG Parsers] Warning: PyMuPDF reader fallback failed: {e}")

    return ""

def parse_bibtex_text(text: str) -> str:
    """Converts BibTeX bibliographic references into clean structured Markdown summaries."""
    entries = []
    raw_entries = re.findall(r'@(\w+)\s*\{\s*([^,]+),([\s\S]*?)\n\}', text, re.IGNORECASE)
    for entry_type, key, body in raw_entries:
        fields = {}
        for m in re.finditer(r'(\w+)\s*=\s*(?:\{([\s\S]*?)\}|"([\s\S]*?)"|(\w+))', body):
            k = m.group(1).lower()
            v = m.group(2) if m.group(2) is not None else (m.group(3) if m.group(3) is not None else m.group(4))
            if v:
                fields[k] = re.sub(r'\s+', ' ', v.strip())
        title = fields.get('title', key)
        author = fields.get('author', 'Unknown Author')
        year = fields.get('year', '')
        journal = fields.get('journal', fields.get('booktitle', ''))
        doi = fields.get('doi', '')
        abstract = fields.get('abstract', '')
        md_entry = f"### {title}\n- **Authors**: {author}\n"
        if year: md_entry += f"- **Year**: {year}\n"
        if journal: md_entry += f"- **Journal/Venue**: {journal}\n"
        if doi: md_entry += f"- **DOI**: [{doi}](https://doi.org/{doi})\n"
        if abstract: md_entry += f"- **Abstract**: {abstract}\n"
        entries.append(md_entry)
    return "\n\n---\n\n".join(entries) if entries else text

def parse_ris_text(text: str) -> str:
    """Converts RIS citation library format into clean structured Markdown summaries."""
    entries = []
    current_entry = {}
    authors = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("ER  -"):
            if current_entry:
                title = current_entry.get("TI", current_entry.get("T1", "Untitled Work"))
                year = current_entry.get("PY", current_entry.get("Y1", ""))
                journal = current_entry.get("JO", current_entry.get("JF", current_entry.get("T2", "")))
                doi = current_entry.get("DO", "")
                abstract = current_entry.get("AB", current_entry.get("N2", ""))
                md_entry = f"### {title}\n"
                if authors: md_entry += f"- **Authors**: {', '.join(authors)}\n"
                if year: md_entry += f"- **Year**: {year}\n"
                if journal: md_entry += f"- **Journal/Venue**: {journal}\n"
                if doi: md_entry += f"- **DOI**: [{doi}](https://doi.org/{doi})\n"
                if abstract: md_entry += f"- **Abstract**: {abstract}\n"
                entries.append(md_entry)
            current_entry = {}
            authors = []
        elif line[:6].endswith("- "):
            tag = line[:2].strip()
            val = line[6:].strip()
            if tag in ("AU", "A1"):
                authors.append(val)
            else:
                current_entry[tag] = val
    return "\n\n---\n\n".join(entries) if entries else text

def parse_csv_file(file_path: str) -> str:
    """Formats CSV/TSV table into readable Markdown table."""
    try:
        import csv
        delimiter = '\t' if file_path.lower().endswith('.tsv') else ','
        lines = []
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            reader = csv.reader(f, delimiter=delimiter)
            for idx, row in enumerate(reader):
                clean_row = [c.strip().replace('\n', ' ') for c in row]
                lines.append("| " + " | ".join(clean_row) + " |")
                if idx == 0:
                    lines.append("| " + " | ".join(['---'] * len(clean_row)) + " |")
        return "\n".join(lines)
    except Exception as e:
        print(f"[RAG Parsers] CSV parse error: {e}")
        return ""

CANONICAL_SECTION_PATTERNS = {
    "abstract": [
        r'\b(?:abstract|abstrak|resumen|resume|overview|executive\s+summary)\b'
    ],
    "introduction": [
        r'\b(?:introduction|pendahuluan|background|latar\s+belakang|overview|motivation)\b'
    ],
    "literature_review": [
        r'\b(?:literature\s+review|related\s+work|kajian\s+pustaka|tinjauan\s+pustaka|theoretical\s+framework|state\s+of\s+the\s+art)\b'
    ],
    "methodology": [
        r'\b(?:methods?|methodology|materials?\s+and\s+methods?|metode|metodologi|experimental\s+setup|study\s+design|protocol|data\s+collection|procedures?)\b'
    ],
    "results": [
        r'\b(?:results?|findings?|hasil|hasil\s+penelitian|data\s+analysis|experimental\s+results?)\b'
    ],
    "discussion": [
        r'\b(?:discussion|pembahasan|interpretation|implications?)\b'
    ],
    "conclusion": [
        r'\b(?:conclusions?|kesimpulan|concluding\s+remarks|summary\s+and\s+conclusion|penutup)\b'
    ],
    "limitations": [
        r'\b(?:limitations?|threats\s+to\s+validity|future\s+works?|limitasi|keterbatasan)\b'
    ],
    "references": [
        r'\b(?:references|bibliography|daftar\s+pustaka|works\s+cited)\b'
    ]
}

def classify_canonical_section(header_title: str) -> str:
    """Classifies a section header into canonical academic IMRaD taxonomy."""
    if not header_title:
        return "general"
    clean_h = header_title.strip().lower()
    for cat, patterns in CANONICAL_SECTION_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, clean_h, re.IGNORECASE):
                return cat
    return "general"

def split_markdown_into_academic_sections(markdown_text: str, filename: str = "") -> list:
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

_PARSED_MARKDOWN_CACHE = {}

def get_file_cache_key(file_path: str) -> str:
    try:
        mtime = os.path.getmtime(file_path)
        fsize = os.path.getsize(file_path)
        return f"{file_path}_{mtime}_{fsize}"
    except Exception:
        return file_path

def parse_document_to_markdown(file_path: str) -> str:
    """Parses any supported document format into Markdown text with in-memory caching."""
    cache_key = get_file_cache_key(file_path)
    if cache_key in _PARSED_MARKDOWN_CACHE:
        return _PARSED_MARKDOWN_CACHE[cache_key]

    ext = os.path.splitext(file_path)[1].lower()
    filename = os.path.basename(file_path)
    
    if ext == ".pdf":
        md_text = pymupdf4llm.to_markdown(file_path)
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
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            md_text = f.read()
            
    if not md_text or not md_text.strip():
        raise ValueError(f"Could not extract readable text from {filename}")
        
    _PARSED_MARKDOWN_CACHE[cache_key] = md_text
    return md_text
