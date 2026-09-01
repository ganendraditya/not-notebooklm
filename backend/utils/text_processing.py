import re
import html

def normalize_title_str(t: str) -> str:
    """Normalizes a title by stripping extensions, punctuation, and collapsing whitespace."""
    if not t:
        return ""
    t = re.sub(r'\.pdf$', '', t, flags=re.I)
    t = re.sub(r'[^a-zA-Z0-9\s]', ' ', t).lower()
    return " ".join(t.split())

def is_valid_academic_title(title: str) -> bool:
    """Quality filter to exclude non-scholarly publication artifacts, covers, and TOCs."""
    t = title.lower().strip()
    if len(t) < 8:
        return False
    junk_patterns = [
        "[front cover]", "[copyright", "table of contents", "author index", "itu k programme",
        "itu k 2018", "keynote summary", "chairman's message", "foreword", "committees",
        "figure 1:", "table 3:", "table 5:", "peer review #", "cover page", "back cover",
        "editorial board", "preliminary pages", "conference report",
    ]
    if any(j in t for j in junk_patterns):
        return False
    # Reject generic publisher artifact headers that are not real paper titles
    generic_exact = {
        "article in press", "in press", "journal pre-proof", "uncorrected proof",
        "corrected proof", "original article", "research article", "full length article",
        "short communication", "review article", "full paper", "research paper",
        "accepted manuscript", "author's copy", "analytical index", "index",
        "abstract", "abstrak", "overview", "paper", "document",
    }
    if t in generic_exact:
        return False
    return True

def clean_academic_abstract(text: str) -> str:
    """Cleans HTML tags, JATS XML tags, HTML entities, and formatting artifacts from academic abstracts."""
    if not text:
        return ""
    cleaned = html.unescape(text)
    cleaned = html.unescape(cleaned)
    
    cleaned = re.sub(r'<\s*br\s*/?\s*>', '\n\n', cleaned, flags=re.I)
    cleaned = re.sub(r'<\s*/\s*p\s*>', '\n\n', cleaned, flags=re.I)
    cleaned = re.sub(r'<\s*p\s*>', '', cleaned, flags=re.I)
    cleaned = re.sub(r'<[^>]+>', '', cleaned)
    
    cleaned = re.sub(r'\*\*_([^_*]+)_\*\*', r'\1', cleaned)
    cleaned = re.sub(r'\*\*([^*]+)\*\*', r'\1', cleaned)
    cleaned = re.sub(r'__([^_]+)__', r'\1', cleaned)
    cleaned = re.sub(r'(?<!\w)\*([^*]+)\*(?!\w)', r'\1', cleaned)
    cleaned = re.sub(r'(?<!\w)_([^_\s][^_]*)_(?!\w)', r'\1', cleaned)
    cleaned = re.sub(r'\*{2,}', '', cleaned)
    cleaned = re.sub(r'(?<!\w)_+(?!\w)', '', cleaned)
    cleaned = re.sub(r'^#{1,6}\s*', '', cleaned, flags=re.MULTILINE)
    
    section_headers = [
        "Research question", "Research methods", "Methods and materials", "Methodology",
        "Results and findings", "Results", "Findings", "Discussion", "Conclusion", "Conclusions",
        "Implications", "Background", "Objective", "Objectives", "Purpose", "Design",
        "Setting", "Participants", "Interventions", "Main outcomes", "Significance"
    ]
    pattern = r'(?:\n+|\s+)\b(' + '|'.join(re.escape(h) for h in section_headers) + r')\s*:\s*'
    cleaned = re.sub(pattern, r'\n\n\1: ', cleaned, flags=re.I)
    
    cleaned = re.sub(r'[ \t]+', ' ', cleaned)
    cleaned = re.sub(r'\n\s*\n\s*\n+', '\n\n', cleaned)
    cleaned = re.sub(r'^\s*(?:abstract|abstract\s*&\s*overview|overview)\s*[:\-\.]?\s*', '', cleaned, flags=re.I)
    return cleaned.strip()

