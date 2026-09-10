import re
from typing import List, Dict, Any

import re
import logging
from typing import List, Dict, Any, Optional
import numpy as np

logger = logging.getLogger("uvicorn.error")

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
        re.compile(r'\b(?:methods?|methodology|materials?\s+and\s+methods?|metode|metodologi|metodología|méthodologie|experimental\s+setup|study\s+design|protocol|data\s+collection|procedures?|proposed\s+(?:\w+\s+)*(?:method|architecture|framework|approach|model|system)|(?:system|model|network)\s+architecture|architectures?)\b|研究方法|調査方法', re.IGNORECASE)
    ],
    "results": [
        re.compile(r'\b(?:results?|findings?|hasil|hasil\s+penelitian|data\s+analysis|experimental\s+results?|benchmarks?|benchmarking|ablation(?:\s+study)?|evaluations?)\b', re.IGNORECASE)
    ],
    "discussion": [
        re.compile(r'\b(?:discussion|pembahasan|interpretation|implications?)\b', re.IGNORECASE)
    ],
    "conclusion": [
        re.compile(r'\b(?:conclusions?|kesimpulan|concluding\s+remarks|summary\s+and\s+conclusion|penutup|takeaways?|closing\s+thoughts?)\b', re.IGNORECASE)
    ],
    "limitations": [
        re.compile(r'\b(?:limitations?|threats\s+to\s+validity|future\s+works?|limitasi|keterbatasan)\b', re.IGNORECASE)
    ],
    "references": [
        re.compile(r'\b(?:references|bibliography|daftar\s+pustaka|works\s+cited)\b', re.IGNORECASE)
    ]
}

CANONICAL_SEMANTIC_ANCHORS = {
    "abstract": "passage: academic research paper abstract executive summary synopsis brief overview of the study",
    "introduction": "passage: introduction research background study motivation problem statement research scope",
    "literature_review": "passage: literature review related work theoretical framework prior research studies state of the art",
    "methodology": "passage: research methodology scientific methods materials and methods experimental setup data collection study design algorithm architecture procedure implementation proposed method",
    "results": "passage: experimental results findings empirical evaluation performance metrics data analysis benchmark results ablation study ablation experiments findings of the study testing",
    "discussion": "passage: discussion interpretation of results implications comparative analysis practical implications critical discussion",
    "conclusion": "passage: conclusion concluding remarks summary of findings final conclusion take away lessons closing remarks",
    "limitations": "passage: study limitations threats to validity research constraints weaknesses ethical considerations",
    "references": "passage: references bibliography literature cited citations works cited publication list",
    "general": "passage: chapter heading section preface foreword table of contents legal clause fiction general document title appendix"
}

_CATEGORY_CENTROIDS_CACHE: Optional[Dict[str, np.ndarray]] = None
_HEADER_CLASSIFICATION_CACHE: Dict[str, str] = {}


def strip_heading_numbering(title: str) -> str:
    """Removes leading section numbering like '1.', '3.2', 'IV.', 'Bab 2:', 'Section 1.1 -'."""
    cleaned = re.sub(
        r'^(?:(?:(?:chapter|section|bab|part)\s+)?[0-9]+(?:\.[0-9]+)*[A-Za-z]?|[IVXLCDM]+)[\.\s\-:]+\s*',
        '',
        title,
        flags=re.IGNORECASE
    ).strip()
    return cleaned if len(cleaned) >= 3 else title


def get_default_embed_model():
    """Lazily retrieves the application-wide embedding model from vector_store if loaded."""
    try:
        from .vector_store import embed_model
        return embed_model
    except Exception:
        try:
            from rag.vector_store import embed_model
            return embed_model
        except Exception:
            return None


def init_semantic_centroids(embed_model: Any) -> Optional[Dict[str, np.ndarray]]:
    """Precomputes normalized vector centroids for canonical categories once."""
    global _CATEGORY_CENTROIDS_CACHE
    if _CATEGORY_CENTROIDS_CACHE is not None:
        return _CATEGORY_CENTROIDS_CACHE
    if embed_model is None or not hasattr(embed_model, "get_text_embedding"):
        return None
    try:
        centroids = {}
        for cat, text in CANONICAL_SEMANTIC_ANCHORS.items():
            vec = np.array(embed_model.get_text_embedding(text), dtype=np.float32)
            norm = np.linalg.norm(vec)
            if norm > 0:
                centroids[cat] = vec / norm
        _CATEGORY_CENTROIDS_CACHE = centroids
        return _CATEGORY_CENTROIDS_CACHE
    except Exception as e:
        logger.warning(f"[Academic Chunker] Failed to initialize semantic centroids: {e}")
        return None


def classify_canonical_section(
    header_title: str,
    embed_model: Optional[Any] = None,
    threshold: float = 0.815,
    min_margin: float = 0.003
) -> str:
    """
    Hybrid 2-Tier Classifier for Academic Sections:
    - Tier 1: Fast-Path Regex (0 ms) for standard IMRaD taxonomy in EN/ID/ES/FR.
    - Tier 2: Multilingual Semantic Cosine Similarity (E5 Embedding) for non-standard/creative titles and 93+ languages.
    - Tier 3: General Fallback for non-academic or low-confidence headers.
    """
    if not header_title:
        return "general"

    clean_h = header_title.strip()
    clean_lower = clean_h.lower()

    # Tier 1: Fast-Path Regex Matcher
    for cat, compiled_patterns in CANONICAL_SECTION_PATTERNS.items():
        for pat in compiled_patterns:
            if pat.search(clean_lower):
                return cat

    # Check cache for previously classified header string
    if clean_lower in _HEADER_CLASSIFICATION_CACHE:
        return _HEADER_CLASSIFICATION_CACHE[clean_lower]

    # Tier 2: Semantic Embedding Matcher (Multilingual E5)
    active_embed_model = embed_model if embed_model is not None else get_default_embed_model()
    if active_embed_model is not None:
        try:
            centroids = init_semantic_centroids(active_embed_model)
            if centroids:
                norm_title = strip_heading_numbering(clean_h)
                query_text = f"query: {norm_title}"
                query_vec = np.array(active_embed_model.get_text_embedding(query_text), dtype=np.float32)
                q_norm = np.linalg.norm(query_vec)
                if q_norm > 0:
                    query_vec /= q_norm
                    scores = {cat: float(np.dot(query_vec, c_vec)) for cat, c_vec in centroids.items()}
                    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
                    top1, s1 = sorted_scores[0]
                    top2, s2 = sorted_scores[1]
                    margin = s1 - s2

                    # Confidence criteria:
                    # If top match is 'general', or confidence is below threshold, or margin is ambiguous:
                    if top1 != "general" and s1 >= threshold and margin >= min_margin:
                        _HEADER_CLASSIFICATION_CACHE[clean_lower] = top1
                        return top1
                    else:
                        _HEADER_CLASSIFICATION_CACHE[clean_lower] = "general"
                        return "general"
        except Exception as e:
            logger.debug(f"[Academic Chunker] Semantic classification skipped ({e})")

    # Tier 3: Fallback
    _HEADER_CLASSIFICATION_CACHE[clean_lower] = "general"
    return "general"


def split_markdown_into_academic_sections(
    markdown_text: str,
    filename: str = "",
    embed_model: Optional[Any] = None
) -> List[Dict[str, Any]]:
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
        canonical_tag = classify_canonical_section(primary_header, embed_model=embed_model)
        if canonical_tag == "general" and header_stack:
            for ancestor in reversed(header_stack[:-1]):
                ancestor_tag = classify_canonical_section(ancestor[1], embed_model=embed_model)
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
