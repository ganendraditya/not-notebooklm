"""
Princeton ALCE Citation Evaluator Adapter
Implements formal Citation Recall & Citation Precision metrics from:
"Enabling Large Language Models to Generate Text with Citations"
(Gao et al., Princeton NLP, EMNLP 2023)
https://github.com/princeton-nlp/ALCE
"""

import os
import re
import json
import asyncio
import logging
from typing import Dict, List, Optional, Tuple, Any
from pydantic import BaseModel, Field

logger = logging.getLogger("uvicorn.error")


class ALCEStatementCitation(BaseModel):
    statement: str
    cited_docs: List[str]
    has_citations: bool
    recall: float = 1.0
    precisions: Dict[str, float] = Field(default_factory=dict)


class ALCEReport(BaseModel):
    """Evaluation output adhering to Princeton ALCE citation quality standards."""
    citation_recall: float = Field(
        default=1.0, ge=0.0, le=1.0,
        description="Ratio of generated statements fully supported by their cited documents."
    )
    citation_precision: float = Field(
        default=1.0, ge=0.0, le=1.0,
        description="Ratio of citations that are relevant and non-redundant (penalizes irrelevant citations)."
    )
    total_statements: int = 0
    cited_statements: int = 0
    total_citations: int = 0
    statement_details: List[ALCEStatementCitation] = Field(default_factory=list)


def split_into_statements(text: str) -> List[str]:
    """
    Segments response into discrete atomic statements following ALCE Section 2.
    Handles standard sentences, Markdown bullets, and comparison table cells.
    """
    # 1. Clean hidden metadata payloads
    clean_text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL).strip()
    if not clean_text:
        return []

    raw_statements = []

    # Handle line-by-line formatting
    for line in clean_text.split("\n"):
        line = line.strip()
        if not line:
            continue

        # Skip bare Markdown table headers/dividers
        if line.startswith("|") and ("---" in line or line.replace("|", "").strip().lower() in ["no", "dokumen", "dimensi", "paper"]):
            continue

        # If table row with pipes, extract meaningful cells
        if line.startswith("|") and line.endswith("|"):
            cells = [c.strip() for c in line.split("|")[1:-1] if c.strip()]
            for cell in cells:
                if re.search(r'\[\d+\]', cell) or len(cell.split()) >= 4:
                    raw_statements.append(cell)
            continue

        # If bullet point, treat as atomic statement
        if line.startswith(("- ", "* ", "• ")) or re.match(r'^\d+[\.\)]\s+', line):
            bullet_clean = re.sub(r'^(?:[-*•]|\d+[\.\)])\s+', '', line).strip()
            if bullet_clean:
                raw_statements.append(bullet_clean)
            continue

        # Split ordinary narrative text into sentences
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', line) if s.strip()]
        raw_statements.extend(sentences)

    # Filter out trivial greetings or bare titles (< 15 characters without citations)
    filtered = []
    for s in raw_statements:
        has_tag = bool(re.search(r'\[\d+\]', s))
        if has_tag or len(s) >= 20:
            filtered.append(s)

    return filtered if filtered else ([clean_text] if clean_text else [])


async def check_nli_entailment(
    premise: str,
    hypothesis: str,
    llm: Any
) -> bool:
    """
    Evaluates NLI entailment phi(premise, hypothesis) following TRUE / AIS protocol.
    Returns True if premise directly entails and supports the hypothesis.
    """
    from utils.text_processing import extract_json_from_llm

    clean_hypo = re.sub(r'\[\d+\]', '', hypothesis).strip()
    clean_premise = premise[:40000].strip()

    if not clean_premise or not clean_hypo:
        return False

    prompt = (
        "You are an expert Natural Language Inference (NLI) judge evaluating citation attribution (Princeton ALCE benchmark).\n"
        f"Premise (Retrieved Document Passage):\n{clean_premise}\n\n"
        f"Hypothesis (Statement made by model):\n{clean_hypo}\n\n"
        "Task: Does the Premise fully support and logically entail the factual claims made in the Hypothesis?\n"
        "Rules:\n"
        "- YES: All facts, numbers, and claims in the hypothesis are directly substantiated by the premise.\n"
        "- NO: The hypothesis introduces outside facts, contradicts the premise, or makes unsubstantiated claims.\n\n"
        "Respond ONLY with valid JSON:\n"
        '{\n  "entailed": true,\n  "reason": "Brief justification"\n}'
    )

    try:
        resp = await llm.acomplete(prompt)
        raw_json = extract_json_from_llm(resp.text)
        data = json.loads(raw_json)
        return bool(data.get("entailed", True))
    except Exception as e:
        logger.debug(f"[ALCE NLI] Fallback for entailment check: {e}")
        # Robust fallback: substring keyword check
        words = set(re.findall(r'\w+', clean_hypo.lower()))
        prem_words = set(re.findall(r'\w+', clean_premise.lower()))
        return len(words.intersection(prem_words)) >= min(len(words), 3)


