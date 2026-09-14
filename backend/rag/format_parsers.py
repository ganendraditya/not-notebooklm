import re

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
        print(f"[RAG Format Parsers] Warning: python-docx parser failed ({e}), attempting XML zip fallback...")

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
        print(f"[RAG Format Parsers] Warning: XML zip extraction failed ({e}), attempting PyMuPDF fallback...")

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
        print(f"[RAG Format Parsers] Warning: PyMuPDF reader fallback failed: {e}")

    return ""

def extract_bibtex_entries(text: str) -> list:
    """
    Extracts structured bibliographic entries from BibTeX content.
    Handles nested braces in fields, multiple authors, and clean metadata extraction.
    """
    entries = []
    entry_start_regex = re.compile(r'@([a-zA-Z]+)\s*([\{\(])\s*([^,\s]+)\s*,', re.IGNORECASE)
    pos = 0
    while pos < len(text):
        m = entry_start_regex.search(text, pos)
        if not m:
            break
        entry_type = m.group(1).lower()
        delimiter = m.group(2)
        closing_char = '}' if delimiter == '{' else ')'
        key = m.group(3).strip()

        if entry_type in ('comment', 'string', 'preamble'):
            pos = m.end()
            continue

        # Track brace depth to accurately locate matching closing delimiter
        depth = 1
        start_body = m.end()
        cur = start_body
        in_quotes = False
        while cur < len(text) and depth > 0:
            char = text[cur]
            if char == '"' and cur > 0 and text[cur - 1] != '\\':
                in_quotes = not in_quotes
            elif not in_quotes:
                if char == delimiter:
                    depth += 1
                elif char == closing_char:
                    depth -= 1
            cur += 1

        entry_body = text[start_body:cur - 1] if depth == 0 else text[start_body:]
        raw_entry = text[m.start():cur].strip()

        fields = {}
        # Match field = {val} or field = "val" or field = val
        field_iter = re.finditer(
            r'([a-zA-Z0-9_\-]+)\s*=\s*(?:\{([\s\S]*?)\}|"([\s\S]*?)"|([a-zA-Z0-9_\-]+))(?:\s*[,|\n|\r])',
            entry_body + '\n,'
        )
        for fm in field_iter:
            fname = fm.group(1).lower()
            fval = fm.group(2) if fm.group(2) is not None else (fm.group(3) if fm.group(3) is not None else fm.group(4))
            if fval:
                cleaned_val = re.sub(r'[\{\}]', '', fval).strip()
                cleaned_val = re.sub(r'\s+', ' ', cleaned_val)
                fields[fname] = cleaned_val

        raw_title = fields.get('title', key.replace('_', ' '))
        # Clean title from LaTeX commands like \textbf{}, \emph{}
        clean_title = re.sub(r'\\[a-zA-Z]+\{([^}]*)\}', r'\1', raw_title).strip()
        
        author_raw = fields.get('author', '')
        authors = []
        if author_raw:
            raw_author_parts = re.split(r'\s+and\s+', author_raw, flags=re.IGNORECASE)
            for a in raw_author_parts:
                cleaned_a = re.sub(r'[\{\}]', '', a).strip()
                # If author is formatted as "Last, First", convert to "First Last" for clean display
                if ',' in cleaned_a:
                    parts = [p.strip() for p in cleaned_a.split(',', 1)]
                    cleaned_a = f"{parts[1]} {parts[0]}".strip()
                if cleaned_a:
                    authors.append(cleaned_a)

        raw_year = fields.get('year', '')
        year_m = re.search(r'\b(19\d\d|20\d\d)\b', raw_year)
        year = year_m.group(1) if year_m else raw_year

        journal = fields.get('journal', fields.get('booktitle', fields.get('publisher', '')))
        raw_doi = fields.get('doi', '')
        doi = re.sub(r'^https?://(?:dx\.)?doi\.org/', '', raw_doi).strip()
        url = fields.get('url', '')
        abstract = fields.get('abstract', '')

        # Build clean structured Markdown summary
        md_lines = [f"### {clean_title}"]
        if authors:
            md_lines.append(f"- **Authors**: {', '.join(authors)}")
        if year:
            md_lines.append(f"- **Year**: {year}")
        if journal:
            md_lines.append(f"- **Journal/Venue**: {journal}")
        if doi:
            md_lines.append(f"- **DOI**: [{doi}](https://doi.org/{doi})")
        elif url:
            md_lines.append(f"- **URL**: [{url}]({url})")
        if abstract:
            md_lines.append(f"- **Abstract**: {abstract}")

        entries.append({
            'key': key,
            'type': entry_type,
            'title': clean_title,
            'authors': authors,
            'year': year,
            'journal': journal,
            'doi': doi,
            'abstract': abstract,
            'url': url,
            'raw': raw_entry,
            'markdown': "\n".join(md_lines)
        })
        pos = cur

    return entries


