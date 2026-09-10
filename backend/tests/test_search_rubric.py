import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from services.search.llm_evaluator_service import judge_and_filter_papers_with_llm

def test_judge_and_filter_papers_with_mock_llm():
    mock_llm = MagicMock()
    mock_response = MagicMock()
    # Mock LLM choosing indices 1 and 2 (filtering out index 0 which is off-topic dental crack)
    mock_response.text = "[1, 2]"
    mock_llm.acomplete = AsyncMock(return_value=mock_response)

    candidates = [
        {
            "id": 101,
            "title": "Automated Detection of Dental Enamel Cracks using Optical Coherence",
            "snippet": "We study crack propagation in human teeth using optical coherence tomography."
        },
        {
            "id": 102,
            "title": "Deep Learning Framework for Asphalt Road Pavement Distress and Crack Segmentation",
            "snippet": "This paper presents YOLOv8 for automated crack detection on highway asphalt surfaces."
        },
        {
            "id": 103,
            "title": "UAV-Based Asphalt Pothole and Crack Identification in Smart Cities",
            "snippet": "Aerial surveillance for highway pavement monitoring with convolutional neural networks."
        }
    ]

    query = "AI for asphalt road crack detection"
    result = asyncio.run(judge_and_filter_papers_with_llm(query, candidates, target_count=2, llm=mock_llm))

    assert len(result) == 2
    assert result[0]["id"] == 102
    assert result[1]["id"] == 103
    # Check that off-topic candidate 101 was strictly filtered out
    assert not any(r["id"] == 101 for r in result)

def test_judge_and_filter_empty_candidates():
    result = asyncio.run(judge_and_filter_papers_with_llm("test query", [], 5, None))
    assert result == []

def test_judge_and_filter_none_llm_fallback():
    candidates = [{"title": "Paper A"}, {"title": "Paper B"}]
    result = asyncio.run(judge_and_filter_papers_with_llm("test query", candidates, 1, None))
    assert len(result) == 1
    assert result[0]["title"] == "Paper A"

def test_search_synthesis_prompt_transparency_directives():
    """Verify prompt synthesis includes quota cap notice, undershoot discrepancy, and filter conflict warning."""
    from rag.prompts import get_search_synthesis_prompt

    # Case 1: Capped search (user asked 500, capped at 25)
    prompt_capped = get_search_synthesis_prompt(
        user_query="cariin 500 paper kanker",
        paper_count=25,
        papers_context="Paper context here",
        user_requested_count=500,
        is_capped=True,
        cap_limit=25
    )
    assert "HARD CAP TRANSPARENCY NOTICE" in prompt_capped
    assert "500 papers" in prompt_capped
    assert "25 papers" in prompt_capped

    # Case 2: Undershoot discrepancy (user asked 10, but only 6 found)
    prompt_undershoot = get_search_synthesis_prompt(
        user_query="find 10 papers about rare bone cyst",
        paper_count=6,
        papers_context="Paper context here",
        user_requested_count=10,
        is_capped=False
    )
    assert "QUOTA DISCREPANCY TRANSPARENCY" in prompt_undershoot
    assert "10 papers" in prompt_undershoot
    assert "6 papers" in prompt_undershoot

    # Case 3: Filter conflict override notification
    prompt_conflict = get_search_synthesis_prompt(
        user_query="cari paper indonesia",
        paper_count=12,
        papers_context="Paper context here",
        filter_conflicts=["Prompt requested Indonesian papers while UI filter was set to Mandarin"]
    )
    assert "FILTER PREFERENCE OVERRIDE ACKNOWLEDGMENT" in prompt_conflict
    assert "Mandarin" in prompt_conflict

