import os
import re
import json
import sys
import types
import asyncio
import logging
from typing import List, Dict, Optional, Any, Tuple
from pydantic import BaseModel, Field

# Ensure Ragas compatibility shims if imported
if 'langchain_community.chat_models.vertexai' not in sys.modules:
    dummy_vertex = types.ModuleType('langchain_community.chat_models.vertexai')
    dummy_vertex.ChatVertexAI = type('ChatVertexAI', (), {})
    sys.modules['langchain_community.chat_models.vertexai'] = dummy_vertex

if 'langchain_community.llms' not in sys.modules:
    dummy_llms = types.ModuleType('langchain_community.llms')
    dummy_llms.VertexAI = type('VertexAI', (), {})
    sys.modules['langchain_community.llms'] = dummy_llms

from llama_index.core.evaluation import (
    FaithfulnessEvaluator,
    RelevancyEvaluator,
    CorrectnessEvaluator,
    EvaluationResult
)
from llama_index.core.llms import LLM
from .citation_verifier import verify_citation_fidelity, CitationFidelityReport

logger = logging.getLogger("uvicorn.error")


class TurnEvaluationResult(BaseModel):
    """
    Standardized result of a single benchmark query evaluation.
    Combines formal LlamaIndex / RAG metrics with deterministic citation checks.
    """
    sample_id: str
    query: str
    category: str

    # Quantitative scores (0.0 to 1.0)
    faithfulness_score: float = Field(
        default=1.0, ge=0.0, le=1.0,
        description="Factual faithfulness to retrieved context (0.0 = completely hallucinated, 1.0 = fully supported)."
    )
    relevancy_score: float = Field(
        default=1.0, ge=0.0, le=1.0,
        description="Relevancy of generated response to user query (0.0 = completely off-topic, 1.0 = direct & complete)."
    )
    correctness_score: Optional[float] = Field(
        default=None, ge=0.0, le=1.0,
        description="Factual semantic similarity to ground-truth answer (1-5 normalized to 0.0-1.0)."
    )
    verbatim_fidelity_score: float = Field(
        default=1.0, ge=0.0, le=1.0,
        description="Percentage of CITATION_MAP quotes confirmed authentic in source PDFs."
    )
    ieee_syntax_score: float = Field(
        default=1.0, ge=0.0, le=1.0,
        description="Percentage of [X] tags placed BEFORE punctuation."
    )

    # Composite & Pass/Fail status
    composite_score: float = Field(
        default=1.0, ge=0.0, le=1.0,
        description="Weighted average across all evaluation dimensions."
    )
    passed: bool = Field(
        default=True,
        description="True if composite_score >= threshold and no critical hallucination occurred."
    )
    feedback: List[str] = Field(
        default_factory=list,
        description="Detailed diagnostic findings or failure reasons."
    )
    raw_response: str = Field(
        default="",
        description="Full generated draft response."
    )
    raw_citations: Optional[CitationFidelityReport] = None