def extract_ris_entries(text: str) -> list:
    """
    Extracts structured bibliographic entries from RIS citation library content.
    Handles multiline tags, multiple authors, and clean metadata extraction.
    """
    entries = []
    current_fields = {}
    authors = []
    raw_lines = []

    for line in text.splitlines():
        raw_lines.append(line)
        trimmed = line.strip()
        if not trimmed:
            continue

        if trimmed.startswith("ER  -") or trimmed == "ER -" or trimmed == "ER-":
            if current_fields or authors:
                raw_title = current_fields.get("TI", current_fields.get("T1", current_fields.get("CT", "Untitled Reference")))
                clean_title = re.sub(r'\s+', ' ', raw_title).strip()

                raw_year = current_fields.get("PY", current_fields.get("Y1", ""))
                year_m = re.search(r'\b(19\d\d|20\d\d)\b', raw_year)
                year = year_m.group(1) if year_m else raw_year.strip()

                journal = current_fields.get("JO", current_fields.get("JF", current_fields.get("T2", current_fields.get("JA", ""))))
                raw_doi = current_fields.get("DO", "")
                doi = re.sub(r'^https?://(?:dx\.)?doi\.org/', '', raw_doi).strip()
                url = current_fields.get("UR", "")
                abstract = current_fields.get("AB", current_fields.get("N2", ""))

                # Clean formatted author names
                cleaned_authors = []
                for a in authors:
                    c_a = a.strip()
                    if ',' in c_a:
                        parts = [p.strip() for p in c_a.split(',', 1)]
                        c_a = f"{parts[1]} {parts[0]}".strip()
                    if c_a:
                        cleaned_authors.append(c_a)

                md_lines = [f"### {clean_title}"]
                if cleaned_authors:
                    md_lines.append(f"- **Authors**: {', '.join(cleaned_authors)}")
                if year:
                    md_lines.append(f"- **Year**: {year}")
                if journal:
                    md_lines.append(f"- **Journal/Venue**: {journal}")
                if doi:
                    md_lines.append(f"- **DOI**: [{doi}](https://doi.org/{doi})")
                elif url:
                    md_lines.append(f"- **URL**: [{url}]({url})")
                if abstract:
                    md_lines.append(f"- **Abstract**: {abstract}")

                entries.append({
                    'type': current_fields.get("TY", "JOUR"),
                    'title': clean_title,
                    'authors': cleaned_authors,
                    'year': year,
                    'journal': journal,
                    'doi': doi,
                    'abstract': abstract,
                    'url': url,
                    'raw': "\n".join(raw_lines).strip(),
                    'markdown': "\n".join(md_lines)
                })
            current_fields = {}
            authors = []
            raw_lines = []
        elif len(trimmed) >= 4 and (trimmed[2:6] == "  - " or trimmed[2:4] == "- "):
            tag = trimmed[:2].strip()
            dash_idx = trimmed.find("-")
            val = trimmed[dash_idx + 1:].strip()
            if tag in ("AU", "A1", "A2"):
                authors.append(val)
            elif tag in ("AB", "N2"):
                if tag in current_fields:
                    current_fields[tag] += " " + val
                else:
                    current_fields[tag] = val
            elif tag in ("TI", "T1"):
                if tag in current_fields:
                    current_fields[tag] += " " + val
                else:
                    current_fields[tag] = val
            else:
                current_fields[tag] = val
        elif authors or current_fields:
            # Continuation line of previous multiline tag
            if "AB" in current_fields:
                current_fields["AB"] += " " + trimmed
            elif "N2" in current_fields:
                current_fields["N2"] += " " + trimmed
            elif "TI" in current_fields:
                current_fields["TI"] += " " + trimmed
            elif "T1" in current_fields:
                current_fields["T1"] += " " + trimmed

    return entries


def parse_bibtex_text(text: str) -> str:
    """Converts BibTeX bibliographic references into clean structured Markdown summaries."""
    entries = extract_bibtex_entries(text)
    if not entries:
        return text
    return "\n\n---\n\n".join(e["markdown"] for e in entries)


def parse_ris_text(text: str) -> str:
    """Converts RIS citation library format into clean structured Markdown summaries."""
    entries = extract_ris_entries(text)
    if not entries:
        return text
    return "\n\n---\n\n".join(e["markdown"] for e in entries)

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
        print(f"[RAG Format Parsers] CSV parse error: {e}")
        return ""
