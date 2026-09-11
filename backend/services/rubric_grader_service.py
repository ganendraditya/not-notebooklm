import json
import re
import logging
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from llama_index.core.llms import LLM

logger = logging.getLogger("uvicorn.error")

MIN_GROUNDING_THRESHOLD = 0.85
MIN_ACADEMIC_QUALITY_THRESHOLD = 0.85

class RubricEvaluationResult(BaseModel):
    """
    Structured outcome of the Rubric-Checked Grounding evaluation.
    Orthogonal & easily serializable.
    """
    is_grounded: bool = Field(
        default=True, 
        description="True if the draft response is strictly grounded in the provided source materials."
    )
    grounding_score: float = Field(
        default=1.0, 
        ge=0.0, 
        le=1.0, 
        description="Confidence score of factual grounding (0.0 = completely hallucinated, 1.0 = fully grounded)."
    )
    citation_accuracy: bool = Field(
        default=True, 
        description="True if all document citation tags (e.g. [1], [2]) correspond to factual statements present in the cited document, and inline citation coverage & CITATION_MAP are fully provided."
    )
    hallucinated_claims: List[str] = Field(
        default_factory=list, 
        description="List of specific claims/facts found in draft that are NOT supported by source documents."
    )
    revision_instruction: Optional[str] = Field(
        default=None, 
        description="Constructive guidance for the Generator LLM to fix hallucinated parts or bad citations."
    )

def build_grounding_rubric_prompt(query: str, sources_context: str, draft_response: str) -> str:
    """
    Pure prompt constructor adhering to DRY & Orthogonality.
    Defines strict academic grounding criteria.
    """
    return (
        "You are an expert Academic Fact-Checker, Citation Auditor, and Scientific Peer Reviewer.\n"
        "Your task: Strictly audit a generated draft response against the verified source documents.\n\n"
        "=== SOURCE DOCUMENTS CONTEXT ===\n"
        f"{sources_context}\n\n"
        "=== USER QUERY ===\n"
        f"{query}\n\n"
        "=== GENERATED DRAFT RESPONSE TO AUDIT ===\n"
        f"{draft_response}\n\n"
        "=== GROUNDING & CITATION RUBRIC ===\n"
        "1. FACTUAL GROUNDING & EVIDENCE INTEGRITY:\n"
        "   - Every claim, statistic, empirical result, or methodological statement in the draft MUST be explicitly stated in or directly inferred from the SOURCE DOCUMENTS.\n"
        "   - If the user asks for facts/methods that ARE PRESENT in the source documents, the draft MUST NOT falsely claim they are missing or unavailable.\n"
        "   - If the draft brings in outside general knowledge not present in sources as if it were from the documents, mark it as ungrounded.\n"
        "2. CITATION COVERAGE & INTERACTIVE EVIDENCE BUTTONS AUDIT:\n"
        "   - Key empirical claims, quantitative metrics, and dataset findings in paragraphs or table cells SHOULD have granular bracketed citation tags [X] (e.g. [1], [2]) directly beside them.\n"
        "   - Check that cited Document [X] actually contains the specific claim or metric.\n"
        "   - Check the <!-- CITATION_MAP: ... --> payload at the end: If documents are cited, the draft MUST include this block with authentic verbatim sentence extracts from the source text. If missing, empty, or malformed, mark citation_accuracy: false.\n"
        "3. NO SPECULATION AS FACT:\n"
        "   - If source documents do not contain certain information requested by the user, the draft should acknowledge this rather than fabricating details.\n\n"
        "OUTPUT FORMAT REQUIREMENTS:\n"
        "You MUST respond ONLY with a valid JSON object matching this exact schema (no markdown wrap or extra commentary):\n"
        "{\n"
        '  "is_grounded": true,\n'
        '  "grounding_score": 0.95,\n'
        '  "citation_accuracy": true,\n'
        '  "hallucinated_claims": ["claim 1 if any"],\n'
        '  "revision_instruction": "Instruction on what to remove/fix if is_grounded or citation_accuracy is false, else null"\n'
        "}"
    )

def parse_rubric_json_response(raw_text: str) -> RubricEvaluationResult:
    """
    Safely parses JSON output from LLM, handling potential markdown wraps or formatting nuances.
    """
    clean_text = raw_text.strip()
    clean_text = re.sub(r'^```(?:json)?\s*', '', clean_text, flags=re.I)
    clean_text = re.sub(r'\s*```$', '', clean_text)
    
    try:
        data = json.loads(clean_text)
        return RubricEvaluationResult(
            is_grounded=bool(data.get("is_grounded", True)),
            grounding_score=float(data.get("grounding_score", 1.0)),
            citation_accuracy=bool(data.get("citation_accuracy", True)),
            hallucinated_claims=list(data.get("hallucinated_claims", [])),
            revision_instruction=data.get("revision_instruction")
        )
    except Exception as e:
        logger.warning(f"[RubricGrader] Failed to parse JSON response: {e}. Raw: {raw_text[:200]}")
        return RubricEvaluationResult(
            is_grounded=False,
            grounding_score=0.0,
            citation_accuracy=False,
            hallucinated_claims=[f"Auditor JSON parse failure: {str(e)}"],
            revision_instruction=None
        )

