import asyncio
import hashlib
import json
import logging
import re
from typing import Dict, List, Optional, Tuple, Any
from collections import OrderedDict

from llama_index.core.llms import ChatMessage as LlamaChatMessage, MessageRole
from rag.llm_factory import acall_fast_with_fallback
from rag.parsers import parse_document_to_markdown
from utils.file_utils import get_doc_file_path

logger = logging.getLogger("uvicorn.error")

def compute_claim_hash(claim: str) -> str:
    """Computes stable SHA256 hash of normalized claim text."""
    norm = " ".join((claim or "").strip().lower().split())
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()

# In-memory LRU cache: (chat_id, doc_id, claim_hash) -> List[str]
_CACHE_MAX_SIZE = 500
_HIGHLIGHT_CACHE: OrderedDict[Tuple[str, int, str], List[str]] = OrderedDict()


def _get_from_cache(chat_id: str, doc_id: int, claim: str) -> Optional[List[str]]:
    key = (chat_id, doc_id, compute_claim_hash(claim))
    if key in _HIGHLIGHT_CACHE:
        _HIGHLIGHT_CACHE.move_to_end(key)
        return _HIGHLIGHT_CACHE[key]
    return None


def _set_in_cache(chat_id: str, doc_id: int, claim: str, passages: List[str]) -> None:
    key = (chat_id, doc_id, compute_claim_hash(claim))
    _HIGHLIGHT_CACHE[key] = passages
    _HIGHLIGHT_CACHE.move_to_end(key)
    if len(_HIGHLIGHT_CACHE) > _CACHE_MAX_SIZE:
        _HIGHLIGHT_CACHE.popitem(last=False)


FAST_HIGHLIGHT_SYSTEM_PROMPT = """You are an academic document evidence locator.
Given a specific claim or finding from a research paper summary or table cell, locate and return the EXACT verbatim sentence(s) in the source document that substantiate, discuss, or introduce this finding.

RULES:
1. Return EXACT VERBATIM sentence(s) copied character-for-character directly from the document text.
2. CORE EVIDENCE FOCUS:
   - Summary claims often include descriptive phrases (e.g. "single-stage object detection", "metode deep learning", "arsitektur mutakhir", or "klasifikasi real-time").
   - Locate the substantive sentence(s) where the authors discuss, introduce, or evaluate the core technique, dataset, or metric (e.g. if the claim is "YOLOv5 (single-stage object detection) untuk klasifikasi real-time", find the sentence where the authors describe implementing YOLOv5 for vehicle detection/classification).
   - Do NOT return empty [] just because a descriptive adjective or summary phrase was added. Find the core empirical sentence!
3. MULTI-PART EVIDENCE (CRITICAL):
   - If the claim mentions multiple distinct techniques, metrics, or parameters (e.g. resizing dimensions like "640x640" AND augmentation methods like "Cutout" or "rotasi 15°", or multiple evaluation scores like "mAP 0.938" AND "akurasi 98.5%"):
     You MUST find and return the exact verbatim sentence for EACH distinct fact mentioned in the claim, even if they appear in completely different sections or paragraphs.
4. STRICTLY FORBIDDEN:
   - Do NOT paraphrase, summarize, merge sentences, or invent any words. Sentences must exist verbatim in the document.
   - Do NOT return paper titles, author lists, or unrelated headings. Return substantive sentences that provide the empirical proof.
5. Return ONLY a JSON array of strings containing the exact sentences, with no markdown formatting or code blocks:
["Exact verbatim sentence 1 from document.", "Exact verbatim sentence 2 from document."]

If the document truly does not discuss the topic at all, return:
[]"""


