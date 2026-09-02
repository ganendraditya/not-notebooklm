import pytest
from unittest.mock import AsyncMock, MagicMock
from services.rubric_grader_service import (
    RubricEvaluationResult,
    build_grounding_rubric_prompt,
    parse_rubric_json_response,
    evaluate_response_grounding
)

def test_parse_rubric_json_response_valid():
    raw_json = '''
    ```json
    {
        "is_grounded": true,
        "grounding_score": 0.98,
        "citation_accuracy": true,
        "hallucinated_claims": [],
        "revision_instruction": null
    }
    ```
    '''
    res = parse_rubric_json_response(raw_json)
    assert res.is_grounded is True
    assert res.grounding_score == 0.98
    assert res.citation_accuracy is True
    assert len(res.hallucinated_claims) == 0

def test_parse_rubric_json_response_hallucinated():
    raw_json = '''
    {
        "is_grounded": false,
        "grounding_score": 0.45,
        "citation_accuracy": false,
        "hallucinated_claims": ["Penulis mengklaim akurasi 99% padahal di dokumen hanya 85%"],
        "revision_instruction": "Perbaiki angka akurasi menjadi 85% sesuai Dokumen [1]."
    }
    '''
    res = parse_rubric_json_response(raw_json)
    assert res.is_grounded is False
    assert res.grounding_score == 0.45
    assert res.citation_accuracy is False
    assert len(res.hallucinated_claims) == 1
    assert "85%" in res.revision_instruction

def test_parse_rubric_json_response_malformed_fallback():
    raw_bad = "Maaf saya AI tidak bisa memproses format JSON."
    res = parse_rubric_json_response(raw_bad)
    # Harus fallback aman (tidak boleh throw error/crash)
    assert isinstance(res, RubricEvaluationResult)
    assert res.is_grounded is True

def test_evaluate_response_grounding_with_mock_llm():
    import asyncio
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.text = '{"is_grounded": true, "grounding_score": 1.0, "citation_accuracy": true, "hallucinated_claims": [], "revision_instruction": null}'
    mock_llm.acomplete = AsyncMock(return_value=mock_response)

    sources = "Dokumen [1]: Algoritma CNN memiliki akurasi 92% pada dataset X."
    draft = "Berdasarkan penelitian pada Dokumen [1], metode CNN mencapai tingkat akurasi sebesar 92% ketika diuji pada dataset X. Penelitian ini membuktikan keandalan model dalam klasifikasi gambar secara mendalam dan menyeluruh pada berbagai kondisi pengujian eksperimental."
    query = "Berapa akurasi metode CNN?"

    result = asyncio.run(evaluate_response_grounding(query, sources, draft, mock_llm))
    assert result.is_grounded is True
    assert result.grounding_score == 1.0
    mock_llm.acomplete.assert_called_once()