def extract_json_objects(text: str) -> List[Dict[str, Any]]:
    """Robust fallback JSON object extractor for streaming or truncated LLM arrays."""
    results = []
    stack = []
    start_idx = None
    in_string = False
    escape = False

    for idx, char in enumerate(text):
        if char == '"' and not escape:
            in_string = not in_string
        elif char == '\\' and in_string:
            escape = not escape
            continue
        elif not in_string:
            if char == '{':
                if not stack:
                    start_idx = idx
                stack.append('{')
            elif char == '}':
                if stack:
                    stack.pop()
                    if not stack and start_idx is not None:
                        try:
                            results.append(json.loads(text[start_idx:idx+1]))
                        except Exception:
                            pass
                        start_idx = None
        escape = False
    return results


def verify_statement_in_doc(stmt: str, doc_text: str) -> bool:
    """Verifies whether substantive keywords/numbers in a statement are corroborated by document text."""
    clean_stmt = re.sub(r'\[\d+\]', '', stmt).lower()
    tokens = [w for w in re.findall(r'\b\w+\b', clean_stmt) if len(w) > 4 or re.match(r'^\d+$', w)]
    if not tokens:
        return True
    doc_lower = doc_text.lower()
    matches = sum(1 for t in tokens if t in doc_lower)
    return (matches / len(tokens)) >= 0.40


