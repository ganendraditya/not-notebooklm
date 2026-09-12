"""
LLM Evaluator Service for Academic Search & Metadata.
Facade re-exporting query planning, paper judging, and metadata auditing modules.
"""

from .query_planner import plan_academic_search
from .paper_judge import judge_and_filter_papers_with_llm
from .metadata_auditor import audit_paper_metadata_with_ai

__all__ = [
    "plan_academic_search",
    "judge_and_filter_papers_with_llm",
    "audit_paper_metadata_with_ai",
]
