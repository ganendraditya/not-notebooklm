import os
import re
import pymupdf4llm

def parse_docx_file(file_path: str) -> str:
    """Extracts text and tables from Word (.docx) document as clean Markdown."""
    try:
        import docx
        doc = docx.Document(file_path)
        lines = []
        for p in doc.paragraphs:
            text = p.text.strip()
            if text:
                style_name = p.style.name.lower() if p.style else ""
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
        return "\n\n".join(lines).strip()
    except Exception as e:
        print(f"[RAG Parsers] Warning: DOCX extraction error: {e}")
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

def parse_document_to_markdown(file_path: str) -> str:
    """Parses any supported document format into Markdown text."""
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
        
    return md_text
