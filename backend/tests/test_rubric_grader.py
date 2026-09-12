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
    assert res.is_grounded is False
    assert res.grounding_score == 0.0
    assert len(res.hallucinated_claims) > 0

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

def test_parse_academic_writing_rubric_json():
    from services.rubric_grader_service import parse_academic_writing_rubric_json
    raw = '''
    ```json
    {
        "is_academic_ready": true,
        "quality_score": 0.96,
        "informal_phrases_found": [],
        "structural_critique": null,
        "revision_guide": null
    }
    ```
    '''
    res = parse_academic_writing_rubric_json(raw)
    assert res.is_academic_ready is True
    assert res.quality_score == 0.96
    assert len(res.informal_phrases_found) == 0

def test_evaluate_academic_writing_quality_with_mock():
    import asyncio
    from services.rubric_grader_service import evaluate_academic_writing_quality
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.text = '{"is_academic_ready": true, "quality_score": 0.92, "informal_phrases_found": [], "structural_critique": null, "revision_guide": null}'
    mock_llm.acomplete = AsyncMock(return_value=mock_response)

    draft = (
        "Penelitian ini menginvestigasi dampak augmentasi data terhadap akurasi klasifikasi citra medis pneumonia "
        "menggunakan arsitektur deep learning ResNet-50 dan membandingkannya secara komparatif dengan model VGG-16. "
        "Metodologi yang diusulkan menguji ketahanan model pada variasi dataset rontgen dada sebanyak 1.200 sampel "
        "dengan skema validasi silang lima lipatan (5-fold cross validation) untuk memastikan generalisasi fitur visual."
    )
    res = asyncio.run(evaluate_academic_writing_quality("Medical Imaging Classification", draft, mock_llm))
    assert res.is_academic_ready is True
    assert res.quality_score == 0.92

def test_build_grounding_rubric_prompt_checks_citation_coverage():
    prompt = build_grounding_rubric_prompt("Bandingkan metode", "Doc 1 data", "Draft table")
    assert "CITATION COVERAGE & INTERACTIVE EVIDENCE BUTTONS AUDIT" in prompt
    assert "CITATION_MAP" in prompt
    assert "table cells" in prompt.lower()