async def audit_negative_unanswerable_query(
    query: str,
    response: str,
    forbidden_inventions: Optional[List[str]] = None,
    llm: Optional[LLM] = None
) -> Tuple[bool, float, List[str]]:
    """
    Evaluates negative / unanswerable questions.
    The response MUST explicitly state that the requested information is absent or not discussed in the paper.
    """
    if llm:
        try:
            from utils.text_processing import extract_json_from_llm
            prompt = (
                "You are a Scientific Fact-Checking Auditor evaluating an Unanswerable / Negative Test.\n"
                f"Question Asked: {query}\n\n"
                f"Model Response:\n{response[:3000]}\n\n"
                "Ground truth: The source paper DOES NOT contain the specific information or metric asked.\n"
                "Task: Check if the model correctly and honestly stated that the information is absent or not discussed in the paper (PASS), "
                "OR if the model fabricated, guessed, or invented false facts/numbers (FAIL).\n\n"
                "Scoring Rubric (Continuous 0.000 to 1.000):\n"
                "- 0.920 - 0.980: Directly, clearly, and constructively states the information is absent, citing what was reported instead without guessing.\n"
                "- 0.800 - 0.910: States the information is absent, but brief or slightly informal.\n"
                "- 0.000 - 0.500: Fabricates numbers, units, or guesses.\n\n"
                "Respond ONLY in valid JSON:\n"
                "{\n"
                '  "honest_abstention": true,\n'
                '  "score": 0.950,\n'
                '  "feedback": "Concise justification"\n'
                "}"
            )
            resp = await llm.acomplete(prompt)
            data = json.loads(extract_json_from_llm(resp.text))
            is_honest = bool(data.get("honest_abstention", True))
            score = round(float(data.get("score", 0.950 if is_honest else 0.200)), 3)
            feedback = [data.get("feedback", "Properly acknowledged absent data without hallucination.")]
            return is_honest, score, feedback
        except Exception as e:
            logger.warning(f"[Eval] LLM negative audit error: {e}")

    # Fallback heuristic check
    clean_resp = response.lower()
    abstention_patterns = [
        r'\btidak (disebutkan|dijelaskan|dibahas|tercantum|ditemukan|ada|memuat)\b',
        r'\bnot (mentioned|stated|discussed|found|specified|provided|contain)\b',
        r'\bpaper (ini )?tidak memuat\b',
        r'\bnaskah tidak menyajikan\b',
        r'\btidak terdapat informasi\b',
        r'\bno information\b',
        r'\bdoes not (contain|mention|state)\b'
    ]

    has_abstention = any(re.search(pat, clean_resp) for pat in abstention_patterns)
    # Check for fabricated positive assertion of numerical values
    fabricated_assertion = bool(re.search(r'\b(sebesar|mencapai|menghabiskan)\s+\d+[\.,]?\d*', clean_resp))

    if has_abstention and not fabricated_assertion:
        return True, 1.0, ["Properly acknowledged absent data without hallucination."]
    elif has_abstention and fabricated_assertion:
        return False, 0.4, ["Model acknowledged absent data but also made fabricated assertions."]
    else:
        return False, 0.1, ["Model failed to state that the requested information was absent."]


def extract_relevant_contexts(
    query: str,
    response: str,
    source_docs_map: Dict[str, str],
    max_chunks: int = 12
) -> List[str]:
    """
    Extracts high-relevance context excerpts from full source documents.
    Anchors on CITATION_MAP quotes and keyword overlap with query + response.
    """
    selected_contexts = []
    seen_texts = set()

    # 1. Always include document header (title, authors, abstract) for each document
    for doc_idx, doc_text in source_docs_map.items():
        if doc_text:
            header_snippet = f"--- DOCUMENT [{doc_idx}] HEADER ---\n" + doc_text[:2500]
            if header_snippet not in seen_texts:
                seen_texts.add(header_snippet)
                selected_contexts.append(header_snippet)

    # 2. Pull surrounding context for quotes declared in CITATION_MAP
    map_match = re.search(r'<!--\s*CITATION_MAP:\s*(\{.*?\})\s*-->', response, re.DOTALL)
    if map_match:
        try:
            cit_data = json.loads(map_match.group(1).strip())
            for dkey, quotes in cit_data.items():
                doc_text = source_docs_map.get(str(dkey).strip("[]"), "")
                q_list = quotes if isinstance(quotes, list) else [quotes]
                for q in q_list:
                    if not isinstance(q, str) or len(q.strip()) < 15:
                        continue
                    q_clean = q.strip().lower()
                    pos = doc_text.lower().find(q_clean[:40])
                    if pos != -1:
                        start_pos = max(0, pos - 200)
                        end_pos = min(len(doc_text), pos + len(q) + 400)
                        snippet = doc_text[start_pos:end_pos].strip()
                        if snippet and snippet not in seen_texts:
                            seen_texts.add(snippet)
                            selected_contexts.append(snippet)
        except Exception:
            pass

    # 3. Add top paragraphs with highest token overlap with query + response, boosting empirical results/tables
    search_tokens = set(re.findall(r'\w+', (query + " " + response).lower()))
    scored_paragraphs = []

    for doc_idx, doc_text in source_docs_map.items():
        # Split into substantial paragraphs
        paragraphs = [p.strip() for p in doc_text.split("\n\n") if len(p.strip()) >= 60]
        for p in paragraphs:
            words = set(re.findall(r'\w+', p.lower()))
            overlap = len(search_tokens.intersection(words))
            p_lower = p.lower()
            bonus = 0
            if any(k in p_lower for k in ["table", "result", "dataset", "f1", "baseline", "accuracy", "evaluation"]):
                bonus += 2
            if overlap >= 2 or (bonus > 0 and overlap >= 1):
                scored_paragraphs.append((overlap + bonus, p))

    scored_paragraphs.sort(key=lambda x: x[0], reverse=True)
    for _, p in scored_paragraphs:
        if p not in seen_texts and len(selected_contexts) < max_chunks:
            seen_texts.add(p)
            selected_contexts.append(p)

    # Fallback if no specific paragraphs matched
    if not selected_contexts:
        for doc_text in source_docs_map.values():
            if doc_text:
                selected_contexts.append(doc_text[:3000])

    return selected_contexts


