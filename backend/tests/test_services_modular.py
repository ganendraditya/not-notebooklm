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
    assert clean_doi("http://dx.doi.org/10.1145/3377325.3377500") == "10.1145/3377325.3377500"
    assert clean_doi("**doi:10.1109/TPAMI.2020.1234567**") == "10.1109/TPAMI.2020.1234567"
    assert normalize_title_str("Deep Learning for Health.pdf") == "deep learning for health"
    assert is_valid_academic_title("Table of Contents") is False
    assert is_valid_academic_title("Attention Is All You Need") is True

def test_source_signatures_db_direct():
    """Verify get_existing_notebook_sources_signatures queries database directly."""
    from rag.search import get_existing_notebook_sources_signatures
    db = SessionLocal()
    chat_id = "test_sig_chat_123"
    try:
        session = ChatSession(id=chat_id, title="Signature Test")
        db.add(session)
        doc1 = Document(
            chat_id=chat_id,
            filename="my_paper.pdf",
            title="A Comprehensive Survey on LLMs",
            doi="10.1016/survey.2024"
        )
        db.add(doc1)
        db.commit()

        sigs = get_existing_notebook_sources_signatures(chat_id)
        assert "10.1016/survey.2024" in sigs["dois"]
        assert "A Comprehensive Survey on LLMs" in sigs["titles"]
        assert "my_paper.pdf" in sigs["filenames"]
    finally:
        db.query(Document).filter(Document.chat_id == chat_id).delete()
        db.query(ChatSession).filter(ChatSession.id == chat_id).delete()
        db.commit()
        db.close()

def test_journal_indexer_classification():
    """Verify journal_indexer correctly classifies preprints, conference proceedings, and peer-reviewed journals."""
    from journal_indexer import lookup_journal_index, init_journal_db
    
    assert init_journal_db() == 0
    
    # Preprints
    res_preprint = lookup_journal_index(journal_title="arXiv preprint cs.AI", venue_type="preprint")
    assert res_preprint["is_preprint"] is True
    assert res_preprint["quality_tier"] == 0
    
    # Conferences
    res_conf = lookup_journal_index(journal_title="IEEE Conference on Computer Vision and Pattern Recognition", venue_type="conference")
    assert res_conf["is_conference"] is True
    assert res_conf["quality_tier"] == 4
    
    # General peer-reviewed journal
    res_journal = lookup_journal_index(journal_title="American Journal of Sociology", venue_type="journal")
    assert res_journal["is_preprint"] is False
    assert res_journal["is_conference"] is False

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
    assert enriched["title"].lower() in ("sample", "test research paper")
    assert bool(enriched["doi"])

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

def test_enhance_table_citations():
    """Verify that table cells under document-mapped columns or rows automatically receive granular citation tags."""
    table_raw = (
        "| Parameter | [1] Doc A | [2] Doc B |\n"
        "| :--- | :--- | :--- |\n"
        "| Metode | • Model BiLSTM • Dataset 1000 | • Model Naive Bayes • Dataset 2000 |\n"
        "| Limitasi | Tidak disebutkan secara eksplisit | • Hanya data teks umum |\n"
        "| Temuan | Akurasi 72.25% | Akurasi 82.54% |"
    )
    formatted = format_clean_response(table_raw)
    assert "BiLSTM [1]" in formatted
    assert "Dataset 1000 [1]" in formatted
    assert "Naive Bayes [2]" in formatted
    assert "Akurasi 72.25% [1]" in formatted
    assert "Akurasi 82.54% [2]" in formatted
    assert "Tidak disebutkan secara eksplisit [1]" not in formatted

def test_paper_service_prepare_and_document_response():
    """Verify prepare_paper_file_sync return signature and DocumentResponse model contracts."""
    import models
    from services.paper_service import prepare_paper_file_sync
    
    cand = models.PaperCandidate(
        title="Attention Is All You Need",
        year="2017",
        doi="10.48550/arXiv.1706.03762",
        snippet="The dominant sequence transduction models are based on complex recurrent or convolutional neural networks.",
        url="https://arxiv.org/abs/1706.03762",
        is_oa=True
    )
    res = prepare_paper_file_sync("test_chat_contract", cand)
    assert len(res) == 4
    doc_text, filename, c_doi, has_downloaded_pdf = res
    assert "Attention Is All You Need" in doc_text
    assert c_doi == "10.48550/arXiv.1706.03762"

    from database import get_utc_now
    doc_resp = models.DocumentResponse(
        id=999,
        filename=filename,
        title="Attention Is All You Need",
        created_at=get_utc_now(),
        index=1,
        has_full_pdf=has_downloaded_pdf,
        is_oa=True
    )
    assert doc_resp.title == "Attention Is All You Need"
    assert doc_resp.has_full_pdf in (True, False)
    assert doc_resp.is_oa is True

def test_delete_storage_file_and_records_resolves_prefix():
    """Verify delete_storage_file_and_records cleans disk file, DB record, and vector index without zombie leak."""
    from services.storage_service import delete_storage_file_and_records
    from utils.file_utils import UPLOAD_DIR
    import uuid

    db = SessionLocal()
    chat_id = f"test_chat_{uuid.uuid4().hex[:8]}"
    clean_name = "test_phase4_paper.pdf"
    disk_filename = f"{chat_id}_{clean_name}"
    disk_path = os.path.join(UPLOAD_DIR, disk_filename)

    try:
        # Create physical dummy file
        with open(disk_path, "w", encoding="utf-8") as f:
            f.write("Dummy PDF content for Phase 4 test")

        # Create DB document record
        doc = Document(
            chat_id=chat_id,
            filename=clean_name,
            title="Phase 4 Test Document"
        )
        db.add(doc)
        db.commit()

        # Ensure document exists before deletion
        assert db.query(Document).filter(Document.chat_id == chat_id, Document.filename == clean_name).first() is not None
        assert os.path.exists(disk_path)

        # Execute single source of truth storage deletion
        deleted = delete_storage_file_and_records(db, disk_path)
        db.commit()

        assert deleted is True
        # Verify physical file removed
        assert not os.path.exists(disk_path)
        # Verify DB record removed (no zombie leak!)
        assert db.query(Document).filter(Document.chat_id == chat_id, Document.filename == clean_name).first() is None
    finally:
        if os.path.exists(disk_path):
            os.remove(disk_path)
        db.query(Document).filter(Document.chat_id == chat_id).delete()
        db.commit()
        db.close()

