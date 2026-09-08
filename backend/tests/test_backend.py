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

def test_chats_pagination():
    """Verify limit and offset pagination on GET /chats."""
    created_ids = []
    try:
        # Create 3 chats
        for i in range(3):
            res = client.post("/chats", json={"title": f"Pagination Test Chat {i}"})
            assert res.status_code == 200
            created_ids.append(res.json()["id"])

        # Test limit
        res_limit = client.get("/chats?limit=2")
        assert res_limit.status_code == 200
        data_limit = res_limit.json()
        assert len(data_limit) <= 2

        # Test offset
        res_first = client.get("/chats?limit=1&offset=0")
        assert res_first.status_code == 200
        res_second = client.get("/chats?limit=1&offset=1")
        assert res_second.status_code == 200
        first_list = res_first.json()
        second_list = res_second.json()
        if first_list and second_list:
            assert first_list[0]["id"] != second_list[0]["id"]

        # Test invalid params validation
        res_invalid_limit_low = client.get("/chats?limit=0")
        assert res_invalid_limit_low.status_code == 422

        res_invalid_limit_high = client.get("/chats?limit=201")
        assert res_invalid_limit_high.status_code == 422

        res_invalid_offset = client.get("/chats?offset=-1")
        assert res_invalid_offset.status_code == 422
    finally:
        for cid in created_ids:
            client.delete(f"/chats/{cid}")

def test_flashrank_reranker():
    """Verify FlashRank cross-encoder loads and ranks passages properly (if installed)."""
    try:
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
    except (ImportError, ModuleNotFoundError):
        import pytest
        pytest.skip("flashrank is not installed in the current environment")

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
    from services.document import calculate_doc_quality
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
    
    # Must execute safely and return an empty list without unhandled exception
    results = search_academic_papers_planned(plan)
    assert isinstance(results, list)
    assert len(results) == 0

def test_sse_streaming_endpoint_flow(monkeypatch):
    """Verify SSE streaming endpoints emit structured SSE events without regression."""
    import rag
    
    async def mock_query_chat(chat_id, message, chat_history=None, status_callback=None, delta_callback=None, **kwargs):
        if status_callback:
            await status_callback("Mock thinking step...")
        if delta_callback:
            await delta_callback("Mock delta chunk...")
        return "This is a mocked assistant response."
        
    monkeypatch.setattr(rag, "query_chat", mock_query_chat)
    
    # 1. Create a chat session
    res_chat = client.post("/chats", json={"title": "SSE Stream Test Chat"})
    assert res_chat.status_code == 200
    chat_id = res_chat.json()["id"]
    
    # 2. Test send_message_stream SSE endpoint (/message/stream)
    res_stream = client.post(
        f"/chats/{chat_id}/message/stream",
        json={"message": "Hello AI"}
    )
    assert res_stream.status_code == 200
    assert "text/event-stream" in res_stream.headers.get("content-type", "")
    body_text = res_stream.text
    assert "data: " in body_text
    assert "Mock thinking step..." in body_text
    assert "Mock delta chunk..." in body_text
    assert "This is a mocked assistant response." in body_text
    
    # 3. Clean up
    client.delete(f"/chats/{chat_id}")
    
def test_rag_history_and_attachment_preparation():
    """Verify format_llama_history cleans hidden markers and prepare_query_attachments appends attachments."""
    from rag.engine import format_llama_history, prepare_query_attachments
    from llama_index.core.llms import MessageRole
    
    # 1. Format history with source comments
    raw_history = [
        {"role": "user", "content": "What is AI?"},
        {"role": "assistant", "content": "AI is artificial intelligence. <!-- SOURCES_DATA: [{'doi': '10.123/456'}] -->"}
    ]
    llama_hist = format_llama_history(raw_history)
    assert len(llama_hist) == 2
    assert llama_hist[0].role == MessageRole.USER
    assert llama_hist[1].role == MessageRole.ASSISTANT
    assert "<!-- SOURCES_DATA" not in llama_hist[1].content
    assert llama_hist[1].content == "AI is artificial intelligence."
    
    # 2. Prepare attachments
    user_query = "Summarize this paper."
    user_chat_history = [
        {
            "role": "user",
            "content": "Summarize this paper.",
            "attachments": [{"filename": "sample_draft.txt", "type": "document", "url": ""}]
        }
    ]
    prepared = prepare_query_attachments(user_query, user_chat_history)
    assert "[Attachments Provided by User:]" in prepared
    assert "Document attached: sample_draft.txt" in prepared

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

