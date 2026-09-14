import os
import sys
import json
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import app
import rag
from database import SessionLocal, ChatSession, Document
from rag.format_parsers import (
    extract_bibtex_entries,
    extract_ris_entries,
    parse_bibtex_text,
    parse_ris_text,
)

client = TestClient(app)

def _generate_mock_pdf_bytes() -> bytes:
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 72), "Attention Is All You Need\nAbstract: The dominant sequence transduction models are based on complex recurrent or convolutional neural networks.")
    data = doc.tobytes()
    doc.close()
    if len(data) < 1000:
        data = data + b" " * (1000 - len(data))
    return data

MOCK_ATTENTION_PDF_BYTES = _generate_mock_pdf_bytes()

def mock_resolve_and_fetch_authentic_pdf(doi="", title="", direct_url="", candidate_pdf_url=""):
    combined = f"{doi} {title} {direct_url} {candidate_pdf_url}".lower()
    if "arxiv" in combined or "attention" in combined:
        return MOCK_ATTENTION_PDF_BYTES
    return None

@pytest.fixture(autouse=True)
def mock_academic_pdf_resolver(monkeypatch):
    """Hermetic isolation: prevent live HTTP requests to Semantic Scholar / Crossref / Unpaywall during tests."""
    monkeypatch.setattr("services.document.upload_service.resolve_and_fetch_authentic_pdf", mock_resolve_and_fetch_authentic_pdf)
    monkeypatch.setattr("services.document.content_service.resolve_and_fetch_authentic_pdf", mock_resolve_and_fetch_authentic_pdf)
    monkeypatch.setattr("providers.academic.pdf_racing_resolver.resolve_and_fetch_authentic_pdf", mock_resolve_and_fetch_authentic_pdf)

SAMPLE_BIB_MULTI = """
@article{vaswani2017attention,
  author    = {Ashish Vaswani and Noam Shazeer and Niki Parmar},
  title     = {Attention Is All You Need},
  journal   = {Advances in Neural Information Processing Systems},
  year      = {2017},
  doi       = {10.48550/arXiv.1706.03762},
  abstract  = {The dominant sequence transduction models are based on complex recurrent or convolutional neural networks.}
}

@inproceedings{devlin2018bert,
  author    = {Jacob Devlin and Ming-Wei Chang and Kenton Lee},
  title     = {BERT: Pre-training of Deep Bidirectional Transformers for {Language} Understanding},
  booktitle = {NAACL-HLT 2019},
  year      = {2019},
  doi       = {10.18653/v1/N19-1423},
  abstract  = {We introduce a new language representation model called BERT.}
}

@article{he2016deep,
  author    = {Kaiming He and Xiangyu Zhang and Shaoqing Ren and Jian Sun},
  title     = {Deep Residual Learning for Image Recognition},
  journal   = {IEEE Conference on Computer Vision and Pattern Recognition},
  year      = {2016},
  doi       = {https://doi.org/10.1109/CVPR.2016.90},
  abstract  = {Deeper neural networks are more difficult to train.}
}
"""

SAMPLE_RIS_MULTI = """
TY  - JOUR
TI  - Attention Is All You Need
AU  - Vaswani, Ashish
AU  - Shazeer, Noam
PY  - 2017/12/04/
JO  - NeurIPS
DO  - 10.48550/arXiv.1706.03762
AB  - Transformer sequence transduction model.
ER  - 

TY  - CONF
TI  - BERT: Language Understanding
AU  - Devlin, Jacob
AU  - Chang, Ming-Wei
PY  - 2019
JO  - NAACL-HLT
DO  - 10.18653/v1/N19-1423
AB  - Deep bidirectional language representations.
ER  - 
"""

