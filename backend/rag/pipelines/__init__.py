"""Pipelines package for modular intent processing."""
from .chat_pipeline import handle_general_chat_pipeline
from .source_action_pipeline import handle_source_removal_pipeline
from .search_pipeline import handle_academic_search_pipeline
from .workspace_pipeline import handle_workspace_analysis_pipeline

__all__ = [
    "handle_general_chat_pipeline",
    "handle_source_removal_pipeline",
    "handle_academic_search_pipeline",
    "handle_workspace_analysis_pipeline",
]
