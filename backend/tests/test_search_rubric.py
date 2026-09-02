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
