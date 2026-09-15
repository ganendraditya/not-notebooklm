"""
Evaluation metrics package for Not-NotebookLM.
Contains deterministic citation verifiers, LlamaIndex evaluators, and composite benchmark metrics.
"""

from .citation_verifier import verify_citation_fidelity, CitationFidelityReport

__all__ = [
    "verify_citation_fidelity",
    "CitationFidelityReport",
]