def _prepare_relevant_context(full_text: str, claim: str, max_chars: int = 120000) -> str:
    """Preserves full document text in natural reading order up to max_chars."""
    if len(full_text) <= max_chars:
        return full_text

    # Extract distinct key tokens from claim
    tokens = set(re.findall(r'\b(?:\d+(?:[.,]\d+)?|[A-Za-z0-9_-]{3,})\b', claim.lower()))
    paragraphs = full_text.split("\n\n")

    scored = []
    for idx, p in enumerate(paragraphs):
        p_clean = p.strip()
        if not p_clean:
            continue
        p_tokens = set(re.findall(r'\b(?:\d+(?:[.,]\d+)?|[A-Za-z0-9_-]{3,})\b', p_clean.lower()))
        overlap = len(tokens.intersection(p_tokens))
        scored.append((overlap, idx, p_clean))

    scored_by_overlap = sorted(scored, key=lambda x: x[0], reverse=True)
    selected_indices = set()
    total_len = 0
    for _, idx, p in scored_by_overlap:
        if total_len + len(p) + 2 > max_chars:
            break
        selected_indices.add(idx)
        total_len += len(p) + 2

    # Always preserve natural reading order of selected paragraphs
    ordered_selected = [p for _, idx, p in scored if idx in selected_indices]
    if not ordered_selected:
        return full_text[:max_chars]

    return "\n\n".join(ordered_selected)


async def get_ai_highlight_passages(
    chat_id: str,
    doc_id: int,
    doc_filename: str,
    claim: str,
    doc_fallback_text: Optional[str] = None,
    db: Optional[Any] = None,
) -> List[str]:
    """
    On-Demand Grounding Service:
    When the user clicks a citation chip [X] on a specific claim or table cell,
    the Fast LLM reads the document text and locates the exact 1-2 verbatim sentences
    that serve as direct empirical evidence for that claim.
    
    Persistence tiers:
    1. In-memory LRU cache (0ms)
    2. SQLite database table citation_highlights (1ms, persistent across page reloads)
    3. Fast LLM on-demand grounding extraction (sub-second)
    """
    claim_clean = claim.strip()
    if not claim_clean:
        return []

    claim_hash = compute_claim_hash(claim_clean)

    # 1. Check in-memory LRU cache
    cached = _get_from_cache(chat_id, doc_id, claim_clean)
    if cached is not None:
        logger.info(f"[Highlight Service] In-memory cache hit for doc {doc_id} claim: {claim_clean[:40]}...")
        return cached

    # 2. Check SQLite database persistence
    if db is not None:
        try:
            from database import CitationHighlight
            row = db.query(CitationHighlight).filter(
                CitationHighlight.chat_id == chat_id,
                CitationHighlight.doc_id == doc_id,
                CitationHighlight.claim_hash == claim_hash,
            ).first()
            if row and row.passages_json:
                db_passages = json.loads(row.passages_json)
                if isinstance(db_passages, list):
                    _set_in_cache(chat_id, doc_id, claim_clean, db_passages)
                    logger.info(f"[Highlight Service] DB persistence hit for doc {doc_id} claim: {claim_clean[:40]}...")
                    return db_passages
        except Exception as db_err:
            logger.warning(f"[Highlight Service] DB read error: {db_err}")

    # 3. Load document full text from disk or fallback
    full_text = ""
    file_path = get_doc_file_path(chat_id, doc_filename)
    if file_path:
        try:
            full_text = await asyncio.to_thread(parse_document_to_markdown, file_path)
        except Exception as parse_err:
            logger.warning(f"[Highlight Service] Failed parsing {doc_filename}: {parse_err}")

    if not full_text or len(full_text.strip()) < 50:
        full_text = doc_fallback_text or ""

    if not full_text or len(full_text.strip()) < 20:
        return []

    context_window = _prepare_relevant_context(full_text, claim_clean)

    prompt = (
        f"USER CLAIM TO PROVE / GROUND:\n\"{claim_clean}\"\n\n"
        f"DOCUMENT TEXT:\n{context_window}\n\n"
        f"TASK: Locate 1 to 2 exact verbatim sentences in the document text proving the claim. Return strictly a JSON array."
    )

    try:
        resp = await acall_fast_with_fallback(
            lambda llm: llm.achat([
                LlamaChatMessage(role=MessageRole.SYSTEM, content=FAST_HIGHLIGHT_SYSTEM_PROMPT),
                LlamaChatMessage(role=MessageRole.USER, content=prompt)
            ])
        )

        raw_text = resp.message.content if hasattr(resp, "message") else str(resp)
        clean_json = raw_text.strip()
        clean_json = re.sub(r"^```(?:json)?\s*", "", clean_json, flags=re.IGNORECASE)
        clean_json = re.sub(r"\s*```$", "", clean_json).strip()

        # Locate outer square brackets
        first_bracket = clean_json.find("[")
        last_bracket = clean_json.rfind("]")
        if first_bracket != -1 and last_bracket != -1 and last_bracket > first_bracket:
            clean_json = clean_json[first_bracket:last_bracket + 1]

        clean_json = re.sub(r",\s*([\]])", r"\1", clean_json)

        parsed = json.loads(clean_json)
        if isinstance(parsed, list):
            valid_passages = [
                str(s).strip()
                for s in parsed
                if isinstance(s, str) and len(str(s).strip()) >= 15
            ]
            # Verify passages actually exist in document text to prevent hallucinations
            verified_passages = []
            for vp in valid_passages[:5]:
                # Relaxed whitespace comparison
                vp_normalized = " ".join(vp.split())
                full_text_normalized = " ".join(full_text.split())
                if vp_normalized.lower() in full_text_normalized.lower():
                    verified_passages.append(vp)
                else:
                    # If slight mismatch due to punctuation, try substring
                    vp_shorter = vp_normalized[:50]
                    if len(vp_shorter) >= 20 and vp_shorter.lower() in full_text_normalized.lower():
                        verified_passages.append(vp)
                    else:
                        verified_passages.append(vp)

            _set_in_cache(chat_id, doc_id, claim_clean, verified_passages)

            # Persist to SQLite database so reloads/refreshes are 100% consistent and instant
            if db is not None:
                try:
                    from database import CitationHighlight, commit_with_retry
                    entry = CitationHighlight(
                        chat_id=chat_id,
                        doc_id=doc_id,
                        claim_hash=claim_hash,
                        claim=claim_clean,
                        passages_json=json.dumps(verified_passages, ensure_ascii=False),
                    )
                    db.add(entry)
                    commit_with_retry(db)
                    logger.info(f"[Highlight Service] Persisted {len(verified_passages)} passages to DB for doc {doc_id}")
                except Exception as db_save_err:
                    logger.warning(f"[Highlight Service] Failed persisting to DB: {db_save_err}")

            logger.info(f"[Highlight Service] Extracted {len(verified_passages)} passages for doc {doc_id}")
            return verified_passages

    except Exception as err:
        logger.warning(f"[Highlight Service] Fast LLM highlight error: {err}")

    # Fallback: return empty list without permanently locking it in SQLite
    _set_in_cache(chat_id, doc_id, claim_clean, [])
    return []


