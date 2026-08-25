import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_root_or_health():
    """Verify backend root / chats endpoint is responsive."""
    response = client.get("/chats")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_chat_lifecycle():
    """Test creating, fetching, renaming, and deleting a chat session."""
    # 1. Create chat
    res_create = client.post("/chats", json={"title": "Pytest Test Chat"})
    assert res_create.status_code == 200
    chat_data = res_create.json()
    chat_id = chat_data["id"]
    assert chat_data["title"] == "Pytest Test Chat"

    # 2. Get chat detail
    res_get = client.get(f"/chats/{chat_id}")
    assert res_get.status_code == 200
    assert res_get.json()["id"] == chat_id

    # 3. Rename chat
    res_patch = client.patch(f"/chats/{chat_id}", json={"title": "Renamed Chat"})
    assert res_patch.status_code == 200
    assert res_patch.json()["title"] == "Renamed Chat"

    # 4. Delete chat
    res_del = client.delete(f"/chats/{chat_id}")
    assert res_del.status_code == 200

    # 5. Verify deleted
    res_check = client.get(f"/chats/{chat_id}")
    assert res_check.status_code == 404

def test_flashrank_reranker():
    """Verify FlashRank cross-encoder loads and ranks passages properly."""
    from flashrank import Ranker, RerankRequest
    ranker = Ranker(model_name="ms-marco-TinyBERT-L-2-v2")
    passages = [
        {"id": 1, "text": "Deep learning and LSTM for precipitation and rainfall forecasting."},
        {"id": 2, "text": "Recipe for chocolate cake and vanilla cupcakes."}
    ]
    req = RerankRequest(query="rainfall machine learning prediction", passages=passages)
    ranked = ranker.rerank(req)
    assert len(ranked) == 2
    assert ranked[0]["id"] == 1

def test_section_aware_academic_chunker():
    """Verify section splitter accurately preserves breadcrumbs, tables, and IMRaD canonical tags."""
    from rag.parsers import split_markdown_into_academic_sections, classify_canonical_section
    
    assert classify_canonical_section("1. Introduction") == "introduction"
    assert classify_canonical_section("2. Methodology & Materials") == "methodology"
    assert classify_canonical_section("3. Results & Discussion") in ("results", "discussion")
    assert classify_canonical_section("4. Limitations") == "limitations"
    
    sample_paper_md = """# AI in Sports Medicine (2024)

## 1. Introduction
Artificial intelligence is rapidly transforming injury diagnosis in professional sports.

## 2. Methods
We conducted a randomized trial with 450 athletes.

### 2.1 Participant Demographics
| Group | Sample Size (n) | Age |
|---|---|---|
| Control | 225 | 24.1 |
| Treatment | 225 | 23.8 |

### 2.2 Intervention Protocol
Athletes in the treatment group were monitored via computer vision tracking.

## 3. Results & Findings
The treatment group demonstrated a 34% decrease in muscular reinjury rates.
"""
    sections = split_markdown_into_academic_sections(sample_paper_md, filename="sports_ai.pdf")
    assert len(sections) >= 3
    
    # Verify breadcrumb propagation
    demo_sec = next((s for s in sections if "Demographics" in s["breadcrumb"]), None)
    assert demo_sec is not None
    assert demo_sec["canonical_section"] == "methodology"
    assert "2. Methods > 2.1 Participant Demographics" in demo_sec["breadcrumb"]
    assert "| Sample Size (n) |" in demo_sec["text"]
    assert "Section: AI in Sports Medicine (2024) > 2. Methods > 2.1 Participant Demographics" in demo_sec["text"]

def test_lru_cache_eviction():
    """Verify LRUMetadataCache bounded capacity works and evicts oldest items."""
    from rag.search import LRUMetadataCache
    cache = LRUMetadataCache(capacity=3)
    cache.set("a", {"title": "Paper A"})
    cache.set("b", {"title": "Paper B"})
    cache.set("c", {"title": "Paper C"})
    assert "a" in cache
    
    # Add 4th item to trigger eviction of oldest (a)
    cache.set("d", {"title": "Paper D"})
    assert "d" in cache
    assert "b" in cache
    assert "c" in cache
    assert "a" not in cache

def test_document_service_quality_calculator(tmp_path):
    """Verify document quality calculator prioritizes full PDFs with DOI and high citations."""
    from services.document_service import calculate_doc_quality
    from database import Document
    
    doc_stub = Document(
        id=1,
        chat_id="test_chat",
        filename="test_stub.pdf",
        title="Stub Paper",
        doi="10.1234/test",
        authors='["Author A"]',
        journal="Journal of AI",
        abstract="Brief abstract about machine learning..."
    )
    
    score, has_full_pdf, doc_id = calculate_doc_quality("test_chat", doc_stub)
    assert doc_id == 1
    assert score > 0
    assert not has_full_pdf

def test_network_failure_fallback_graceful(monkeypatch):
    """Verify external journal API timeouts/errors are gracefully caught without crashing."""
    import requests
    from rag.search import search_academic_papers_planned
    
    def mock_get_fail(*args, **kwargs):
        raise requests.exceptions.ConnectTimeout("Mocked network timeout")
        
    monkeypatch.setattr(requests, "get", mock_get_fail)
    
    plan = {
        "en_query": "machine learning",
        "id_query": "machine learning",
        "target_count": 5,
        "language_preference": "en"
    }
    
def test_doi_cleaning_and_pdf_validation():
    """Verify clean_doi standardizes strings and is_authentic_pdf_bytes filters synthetic PDFs."""
    from helpers import clean_doi, is_authentic_pdf_bytes

    assert clean_doi("https://doi.org/10.1016/j.csi.2020.103429") == "10.1016/j.csi.2020.103429"
    assert clean_doi("**10.1109/ACCESS.2023.12345**.") == "10.1109/ACCESS.2023.12345"
    assert clean_doi("doi: 10.1000/182 ") == "10.1000/182"
    assert clean_doi(None) == ""

    # Check authentic PDF bytes
    fake_header = b"not a pdf at all"
    assert not is_authentic_pdf_bytes(fake_header)
    
    synthetic_pdf = b"%PDF-1.4 " + b"x" * 40000 + b" NOTBOOKLM SCHOLARLY ARCHIVE "
    assert not is_authentic_pdf_bytes(synthetic_pdf)
    
    authentic_pdf = b"%PDF-1.7 " + b"a" * 40000
    assert is_authentic_pdf_bytes(authentic_pdf)

def test_select_llm_validation():
    """Verify select_llm endpoint rejects disallowed providers and malformed model names."""
    res_invalid_provider = client.post("/llm/select", json={"provider": "malicious_provider"})
    assert res_invalid_provider.status_code == 400
    assert "Invalid provider" in res_invalid_provider.json()["detail"]

    res_invalid_chars = client.post("/llm/select", json={"provider": "9router", "model_name": "model; rm -rf /"})
    assert res_invalid_chars.status_code == 400
    assert "Invalid characters" in res_invalid_chars.json()["detail"]

def test_storage_path_traversal_protection():
    """Verify storage download and delete prevent directory traversal attempts."""
    res_del_traversal = client.post("/storage/delete", json={"file_ids": ["../../etc/passwd", "../../../test.txt"]})
    assert res_del_traversal.status_code == 200
    assert res_del_traversal.json()["failed"] == 2

    res_dl_traversal = client.post("/storage/download", json={"file_ids": ["../../secret.txt"]})
    assert res_dl_traversal.status_code in (400, 404)