async def evaluate_response_grounding(
    query: str,
    sources_context: str,
    draft_response: str,
    llm: Optional[LLM]
) -> RubricEvaluationResult:
    """
    Evaluates a generated draft response against the provided sources using an LLM Auditor.
    
    Args:
        query: Original user question / prompt
        sources_context: Text of source documents provided to the generator
        draft_response: Draft text produced by the generator
        llm: LLM instance to perform the evaluation
        
    Returns:
        RubricEvaluationResult with grounding status, score, and revision instructions.
    """
    # Guard: If no LLM or empty context, return neutral pass
    if not llm or not sources_context.strip() or not draft_response.strip():
        return RubricEvaluationResult(
            is_grounded=True,
            grounding_score=1.0,
            citation_accuracy=True,
            hallucinated_claims=[],
            revision_instruction=None
        )
    
    # Avoid grading very short conversational replies (e.g., "Halo!", "Sama-sama")
    if len(draft_response.strip().split()) < 25:
        return RubricEvaluationResult(
            is_grounded=True,
            grounding_score=1.0,
            citation_accuracy=True,
            hallucinated_claims=[],
            revision_instruction=None
        )

    try:
        prompt = build_grounding_rubric_prompt(
            query=query,
            sources_context=sources_context[:25000], # Safe window slice
            draft_response=draft_response
        )
        resp = await llm.acomplete(prompt)
        return parse_rubric_json_response(resp.text)
    except Exception as e:
        logger.warning(f"[RubricGrader] Evaluation execution failed: {e}")
        return RubricEvaluationResult(
            is_grounded=False,
            grounding_score=0.0,
            citation_accuracy=False,
            hallucinated_claims=[f"Auditor execution failure: {str(e)}"],
            revision_instruction=None
        )

class AcademicWritingRubricResult(BaseModel):
    """
    Structured outcome of the Academic Tone, Structure & Synthesis Quality Rubric.
    """
    is_academic_ready: bool = Field(default=True, description="True if text meets rigorous scientific writing standards.")
    quality_score: float = Field(default=1.0, ge=0.0, le=1.0, description="Overall academic quality score (0.0 - 1.0).")
    informal_phrases_found: List[str] = Field(default_factory=list, description="Non-academic / informal / colloquial expressions found.")
    structural_critique: Optional[str] = Field(default=None, description="Critique on IMRaD structure, methodology depth, or analytical synthesis.")
    revision_guide: Optional[str] = Field(default=None, description="Actionable recommendations for academic refinement.")

def build_academic_writing_rubric_prompt(topic: str, draft_text: str) -> str:
    """
    Prompt constructor for auditing formal academic drafts, chapter drafts, or literature reviews.
    """
    return (
        "You are an Academic Journal Chief Editor and Senior Peer Reviewer.\n"
        "Your task: Strictly audit an academic draft/synthesis against international scientific publishing standards.\n\n"
        f"Topic / Context:\n{topic}\n\n"
        f"Draft Text to Audit:\n{draft_text}\n\n"
        "=== ACADEMIC WRITING RUBRIC ===\n"
        "1. FORMAL ACADEMIC TONE:\n"
        "   - Zero colloquialism, conversational chatter, or emotional/unsupported adjectives.\n"
        "   - Objective, precise academic diction (Indonesian formal ilmiah or English academic standard).\n"
        "2. STRUCTURAL COMPLETENESS & COHERENCE:\n"
        "   - Logical flow between problem background, empirical evidence, methodology, and synthesis.\n"
        "   - Clear comparative synthesis (avoid shallow bullet dumps without analytical context).\n"
        "3. CITATION HYGIENE:\n"
        "   - Factual claims and metrics must be backed by consistent citations.\n\n"
        "OUTPUT FORMAT (STRICT JSON ONLY):\n"
        "{\n"
        '  "is_academic_ready": true,\n'
        '  "quality_score": 0.95,\n'
        '  "informal_phrases_found": [],\n'
        '  "structural_critique": "Critique if quality is sub-par, else null",\n'
        '  "revision_guide": "Specific guide to elevate text if needed, else null"\n'
        "}"
    )

def parse_academic_writing_rubric_json(raw_text: str) -> AcademicWritingRubricResult:
    clean_text = raw_text.strip()
    clean_text = re.sub(r'^```(?:json)?\s*', '', clean_text, flags=re.I)
    clean_text = re.sub(r'\s*```$', '', clean_text)
    try:
        data = json.loads(clean_text)
        return AcademicWritingRubricResult(
            is_academic_ready=bool(data.get("is_academic_ready", True)),
            quality_score=float(data.get("quality_score", 1.0)),
            informal_phrases_found=list(data.get("informal_phrases_found", [])),
            structural_critique=data.get("structural_critique"),
            revision_guide=data.get("revision_guide")
        )
    except Exception as e:
        logger.warning(f"[RubricGrader] Failed to parse academic writing rubric JSON: {e}")
        return AcademicWritingRubricResult(
            is_academic_ready=False,
            quality_score=0.0,
            informal_phrases_found=[],
            structural_critique=f"Auditor JSON parse failure: {str(e)}",
            revision_guide=None
        )

async def evaluate_academic_writing_quality(
    topic: str,
    draft_text: str,
    llm: Optional[LLM]
) -> AcademicWritingRubricResult:
    """
    Audits a draft text against formal academic publication standards.
    """
    if not llm or not draft_text.strip() or len(draft_text.strip().split()) < 30:
        return AcademicWritingRubricResult(
            is_academic_ready=True,
            quality_score=1.0,
            informal_phrases_found=[],
            structural_critique=None,
            revision_guide=None
        )

    try:
        prompt = build_academic_writing_rubric_prompt(topic, draft_text[:20000])
        resp = await llm.acomplete(prompt)
        return parse_academic_writing_rubric_json(resp.text)
    except Exception as e:
        logger.warning(f"[RubricGrader] Academic writing audit execution failed: {e}")
        return AcademicWritingRubricResult(
            is_academic_ready=False,
            quality_score=0.0,
            informal_phrases_found=[],
            structural_critique=f"Auditor execution failure: {str(e)}",
            revision_guide=None
        )