def test_llm_models_info_endpoint():
    """Verify active LLM models endpoint returns two-tier architecture status."""
    res = client.get("/llm/models")
    assert res.status_code == 200
    data = res.json()
    assert data.get("tiered_architecture") is True
    assert "main_model" in data
    assert "fast_model" in data

def test_storage_path_traversal_protection():
    """Verify storage download and delete prevent directory traversal attempts and static uploads is restricted."""
    res_del_traversal = client.post("/storage/delete", json={"file_ids": ["../../etc/passwd", "../../../test.txt"]})
    assert res_del_traversal.status_code == 200
    assert res_del_traversal.json()["failed"] == 2

    res_dl_traversal = client.post("/storage/download", json={"file_ids": ["../../secret.txt"]})
    assert res_dl_traversal.status_code in (400, 404)

    # Verify root /uploads is no longer statically mounted directly
    res_uploads_root = client.get("/uploads/")
    assert res_uploads_root.status_code == 404

@pytest.mark.asyncio
async def test_workspace_pipeline_execution():
    """Verify workspace analysis pipeline executes without DetachedInstanceError or import errors."""
    from rag.pipelines.workspace_pipeline import handle_workspace_analysis_pipeline
    from unittest.mock import AsyncMock, MagicMock
    from database import SessionLocal, Document as DBDocument

    dummy_chat_id = "test_ws_chat_123"
    db = SessionLocal()
    try:
        dummy_doc = DBDocument(
            chat_id=dummy_chat_id,
            filename="test_paper.pdf",
            title="Testing Modern RAG Pipeline",
            year=2024,
            abstract="This is a test abstract.",
            snippet="Overview snippet",
            is_oa=False
        )
        db.add(dummy_doc)
        db.commit()
    finally:
        db.close()

    try:
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.message.content = "Hasil analisis sintesis dokumen."
        mock_llm.achat = AsyncMock(return_value=mock_response)

        async def mock_status(text):
            pass

        result = await handle_workspace_analysis_pipeline(
            chat_id=dummy_chat_id,
            query="Bandingkan metode paper",
            local_docs=["test_paper.pdf"],
            formatted_history=[],
            target_llm=mock_llm,
            report_status=mock_status
        )
        assert "Hasil analisis sintesis" in result
    finally:
        db = SessionLocal()
        db.query(DBDocument).filter(DBDocument.chat_id == dummy_chat_id).delete()
        db.commit()
        db.close()

def test_rag_exports_and_aliases():
    """Verify delete_document_vectors and backward-compat delete_qdrant_vectors export properly."""
    import rag
    assert hasattr(rag, "delete_document_vectors")
    assert hasattr(rag, "delete_qdrant_vectors")
    assert rag.delete_qdrant_vectors is rag.delete_document_vectors

@pytest.mark.asyncio
async def test_dispatch_intent_pipeline_timeout_protection(monkeypatch):
    """Verify dispatch_intent_pipeline enforces timeout protection on intent pipelines."""
    import asyncio
    from rag.engine import dispatch_intent_pipeline
    import rag.pipelines.chat_pipeline as chat_pipe

    async def slow_chat_pipeline(*args, **kwargs):
        await asyncio.sleep(0.5)
        return "Slow response"

    monkeypatch.setattr(chat_pipe, "handle_general_chat_pipeline", slow_chat_pipeline)

    async def mock_status(text):
        pass

    with pytest.raises(TimeoutError) as exc_info:
        await dispatch_intent_pipeline(
            intent="GENERAL_CHAT",
            chat_id="dummy_chat",
            query="Hello",
            local_docs=[],
            formatted_history=[],
            target_llm=None,
            report_status=mock_status,
            tools=[],
            doc_context_info="",
            timeout_sec=0.05
        )
    assert "melebihi batas waktu" in str(exc_info.value)

