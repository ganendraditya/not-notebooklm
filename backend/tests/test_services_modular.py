import os
import io
import pytest
from fastapi.testclient import TestClient
from main import app
from database import get_db, SessionLocal, Document, ChatSession
from services.document import extract_and_enrich_uploaded_file, calculate_doc_quality
from utils.file_utils import sanitize_paper_filename, get_doc_file_path, make_content_disposition
from utils.text_processing import clean_doi, normalize_title_str, is_valid_academic_title
from utils.pdf_utils import is_authentic_pdf_bytes
from rag.formatters import format_clean_response, extract_structured_citations

client = TestClient(app)

def test_file_utils_sanitization():
    """Verify filename sanitization cleans invalid chars and limits length safely."""
    raw = 'A <Novel> Approach: Fast & "Deep" Learning in 2024 / Version | 1.0?'
    sanitized = sanitize_paper_filename(raw, max_length=50)
    assert sanitized.endswith(".pdf")
    assert "<" not in sanitized
    assert ">" not in sanitized
    assert ":" not in sanitized
    assert "/" not in sanitized
    assert "\\" not in sanitized
    assert "|" not in sanitized

def test_make_content_disposition():
    """Verify RFC 5987 Unicode content disposition header."""
    header = make_content_disposition("attachment", "Laporan Riset AI.pdf")
    assert 'attachment; filename="Laporan Riset AI.pdf"' in header
    assert "filename*=UTF-8''" in header
    assert "Laporan%20Riset%20AI.pdf" in header

def test_text_processing_doi_and_title():
    """Verify DOI cleaning and title normalization."""
    assert clean_doi("https://doi.org/10.1016/j.jbi.2021.103789.") == "10.1016/j.jbi.2021.103789"
    assert clean_doi("**doi:10.1109/TPAMI.2020.1234567**") == "10.1109/TPAMI.2020.1234567"
    assert normalize_title_str("Deep Learning for Health.pdf") == "deep learning for health"
    assert is_valid_academic_title("Table of Contents") is False
    assert is_valid_academic_title("Attention Is All You Need") is True

def test_pdf_authenticity_check():
    """Verify authentic PDF bytes header detection."""
    fake_bytes = b"This is just plain text, not a pdf file"
    assert is_authentic_pdf_bytes(fake_bytes, min_size=10) is False
    
    real_header = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n" + b"A" * 1200
    assert is_authentic_pdf_bytes(real_header, min_size=1000) is True

def test_services_modular_integration(tmp_path):
    """Verify service layer functions work end-to-end with temporary artifacts."""
    sample_file = tmp_path / "sample.txt"
    sample_file.write_text("# Test Research Paper (2024)\n\nDOI: 10.1234/test.2024\n\nAbstract\nThis is a test abstract.", encoding="utf-8")
    
    enriched = extract_and_enrich_uploaded_file(str(sample_file), "sample.txt")
    assert enriched["title"] == "sample"
    assert enriched["doi"] == "10.1234/test.2024"

def test_rag_formatters():
    """Verify clean response formatting and deterministic citation extraction."""
    raw_response = (
        "Here is the synthesized analysis of the papers [1].\n\n"
        "<!-- CITATION_MAP: {\"1\": [\"Exact quote from document 1\"]} -->"
    )
    clean_formatted = format_clean_response(raw_response)
    assert "<!-- CITATION_MAP:" in clean_formatted
    
    clean_text, citations = extract_structured_citations(raw_response)
    assert clean_text == "Here is the synthesized analysis of the papers [1]."
    assert citations == {"1": ["Exact quote from document 1"]}