def test_extract_bibtex_entries_unit():
    """Verify BibTeX extractor parses entries, authors, years, DOIs, and titles accurately."""
    entries = extract_bibtex_entries(SAMPLE_BIB_MULTI)
    assert len(entries) == 3

    e1 = entries[0]
    assert e1["key"] == "vaswani2017attention"
    assert e1["title"] == "Attention Is All You Need"
    assert e1["year"] == "2017"
    assert len(e1["authors"]) == 3
    assert "Ashish Vaswani" in e1["authors"]
    assert e1["doi"] == "10.48550/arXiv.1706.03762"
    assert "dominant sequence transduction" in e1["abstract"]

    e2 = entries[1]
    # Braces around Language should be stripped
    assert e2["title"] == "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding"
    assert e2["year"] == "2019"
    assert e2["doi"] == "10.18653/v1/N19-1423"

    e3 = entries[2]
    assert e3["doi"] == "10.1109/CVPR.2016.90"  # Stripped https://doi.org/
    assert len(e3["authors"]) == 4

def test_extract_ris_entries_unit():
    """Verify RIS extractor parses multiline entries, authors, years, and clean DOIs."""
    entries = extract_ris_entries(SAMPLE_RIS_MULTI)
    assert len(entries) == 2

    r1 = entries[0]
    assert r1["title"] == "Attention Is All You Need"
    assert r1["year"] == "2017"
    assert r1["doi"] == "10.48550/arXiv.1706.03762"
    assert len(r1["authors"]) == 2
    assert "Ashish Vaswani" in r1["authors"]

    r2 = entries[1]
    assert r2["title"] == "BERT: Language Understanding"
    assert r2["year"] == "2019"
    assert r2["doi"] == "10.18653/v1/N19-1423"

def test_parse_bibtex_and_ris_markdown():
    """Verify format parsers generate clean Markdown summaries."""
    md_bib = parse_bibtex_text(SAMPLE_BIB_MULTI)
    assert "### Attention Is All You Need" in md_bib
    assert "- **Authors**: Ashish Vaswani" in md_bib
    assert "- **Year**: 2017" in md_bib
    assert "### BERT" in md_bib

    md_ris = parse_ris_text(SAMPLE_RIS_MULTI)
    assert "### Attention Is All You Need" in md_ris
    assert "### BERT: Language Understanding" in md_ris

def test_upload_bibtex_multi_entry_splits_documents(monkeypatch):
    """Upload a multi-entry .bib file and verify individual documents are created in DB."""
    monkeypatch.setattr(rag, "ingest_document", lambda *args, **kwargs: None)
    # 1. Create a test chat
    res_chat = client.post("/chats", json={"title": "BibTeX Multi-Entry Ingest Test"})
    assert res_chat.status_code == 200
    chat_id = res_chat.json()["id"]

    try:
        # 2. Upload multi-entry .bib
        files = {
            "file": ("collection.bib", SAMPLE_BIB_MULTI.encode("utf-8"), "application/x-bibtex")
        }
        res_upload = client.post(f"/chats/{chat_id}/upload", files=files)
        assert res_upload.status_code == 200
        docs_data = res_upload.json()

        # Should return a list of 3 documents!
        assert isinstance(docs_data, list)
        assert len(docs_data) == 3

        titles = [d["title"] for d in docs_data]
        assert "Attention Is All You Need" in titles
        assert any("BERT" in t for t in titles)
        assert any("Residual" in t for t in titles)

        # 3. Check documents from chat endpoint
        res_get_chat = client.get(f"/chats/{chat_id}")
        assert res_get_chat.status_code == 200
        chat_docs = res_get_chat.json()["documents"]
        assert len(chat_docs) == 3

        # 4. Check document content endpoint for first doc
        doc_id = docs_data[0]["id"]
        res_content = client.get(f"/chats/{chat_id}/documents/{doc_id}/content")
        assert res_content.status_code == 200
        content_data = res_content.json()
        assert "Attention Is All You Need" in content_data["title"]
        assert len(content_data["authors"]) > 0
        assert content_data["doi"] == "10.48550/arXiv.1706.03762"
        # Attention Is All You Need is Open Access on arXiv, so authentic PDF is resolved!
        assert content_data["is_oa"] is True
        assert content_data["has_full_pdf"] is True

        # Check doc 3 (ResNet - IEEE paywalled), which remains registered with full abstract
        doc3_id = docs_data[2]["id"]
        res_c3 = client.get(f"/chats/{chat_id}/documents/{doc3_id}/content")
        assert res_c3.status_code == 200
        c3_data = res_c3.json()
        assert "Deep Residual Learning" in c3_data["title"]
        assert "Deeper neural networks are more difficult to train" in c3_data["content"]
        assert c3_data["doi"] == "10.1109/CVPR.2016.90"

        # 5. Delete one document and verify remaining 2 documents persist cleanly
        res_del = client.delete(f"/chats/{chat_id}/documents/{doc_id}")
        assert res_del.status_code == 200

        res_after_del = client.get(f"/chats/{chat_id}")
        assert len(res_after_del.json()["documents"]) == 2

    finally:
        client.delete(f"/chats/{chat_id}")