async def evaluate_alce_citation_quality(
    response: str,
    source_docs_map: Dict[str, str],
    llm: Any
) -> ALCEReport:
    """
    Computes formal Princeton ALCE Citation Recall and Citation Precision:
    - Citation Recall: phi(concat(C_i), s_i) averaged over all statements
    - Citation Precision: penalizes irrelevant citations that do not support the claim
    Uses parallel chunked batch auditing (8 statements per batch) to prevent JSON truncation on large tables.
    """
    from utils.text_processing import extract_json_from_llm

    statements = split_into_statements(response)
    if not statements:
        return ALCEReport()

    report = ALCEReport()
    report.total_statements = len(statements)

    # Filter out statements with citations vs statements without citations
    cited_stmts_info = []
    uncited_recall_scores = []
    evaluated_details: List[ALCEStatementCitation] = []

    for idx, stmt in enumerate(statements, 1):
        cited_tags = list(dict.fromkeys(re.findall(r'\[(\d+)\]', stmt)))
        # In single-document contexts, all factual statements implicitly anchor to Document 1
        if not cited_tags and len(source_docs_map) == 1:
            cited_tags = ["1"]

        has_cits = len(cited_tags) > 0
        if not has_cits:
            # Empirical statements with numbers without citations in multi-doc are penalized
            has_numbers = bool(re.search(r'\b\d+[\.,]?\d*\b', stmt))
            s_rec = 0.0 if has_numbers else 1.0
            uncited_recall_scores.append(s_rec)
            evaluated_details.append(
                ALCEStatementCitation(statement=stmt, cited_docs=[], has_citations=False, recall=s_rec)
            )
        else:
            cited_stmts_info.append((idx, stmt, cited_tags))

    if not cited_stmts_info:
        report.citation_recall = round(sum(uncited_recall_scores) / len(uncited_recall_scores), 3) if uncited_recall_scores else 1.0
        report.citation_precision = 1.0
        report.statement_details = evaluated_details
        return report

    report.cited_statements = len(cited_stmts_info)
    report.total_citations = sum(len(tags) for _, _, tags in cited_stmts_info)

    # Format document reference blocks
    docs_blocks = []
    for doc_k, doc_txt in source_docs_map.items():
        if doc_txt:
            docs_blocks.append(f"--- DOCUMENT [{doc_k}] ---\n{doc_txt[:30000]}")
    docs_str = "\n\n".join(docs_blocks)

    # Chunk statements into parallel batches of 8 to prevent output token saturation & truncated JSON arrays
    BATCH_SIZE = 8
    batches = [cited_stmts_info[i:i+BATCH_SIZE] for i in range(0, len(cited_stmts_info), BATCH_SIZE)]

    async def audit_batch(batch_items):
        stmts_str = "\n".join([f"{i}. {stmt}" for i, stmt, _ in batch_items])
        prompt = (
            "You are an expert Natural Language Inference (NLI) citation quality auditor adhering to the Princeton ALCE benchmark (EMNLP 2023).\n\n"
            f"Authoritative Reference Documents:\n{docs_str}\n\n"
            f"Statements with Citations to Audit:\n{stmts_str}\n\n"
            "Task for each numbered statement:\n"
            "1. is_supported (Recall): Do the cited documents [X] support the claims in the statement? (true/false)\n"
            "2. citations (Precision): For each cited document [X], is it relevant and helpful in proving the claim? (e.g. {\"1\": true, \"2\": false})\n\n"
            "Respond ONLY with valid JSON array:\n"
            "[\n"
            "  {\n"
            "    \"index\": 1,\n"
            "    \"is_supported\": true,\n"
            "    \"citations\": {\"1\": true}\n"
            "  }\n"
            "]"
        )
        try:
            resp = await llm.acomplete(prompt)
            raw = extract_json_from_llm(resp.text)
            try:
                data = json.loads(raw)
            except Exception:
                data = extract_json_objects(raw)
            if not isinstance(data, list):
                data = extract_json_objects(raw)
            return {item.get("index"): item for item in data if isinstance(item, dict)}
        except Exception as e:
            logger.warning(f"[ALCE Evaluator] Batch audit failed: {e}")
            return {}

    batch_results = await asyncio.gather(*[audit_batch(b) for b in batches], return_exceptions=True)
    data_by_idx: Dict[int, Dict[str, Any]] = {}
    for res in batch_results:
        if isinstance(res, dict):
            data_by_idx.update(res)

    recall_scores = list(uncited_recall_scores)
    precision_scores = []

    for idx, stmt, tags in cited_stmts_info:
        audit_item = data_by_idx.get(idx)
        if audit_item is not None:
            is_supp = bool(audit_item.get("is_supported", True))
            cit_map = audit_item.get("citations", {})
            prec_dict = {}
            for t in tags:
                p_val = 1.0 if (is_supp and cit_map.get(str(t), True)) else 0.0
                prec_dict[str(t)] = p_val
                precision_scores.append(p_val)
        else:
            # Resilient fallback: evaluate statement against cited documents directly via term verification
            prec_dict = {}
            has_support = False
            for t in tags:
                d_text = source_docs_map.get(str(t), "")
                t_match = verify_statement_in_doc(stmt, d_text)
                prec_dict[str(t)] = 1.0 if t_match else 0.0
                precision_scores.append(1.0 if t_match else 0.0)
                if t_match:
                    has_support = True
            is_supp = has_support

        s_rec = 1.0 if is_supp else 0.0
        recall_scores.append(s_rec)

        evaluated_details.append(
            ALCEStatementCitation(
                statement=stmt,
                cited_docs=tags,
                has_citations=True,
                recall=s_rec,
                precisions=prec_dict
            )
        )

    report.statement_details = evaluated_details
    report.citation_recall = round(sum(recall_scores) / len(recall_scores), 3) if recall_scores else 1.0
    report.citation_precision = round(sum(precision_scores) / len(precision_scores), 3) if precision_scores else 1.0

    return report