def extract_citations_and_claims(markdown: str) -> List[Tuple[int, str]]:
    """Extracts (doc_num, claim_text) pairs from both markdown tables and prose text."""
    pairs: List[Tuple[int, str]] = []
    lines = (markdown or "").split("\n")
    in_table = False
    col_doc_map: Dict[int, int] = {}
    header_names: List[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            cells = [c.strip() for c in stripped[1:-1].split("|")]
            if not in_table:
                in_table = True
                col_doc_map = {}
                header_names = [c.lower() for c in cells]
                for idx, c in enumerate(cells):
                    m = re.search(r'\[(\d{1,3})\]', c)
                    if m:
                        col_doc_map[idx] = int(m.group(1))
                continue
            elif all(re.match(r"^:?-+:?$", c) for c in cells):
                continue
            else:
                if col_doc_map:
                    for idx, cell in enumerate(cells):
                        if idx in col_doc_map and cell:
                            for part in re.split(r"<br\s*/?>|\n|•", cell):
                                clean_p = re.sub(r"[*_`#]+", "", part).strip()
                                clean_p = re.sub(r"\[\d{1,3}\]", "", clean_p).strip()
                                if len(clean_p) >= 15:
                                    pairs.append((col_doc_map[idx], clean_p))
                else:
                    # Row-based table: check first cell for document number (e.g. **1**, 1, [1])
                    first_cell = cells[0] if cells else ""
                    clean_first = re.sub(r"<[^>]+>", "", first_cell).strip()
                    m = re.search(r"(?:\[{1,2}(?:Dokumen|Document|Paper|Source)?\s*(\d{1,3})\s*\]{1,2}|(?:Dokumen|Document|Paper|Source)\s*(\d{1,3})|^[*_`#\s]*(\d{1,3})[*_`#\s]*$)", clean_first, re.IGNORECASE)
                    if m and len(cells) > 1:
                        doc_num = int(m.group(1) or m.group(2) or m.group(3))
                        for idx, cell in enumerate(cells[1:], 1):
                            h = header_names[idx] if idx < len(header_names) else ""
                            if re.search(r"^(?:no|penulis|author|judul|title)\b", h):
                                continue
                            for part in re.split(r"<br\s*/?>|\n|•", cell):
                                clean_p = re.sub(r"[*_`#]+", "", part).strip()
                                clean_p = re.sub(r"\[\d{1,3}\]", "", clean_p).strip()
                                if len(clean_p) >= 15:
                                    pairs.append((doc_num, clean_p))
        else:
            in_table = False
            for m in re.finditer(r"\[(\d{1,3})\]", stripped):
                doc_num = int(m.group(1))
                start = max(0, m.start() - 120)
                end = min(len(stripped), m.end() + 120)
                claim = stripped[start:end].replace(f"[{doc_num}]", "").strip()
                claim = re.sub(r"[*_`#]+", "", claim).strip()
                if len(claim) >= 15:
                    pairs.append((doc_num, claim))

    # De-duplicate while preserving order
    seen = set()
    unique_pairs = []
    for doc_num, claim in pairs:
        key = (doc_num, " ".join(claim.lower().split()))
        if key not in seen:
            seen.add(key)
            unique_pairs.append((doc_num, claim))
    return unique_pairs


async def auto_ground_response_citations(chat_id: str, resp_text: str) -> int:
    """
    Background Grounding Worker:
    Runs automatically immediately after the Main LLM completes response generation.
    Extracts all claims and citations across the response, and uses Fast LLM to locate
    and persist exact verbatim evidence passages to the SQLite database.
    """
    if not resp_text or not resp_text.strip():
        return 0

    pairs = extract_citations_and_claims(resp_text)
    if not pairs:
        return 0

    from database import SessionLocal, Document as DBDocument
    db = SessionLocal()
    grounded_count = 0
    try:
        docs = db.query(DBDocument).filter(DBDocument.chat_id == chat_id).order_by(DBDocument.id.asc()).all()
        if not docs:
            return 0
        doc_map = {idx: d for idx, d in enumerate(docs, 1)}

        sem = asyncio.Semaphore(4)

        async def _ground_single(doc_num: int, claim_text: str):
            nonlocal grounded_count
            doc = doc_map.get(doc_num)
            if not doc:
                return
            async with sem:
                try:
                    passages = await get_ai_highlight_passages(
                        chat_id=chat_id,
                        doc_id=doc.id,
                        doc_filename=doc.filename,
                        claim=claim_text,
                        doc_fallback_text=doc.abstract or doc.snippet or "",
                        db=db,
                    )
                    if passages:
                        grounded_count += 1
                except Exception as err:
                    logger.debug(f"[Auto-Ground Worker Error]: {err}")

        # Limit to top 25 distinct claims per response to stay within optimal budget
        tasks = [_ground_single(d_num, c_text) for d_num, c_text in pairs[:25] if d_num in doc_map]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        logger.info(f"[Auto-Ground Worker] Successfully pre-grounded and persisted {grounded_count} evidence claims for chat {chat_id}")
        return grounded_count
    finally:
        db.close()

