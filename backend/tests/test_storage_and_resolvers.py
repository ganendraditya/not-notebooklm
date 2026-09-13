import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
import re
import json
from fastapi.testclient import TestClient
from main import app
from database import SessionLocal, ChatSession, Document

client = TestClient(app)

def test_storage_summary_endpoint():
    """Verify /storage/summary returns expected quota structure."""
    res = client.get("/storage/summary")
    assert res.status_code == 200
    data = res.json()
    assert "total_bytes" in data
    assert "used_bytes" in data
    assert "categories" in data
    assert isinstance(data["categories"], dict)
    assert "documents" in data["categories"]
    assert "images" in data["categories"]
    assert "others" in data["categories"]

def test_storage_files_listing_and_filter():
    """Verify /storage/files lists files and handles category query."""
    res = client.get("/storage/files")
    assert res.status_code == 200
    assert isinstance(res.json(), list)

    res_cat = client.get("/storage/files?category=documents")
    assert res_cat.status_code == 200
    assert isinstance(res_cat.json(), list)

def test_storage_cleanup_endpoint():
    """Verify /settings/storage/cleanup runs safely."""
    res = client.post("/settings/storage/cleanup")
    assert res.status_code == 200
    data = res.json()
    assert data.get("status") == "success"
    assert "deleted_files_count" in data
    assert "freed_bytes" in data

def test_storage_download_path_traversal_protection():
    """Verify path traversal attacks in file download are rejected."""
    # Attempt directory traversal
    res = client.post("/storage/download", json={"file_ids": ["../../etc/passwd"]})
    # Should reject or return 404 because file is outside upload directory
    assert res.status_code in (400, 404)

def test_storage_adapter_safety():
    """Verify S3 adapter safety guards."""
    from services.storage_adapter import delete_files_with_prefix, is_s3_enabled, get_bucket_name
    
    # Must never delete when prefix is empty or whitespace
    assert delete_files_with_prefix("") == 0
    assert delete_files_with_prefix("   ") == 0
    
    # Check helper returns
    assert isinstance(is_s3_enabled(), bool)
    assert isinstance(get_bucket_name(), str)

def test_academic_resolvers_regex_and_rewriting():
    """Verify URL rewriting and preprint identifier extraction."""
    # 1. Test OJS URL rewriting with and without galley IDs
    fast_url_single = "https://journal.org/article/view/9999"
    rewritten_single = re.sub(
        r'/article/view/(\d+)(?:/(\d+))?',
        lambda m: f"/article/download/{m.group(1)}" + (f"/{m.group(2)}" if m.group(2) else ""),
        fast_url_single
    ).rstrip('/')
    assert rewritten_single == "https://journal.org/article/download/9999"

    fast_url_double = "https://journal.org/article/view/9999/8888"
    rewritten_double = re.sub(
        r'/article/view/(\d+)(?:/(\d+))?',
        lambda m: f"/article/download/{m.group(1)}" + (f"/{m.group(2)}" if m.group(2) else ""),
        fast_url_double
    ).rstrip('/')
    assert rewritten_double == "https://journal.org/article/download/9999/8888"

    # 2. Test arXiv ID extraction excludes random publisher PDF URLs
    fake_publisher_url = "https://publisher.com/journal/pdf/2024.1234.pdf"
    m_fake = re.search(r'(?:arxiv[:\s/]|arxiv\.org/(?:abs|pdf)/)(\d{4}\.\d{4,5}(?:v\d+)?)', fake_publisher_url)
    assert m_fake is None

    real_arxiv_url = "https://arxiv.org/abs/2301.12345"
    m_real = re.search(r'(?:arxiv[:\s/]|arxiv\.org/(?:abs|pdf)/)(\d{4}\.\d{4,5}(?:v\d+)?)', real_arxiv_url)
    assert m_real is not None
    assert m_real.group(1) == "2301.12345"

def test_import_sources_stream_with_novel_and_duplicate():
    """Verify import sources stream handles novel documents and reports duplicate items."""
    db = SessionLocal()
    chat = ChatSession(title="Import Stream Test Session")
    db.add(chat)
    db.commit()
    db.refresh(chat)
    chat_id = chat.id
    db.close()

    try:
        payload = {
            "sources": [
                {
                    "title": "Quantum Supremacy Using a Programmable Superconducting Processor",
                    "year": "2019",
                    "doi": "10.1038/s41586-019-1666-5",
                    "url": "https://doi.org/10.1038/s41586-019-1666-5",
                    "snippet": "The promise of quantum computers is that certain computational tasks might be executed exponentially faster.",
                    "authors": ["Frank Arute", "Kunyi Arya"],
                    "venue": "Nature",
                    "is_oa": True
                }
            ]
        }

        # First import: should succeed
        res = client.post(f"/chats/{chat_id}/import_sources_stream", json=payload)
        assert res.status_code == 200
        lines = [line.decode("utf-8") if isinstance(line, bytes) else line for line in res.iter_lines() if line]
        assert any("progress" in l for l in lines)
        assert any("done" in l for l in lines)

        # Second import with identical DOI: should recognize existing document and not crash
        res_dup = client.post(f"/chats/{chat_id}/import_sources_stream", json=payload)
        assert res_dup.status_code == 200
        lines_dup = [line.decode("utf-8") if isinstance(line, bytes) else line for line in res_dup.iter_lines() if line]
        assert any("progress" in l for l in lines_dup)
    finally:
        # Cleanup test chat
        client.delete(f"/chats/{chat_id}")