def test_upload_ris_multi_entry_splits_documents(monkeypatch):
    """Upload a multi-entry .ris file and verify individual documents are created in DB."""
    monkeypatch.setattr(rag, "ingest_document", lambda *args, **kwargs: None)
    res_chat = client.post("/chats", json={"title": "RIS Multi-Entry Ingest Test"})
    assert res_chat.status_code == 200
    chat_id = res_chat.json()["id"]

    try:
        files = {
            "file": ("papers.ris", SAMPLE_RIS_MULTI.encode("utf-8"), "application/x-research-info-systems")
        }
        res_upload = client.post(f"/chats/{chat_id}/upload", files=files)
        assert res_upload.status_code == 200
        docs_data = res_upload.json()

        assert isinstance(docs_data, list)
        assert len(docs_data) == 2

        titles = [d["title"] for d in docs_data]
        assert "Attention Is All You Need" in titles
        assert "BERT: Language Understanding" in titles

        # Check content of the second document
        doc2_id = docs_data[1]["id"]
        res_content = client.get(f"/chats/{chat_id}/documents/{doc2_id}/content")
        assert res_content.status_code == 200
        c_data = res_content.json()
        assert c_data["year"] == "2019"
        assert c_data["doi"] == "10.18653/v1/N19-1423"
        assert "Deep bidirectional language representations" in c_data["content"] or "BERT" in c_data["content"]

    finally:
        client.delete(f"/chats/{chat_id}")

def test_upload_bibtex_single_entry(monkeypatch):
    """Verify single-entry BibTeX uploads cleanly as 1 document."""
    monkeypatch.setattr(rag, "ingest_document", lambda *args, **kwargs: None)
    res_chat = client.post("/chats", json={"title": "Single Bib Test"})
    assert res_chat.status_code == 200
    chat_id = res_chat.json()["id"]

    try:
        single_bib = """
@article{vaswani2017attention,
  author    = {Ashish Vaswani},
  title     = {Attention Is All You Need},
  year      = {2017},
  doi       = {10.48550/arXiv.1706.03762}
}
"""
        files = {"file": ("single.bib", single_bib.encode("utf-8"), "application/x-bibtex")}
        res_upload = client.post(f"/chats/{chat_id}/upload", files=files)
        assert res_upload.status_code == 200
        data = res_upload.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["title"] == "Attention Is All You Need"
    finally:
        client.delete(f"/chats/{chat_id}")

def test_upload_malformed_bibtex_fallback(monkeypatch):
    """Verify malformed/empty BibTeX falls back gracefully to standard single document upload."""
    monkeypatch.setattr(rag, "ingest_document", lambda *args, **kwargs: None)
    res_chat = client.post("/chats", json={"title": "Malformed Bib Test"})
    assert res_chat.status_code == 200
    chat_id = res_chat.json()["id"]

    try:
        bad_bib = "This is not a valid BibTeX file at all."
        files = {"file": ("corrupt.bib", bad_bib.encode("utf-8"), "application/x-bibtex")}
        res_upload = client.post(f"/chats/{chat_id}/upload", files=files)
        assert res_upload.status_code == 200
        data = res_upload.json()
        # Fallback creates single DocumentResponse object
        assert isinstance(data, dict)
        assert "id" in data
    finally:
        client.delete(f"/chats/{chat_id}")