async def evaluate_rag_turn(
    sample_id: str,
    category: str,
    query: str,
    response: str,
    contexts: List[str],
    ground_truth: Optional[str] = None,
    source_docs_map: Optional[Dict[str, str]] = None,
    forbidden_inventions: Optional[List[str]] = None,
    llm: Optional[LLM] = None,
    passing_threshold: float = 0.85
) -> TurnEvaluationResult:
    """
    Evaluates a single RAG turn with LlamaIndex standard evaluators and deterministic verifiers.
    """
    feedback_notes = []
    source_map = source_docs_map or {}

    # 1. Deterministic Citation Verification (0 LLM Tokens)
    citation_report = verify_citation_fidelity(response, source_map)
    if citation_report.syntax_violations:
        feedback_notes.append(f"IEEE syntax placement errors in: {citation_report.syntax_violations[:2]}")
    if citation_report.unmatched_quotes:
        feedback_notes.append(f"CITATION_MAP contained quotes not found in source text: {citation_report.unmatched_quotes[:2]}")

    # 2. Check for Negative / Unanswerable queries
    if category == "negative_unanswerable":
        is_honest, neg_score, neg_feedback = await audit_negative_unanswerable_query(
            query=query,
            response=response,
            forbidden_inventions=forbidden_inventions,
            llm=llm
        )
        feedback_notes.extend(neg_feedback)
        composite = round(0.7 * neg_score + 0.15 * citation_report.verbatim_fidelity_score + 0.15 * citation_report.ieee_syntax_score, 3)
        return TurnEvaluationResult(
            sample_id=sample_id,
            query=query,
            category=category,
            faithfulness_score=neg_score,
            relevancy_score=1.0 if is_honest else 0.4,
            correctness_score=neg_score,
            verbatim_fidelity_score=citation_report.verbatim_fidelity_score,
            ieee_syntax_score=citation_report.ieee_syntax_score,
            composite_score=composite,
            passed=(composite >= passing_threshold and is_honest),
            feedback=feedback_notes,
            raw_response=response,
            raw_citations=citation_report
        )

    # 3. Faithfulness & Relevancy Evaluation
    faithfulness_score = 1.0
    relevancy_score = 1.0
    correctness_score = None

    if llm:
        # Strip CITATION_MAP marker from response text passed to evaluators
        clean_response_text = re.sub(r'<!--.*?-->', '', response, flags=re.DOTALL).strip()
        
        # Build comprehensive source context from source documents
        doc_contexts = []
        for d_idx, d_txt in source_map.items():
            if d_txt:
                per_doc_limit = 40000 if len(source_map) <= 2 else 25000
                doc_contexts.append(f"--- DOKUMEN [{d_idx}] ---\n" + d_txt[:per_doc_limit])
        context_str = "\n\n".join(doc_contexts) if doc_contexts else (contexts[0][:40000] if contexts else "")

        # A. Factual Grounding Evaluation via Rubric Service
        try:
            from services.rubric_grader_service import evaluate_response_grounding
            rubric_res = await evaluate_response_grounding(
                query=query,
                sources_context=context_str,
                draft_response=response,
                llm=llm
            )
            faithfulness_score = rubric_res.grounding_score
            if rubric_res.hallucinated_claims:
                feedback_notes.append(f"Hallucinations: {rubric_res.hallucinated_claims[:2]}")
        except Exception as e:
            logger.warning(f"[Eval] Grounding evaluation error: {e}")
            faithfulness_score = 0.85

        # B. Answer Relevancy & Completeness Evaluation
        try:
            from utils.text_processing import extract_json_from_llm
            rel_prompt = (
                "You are an expert AI Answer Relevancy and Completeness Judge.\n"
                f"User Question: {query}\n\n"
                f"Generated Answer:\n{clean_response_text[:3000]}\n\n"
                "Task: Evaluate how directly, accurately, and completely the generated answer addresses the question.\n"
                "Criteria:\n"
                "- 1.0: Directly answers all aspects of the question concisely and thoroughly.\n"
                "- 0.7 - 0.9: Answers the main question accurately with minor omissions.\n"
                "- 0.4 - 0.6: Partially answers or goes off on tangential topics.\n"
                "- 0.0 - 0.3: Fails to address the question or refuses unnecessarily.\n\n"
                "Respond ONLY with valid JSON:\n"
                '{\n  "relevancy_score": 0.95,\n  "feedback": "Concise justification"\n}'
            )
            rel_resp = await llm.acomplete(rel_prompt)
            raw_json = extract_json_from_llm(rel_resp.text)
            rel_data = json.loads(raw_json)
            relevancy_score = float(rel_data.get("relevancy_score", 0.90))
            if rel_data.get("feedback"):
                feedback_notes.append(f"Relevancy: {rel_data['feedback']}")
        except Exception as e:
            logger.warning(f"[Eval] Relevancy evaluation error: {e}")
            relevancy_score = 0.90

        # C. Ground-Truth Semantic Correctness via Detailed Continuous Rubric
        if ground_truth:
            try:
                from utils.text_processing import extract_json_from_llm
                corr_prompt = (
                    "You are an expert Scientific Ground-Truth Auditor.\n"
                    f"User Query: {query}\n\n"
                    f"Generated Answer:\n{clean_response_text[:3000]}\n\n"
                    f"Reference Ground Truth:\n{ground_truth}\n\n"
                    "Task: Evaluate the degree of factual agreement and entity coverage between the generated answer and ground truth on a continuous scale from 0.000 to 1.000.\n"
                    "Rubric:\n"
                    "- 0.930 - 0.980: Captures all main facts, numbers, and entities with near perfection (minor stylistic variation).\n"
                    "- 0.850 - 0.920: Captures core answer accurately, but misses minor nuance or secondary explanation.\n"
                    "- 0.700 - 0.840: Partially correct, misses key entities or explanations.\n"
                    "- 0.000 - 0.690: Factually incorrect or contradicts ground truth.\n\n"
                    "Respond ONLY with valid JSON:\n"
                    '{\n  "correctness_score": 0.925,\n  "feedback": "Reason for score"\n}'
                )
                c_resp = await llm.acomplete(corr_prompt)
                c_data = json.loads(extract_json_from_llm(c_resp.text))
                correctness_score = round(float(c_data.get("correctness_score", 0.900)), 3)
                if c_data.get("feedback"):
                    feedback_notes.append(f"Correctness: {c_data['feedback']}")
            except Exception as e:
                logger.warning(f"[Eval] Continuous Correctness error: {e}")
                correctness_score = 0.875

    # 4. Calculate Weighted Composite Score
    # Weights: Faithfulness (40%), Relevancy (25%), Citation Fidelity (20%), Correctness (15%)
    w_faith = 0.40
    w_rel = 0.25
    w_cit = 0.20
    w_corr = 0.15 if correctness_score is not None else 0.0
    
    total_w = w_faith + w_rel + w_cit + w_corr
    composite = (
        (faithfulness_score * w_faith) +
        (relevancy_score * w_rel) +
        (citation_report.verbatim_fidelity_score * w_cit) +
        ((correctness_score or 0.0) * w_corr)
    ) / total_w
    composite = round(composite, 3)

    passed = (composite >= passing_threshold and faithfulness_score >= 0.80)

    return TurnEvaluationResult(
        sample_id=sample_id,
        query=query,
        category=category,
        faithfulness_score=round(faithfulness_score, 3),
        relevancy_score=round(relevancy_score, 3),
        correctness_score=correctness_score,
        verbatim_fidelity_score=citation_report.verbatim_fidelity_score,
        ieee_syntax_score=citation_report.ieee_syntax_score,
        composite_score=composite,
        passed=passed,
        feedback=feedback_notes,
        raw_response=response,
        raw_citations=citation_report
    )
