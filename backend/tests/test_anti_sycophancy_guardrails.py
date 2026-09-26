"""
Unit tests for Issue #44:
- Anti-Sycophancy Guardrails
- Closed-Book Boundary Honesty & Anti-Parametric Leakage
- No-blaming user file integrity
- Tool Effect Gating & Authority Check Invariant
"""

import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from rag.prompts import (
    get_general_chat_system_prompt,
    get_workspace_analysis_system_prompt,
)


def test_general_chat_prompt_contains_anti_sycophancy_and_boundary_honesty():
    prompt = get_general_chat_system_prompt()
    
    # 1. Closed-Book & Anti-Parametric Leakage
    assert "CLOSED-BOOK BOUNDARY HONESTY" in prompt
    assert "parametric memory" in prompt.lower()
    assert "This detail is not found in the documents currently available" in prompt
    assert "NEVER blame the user's file integrity" in prompt

    # 2. Anti-Sycophancy & Objective Skepticism
    assert "ANTI-SYCOPHANCY & OBJECTIVE SKEPTICISM" in prompt
    assert "sycophantic agreement" in prompt.lower()
    assert "flip-flop" in prompt.lower()
    assert "Based on the excerpts available to me, data X is not recorded" in prompt

    # 3. Tool Effect Gating & Authority Checks
    assert "TOOL EFFECT GATING & AUTHORITY CHECKS" in prompt
    assert "licensed action" in prompt.lower()
    assert "flattering" in prompt.lower()


def test_workspace_analysis_prompt_contains_anti_sycophancy_and_boundary_honesty():
    prompt = get_workspace_analysis_system_prompt(doc_count=3)

    # 1. Closed-Book & Universal Factuality
    assert "NO PARAMETRIC LEAKAGE" in prompt
    assert "DIRECT NEGATIVE ABSTENTION" in prompt
    assert "NO USER UPLOAD BLAME" in prompt
    assert "This detail is not found in the documents currently available in the system" in prompt

    # 2. Anti-Sycophancy & Objective Skepticism
    assert "ANTI-SYCOPHANCY & OBJECTIVE SKEPTICISM" in prompt
    assert "sycophantic agreement" in prompt.lower()
    assert "flip-flop" in prompt.lower()
    assert "Based on the excerpts available to me, data X is not recorded" in prompt

    # 3. Tool Effect Gating & Authority Checks
    assert "TOOL EFFECT GATING (AUTHORITY CHECK INVARIANT)" in prompt
    assert "licensed action" in prompt.lower()
    assert "flattering" in prompt.lower()


@pytest.mark.asyncio
async def test_simulated_user_pushback_anti_sycophancy_defense():
    """
    Simulates a multi-turn conversation where user aggressively contradicts the model
    without providing textual proof, ensuring system prompt instructions remain firm.
    """
    prompt = get_workspace_analysis_system_prompt(doc_count=1)
    
    # Ensure guardrail strictly forbids concession without quote verification
    assert "CALIBRATED CORRECTION (DO NOT BE DOGMATICALLY STUBBORN)" in prompt
    assert "verifiable, verbatim textual proof" in prompt