def is_valid_abstract_content(text: str) -> bool:
    """Validates whether a candidate string is an authentic academic abstract or just taxonomy/boilerplate."""
    if not text or not isinstance(text, str):
        return False
    t = text.strip()
    if len(t) < 50:
        return False
        
    t_low = t.lower()
    invalid_exact = {
        "social and behavioral sciences", "social sciences", "behavioral sciences",
        "medicine and health", "medical sciences", "engineering and computer science",
        "computer science", "physical sciences", "humanities", "arts and humanities",
        "business and economics", "life sciences", "biological sciences", "decision sciences"
    }
    if t_low in invalid_exact:
        return False
        
    boilerplate_phrases = [
        "publikasi ilmiah", "terindeks crossref", "scholarly publication", 
        "indexed in international", "no abstract available", "abstract not available",
        "preview this article", "full text is available", "an abstract is not available"
    ]
    if any(b in t_low for b in boilerplate_phrases) and len(t) < 250:
        return False
        
    return True

def extract_abstract_from_html(html_text: str) -> str:
    """Extracts authentic academic abstract from HTML meta tags and semantic container elements across scholarly publishers."""
    if not html_text:
        return ""
        
    meta_patterns = [
        r'<meta\s+[^>]*?(?:name|property)=["\'](?:citation_abstract|dc\.description)["\'][^>]*?content=["\'](.*?)["\']',
        r'<meta\s+[^>]*?content=["\'](.*?)["\'][^>]*?(?:name|property)=["\'](?:citation_abstract|dc\.description)["\']',
        r'<meta\s+[^>]*?(?:name|property)=["\'](?:og:description|description)["\'][^>]*?content=["\'](.*?)["\']'
    ]
    for pattern in meta_patterns:
        for m in re.findall(pattern, html_text, re.I | re.DOTALL):
            candidate = clean_academic_abstract(m)
            if is_valid_abstract_content(candidate) and "cookie" not in candidate.lower() and "javascript" not in candidate.lower():
                return candidate
                
    semantic_patterns = [
        r'<section[^>]*?class=["\'][^"\']*\babstract\b[^"\']*["\'][^>]*>([\s\S]*?)</section>',
        r'<div[^>]*?(?:class|id)=["\'][^"\']*\b(?:item\s+abstract|abstract-content|article-abstract|abstractText|abstract_content|abstract)\b[^"\']*["\'][^>]*>([\s\S]*?)</div>',
        r'<blockquote[^>]*?class=["\'][^"\']*\babstract\b[^"\']*["\'][^>]*>([\s\S]*?)</blockquote>',
        r'<section[^>]*?id=["\']abstract["\'][^>]*>([\s\S]*?)</section>',
        r'<div[^>]*?id=["\']abstract["\'][^>]*>([\s\S]*?)</div>'
    ]
    for pattern in semantic_patterns:
        for m in re.findall(pattern, html_text, re.I):
            candidate = clean_academic_abstract(m)
            if is_valid_abstract_content(candidate):
                return candidate
                
    return ""

def is_title_match(t1: str, t2: str) -> bool:
    """Checks if two academic paper titles match with high fuzzy similarity (>= 65%)."""
    if not t1 or not t2:
        return False
    c1 = re.sub(r'[^a-zA-Z0-9\s]', '', t1).lower().strip()
    c2 = re.sub(r'[^a-zA-Z0-9\s]', '', t2).lower().strip()
    if c1 == c2 or c1 in c2 or c2 in c1:
        return True
    import difflib
    ratio = difflib.SequenceMatcher(None, c1, c2).ratio()
    return ratio >= 0.65

def is_ai_synthesized_overview(text: str) -> bool:
    """Detects if an abstract text is an AI-generated fallback summary template rather than authentic author text."""
    if not text:
        return False
    t_low = text.lower()
    return any(p in t_low for p in [
        "this scholarly publication investigates",
        "this scholarly article investigates",
        "the research presents methodology, analytical framework",
        "the research presents methodology, computational framework",
        "indexed in international academic databases",
        "indexed in international academic indexing services"
    ])