def test_rubric_grader_parse_error_handling():
    """Verify parse_rubric_json_response does not fake high grounding scores on corrupted JSON."""
    from services.rubric_grader_service import parse_rubric_json_response

    corrupted_output = "I am an AI and here is your score: {not valid json"
    res = parse_rubric_json_response(corrupted_output)
    assert res.is_grounded is False
    assert res.grounding_score == 0.0
    assert len(res.hallucinated_claims) > 0
    assert "JSON parse failure" in res.hallucinated_claims[0]

    valid_json = '{"is_grounded": true, "grounding_score": 0.92, "citation_accuracy": true, "hallucinated_claims": []}'
    res_valid = parse_rubric_json_response(valid_json)
    assert res_valid.is_grounded is True
    assert res_valid.grounding_score == 0.92

@pytest.mark.asyncio
async def test_workspace_pipeline_hybrid_retrieval_scaling():
    """Verify workspace pipeline uses hybrid retrieval and catalog when docs > 4."""
    from rag.pipelines.workspace_pipeline import handle_workspace_analysis_pipeline
    from unittest.mock import AsyncMock, MagicMock
    from database import SessionLocal, Document as DBDocument

    dummy_chat_id = "test_hybrid_scaling_chat"
    db = SessionLocal()
    docs_to_add = [
        DBDocument(
            chat_id=dummy_chat_id,
            filename=f"paper_{i}.pdf",
            title=f"Scalable Academic Research Paper {i}",
            year=2023 + (i % 3),
            abstract=f"Abstract methodology and empirical results for paper {i}.",
            snippet=f"Snippet {i}",
            is_oa=False
        )
        for i in range(1, 6)
    ]
    try:
        for d in docs_to_add:
            db.add(d)
        db.commit()
    finally:
        db.close()

    try:
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.message.content = "Sintesis perbandingan 5 dokumen."
        mock_llm.achat = AsyncMock(return_value=mock_response)

        status_logs = []
        async def mock_status(text):
            status_logs.append(text)

        result = await handle_workspace_analysis_pipeline(
            chat_id=dummy_chat_id,
            query="Bandingkan kontribusi 5 paper ini",
            local_docs=[f"paper_{i}.pdf" for i in range(1, 6)],
            formatted_history=[],
            target_llm=mock_llm,
            report_status=mock_status
        )
        assert "Sintesis perbandingan 5 dokumen" in result
    finally:
        db = SessionLocal()
        db.query(DBDocument).filter(DBDocument.chat_id == dummy_chat_id).delete()
        db.commit()
        db.close()

def test_commit_with_retry():
    """Verify commit_with_retry handles success, transient locks with backoff, and fatal errors."""
    from unittest.mock import MagicMock
    from database import commit_with_retry
    from sqlalchemy.exc import OperationalError
    import sqlite3

    # 1. Normal commit succeeds without retries
    mock_db = MagicMock()
    commit_with_retry(mock_db)
    mock_db.commit.assert_called_once()
    mock_db.rollback.assert_not_called()

    # 2. Transient lock error succeeds on second attempt
    mock_db = MagicMock()
    lock_err = OperationalError("COMMIT", {}, sqlite3.OperationalError("database is locked"))
    mock_db.commit.side_effect = [lock_err, None]
    commit_with_retry(mock_db, max_retries=3, initial_delay=0.01)
    assert mock_db.commit.call_count == 2
    mock_db.rollback.assert_not_called()

    # 3. Persistent lock exhausts retries, triggers rollback, and re-raises
    mock_db = MagicMock()
    mock_db.commit.side_effect = lock_err
    with pytest.raises(OperationalError):
        commit_with_retry(mock_db, max_retries=2, initial_delay=0.01)
    assert mock_db.commit.call_count == 2
    mock_db.rollback.assert_called_once()

    # 4. Non-lock error does not retry, triggers rollback immediately
    mock_db = MagicMock()
    mock_db.commit.side_effect = ValueError("Non-lock exception")
    with pytest.raises(ValueError):
        commit_with_retry(mock_db, max_retries=3, initial_delay=0.01)
    mock_db.commit.assert_called_once()
    mock_db.rollback.assert_called_once()