def test_delete_multiple_documents_batch():
    """Verify batch deletion in delete_multiple_documents."""
    from services.storage_service import delete_multiple_documents
    import uuid

    db = SessionLocal()
    chat_id = f"test_bulk_{uuid.uuid4().hex[:8]}"
    try:
        d1 = Document(chat_id=chat_id, filename="bulk_doc_1.pdf", title="Bulk 1")
        d2 = Document(chat_id=chat_id, filename="bulk_doc_2.pdf", title="Bulk 2")
        db.add_all([d1, d2])
        db.commit()
        db.refresh(d1)
        db.refresh(d2)

        count = delete_multiple_documents(db, chat_id, [d1.id, d2.id])
        assert count == 2
        remaining = db.query(Document).filter(Document.chat_id == chat_id).count()
        assert remaining == 0
    finally:
        db.query(Document).filter(Document.chat_id == chat_id).delete()
        db.commit()
        db.close()

def test_storage_summary_consistency():
    """Verify storage summary single traversal computes matching totals."""
    from services.storage_service import get_unified_storage_summary
    from database import DB_PATH

    summary = get_unified_storage_summary(DB_PATH)
    assert "total_bytes" in summary
    assert "used_bytes" in summary
    assert "categories" in summary
    assert "category_counts" in summary
    assert summary["uploads_bytes"] == sum(summary["categories"].values())

def test_clean_chat_duplicates_normalizes_doi_formats():
    """Verify duplicate detection correctly equates different DOI URI schemes."""
    import asyncio
    from services.document.duplicate_service import clean_chat_duplicates
    import uuid

    db = SessionLocal()
    chat_id = f"test_dup_{uuid.uuid4().hex[:8]}"
    try:
        session = ChatSession(id=chat_id, title="Duplicate DOI Test")
        db.add(session)

        # First doc with full HTTPS URL and comprehensive abstract (>100 chars for higher quality score)
        d1 = Document(
            chat_id=chat_id,
            filename="doc_full_url.txt",
            title="Advancements in Quantum AI",
            doi="https://doi.org/10.1016/j.quant.2024.01",
            abstract="This comprehensive analysis explores the theoretical intersections of quantum computing algorithms and modern machine learning synergy."
        )
        # Second doc with bare DOI and different title casing
        d2 = Document(
            chat_id=chat_id,
            filename="doc_bare_doi.txt",
            title="Advancements In Quantum Ai",
            doi="10.1016/j.quant.2024.01",
            abstract="Short abstract"
        )
        db.add_all([d1, d2])
        db.commit()

        result = asyncio.run(clean_chat_duplicates(chat_id, db))
        assert result["status"] == "success"
        assert result["cleaned_count"] == 1
        assert result["remaining_count"] == 1

        remaining_docs = db.query(Document).filter(Document.chat_id == chat_id).all()
        assert len(remaining_docs) == 1
        assert remaining_docs[0].filename == "doc_full_url.txt"
    finally:
        db.query(Document).filter(Document.chat_id == chat_id).delete()
        db.query(ChatSession).filter(ChatSession.id == chat_id).delete()
        db.commit()
        db.close()


def test_delete_chat_physical_files_cleans_sources_and_media():
    """Verify delete_chat_physical_files removes files in both UPLOAD_DIR and CHAT_MEDIA_DIR."""
    import os
    import uuid
    from services.storage_service import delete_chat_physical_files
    from utils.file_utils import UPLOAD_DIR, CHAT_MEDIA_DIR

    test_cid = f"test_purge_{uuid.uuid4().hex}"
    source_file = os.path.join(UPLOAD_DIR, f"{test_cid}_paper.pdf")
    media_file = os.path.join(CHAT_MEDIA_DIR, f"{test_cid}_image.png")

    with open(source_file, "w") as f:
        f.write("dummy source content")
    with open(media_file, "w") as f:
        f.write("dummy media content")

    assert os.path.exists(source_file)
    assert os.path.exists(media_file)

    deleted_count = delete_chat_physical_files(test_cid)
    assert deleted_count == 2
    assert not os.path.exists(source_file)
    assert not os.path.exists(media_file)


def test_storage_adapter_configuration_and_fallback():
    """Verify storage adapter correctly detects S3 credentials and falls back gracefully when disabled."""
    import os
    from services.storage_adapter import is_s3_enabled, get_bucket_name, upload_file, delete_file

    # Save original env
    orig_type = os.environ.get("STORAGE_TYPE")
    try:
        os.environ["STORAGE_TYPE"] = "local"
        assert is_s3_enabled() is False

        # When local, upload/delete functions should gracefully return without crashing
        assert upload_file("/nonexistent/file.pdf", "file.pdf") is False
        assert delete_file("file.pdf") is False

        # Verify bucket name default
        os.environ["S3_BUCKET_NAME"] = "test-bucket"
        assert get_bucket_name() == "test-bucket"
    finally:
        if orig_type is not None:
            os.environ["STORAGE_TYPE"] = orig_type
        else:
            os.environ.pop("STORAGE_TYPE", None)





