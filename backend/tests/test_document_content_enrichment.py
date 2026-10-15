import asyncio
import os
import sys
import threading

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database import Base, ChatSession, Document
from services.document import content_service, metadata_extractor
from services.source_rename_service import persist_chat_source_rename
from utils import metadata_extractor as heuristic_metadata_extractor
import rag.parsers


def _make_database(tmp_path, title):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'content-enrichment.db'}",
        connect_args={"check_same_thread": False, "timeout": 5},
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragmas(connection, _record):
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=NORMAL")
        connection.execute("PRAGMA busy_timeout=5000")

    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    with session_factory.begin() as db:
        db.add(ChatSession(id="content-race-chat", title="Content race"))
        db.add(
            Document(
                id=950,
                chat_id="content-race-chat",
                filename="paper.pdf",
                title=title,
                authors=None,
                doi=None,
            )
        )
    return engine, session_factory


@pytest.mark.asyncio
async def test_metadata_enrichment_does_not_overwrite_concurrent_rename(tmp_path, monkeypatch):
    engine, session_factory = _make_database(tmp_path, "paper")

    file_path = tmp_path / "paper.pdf"
    file_path.write_text("Fixture document content", encoding="utf-8")
    extraction_started = asyncio.Event()
    continue_extraction = asyncio.Event()

    async def blocked_metadata_extraction(_path, _filename):
        extraction_started.set()
        await continue_extraction.wait()
        return {
            "title": "Registry title",
            "authors": ["Registry Author"],
            "year": "2024",
            "journal": "Registry Journal",
        }

    async def no_pdf_fetch(_doc, _path):
        return False, ""

    monkeypatch.setattr(
        metadata_extractor,
        "extract_hybrid_document_metadata",
        blocked_metadata_extraction,
    )
    monkeypatch.setattr(
        content_service,
        "get_doc_file_path",
        lambda _chat_id, _filename: str(file_path),
    )
    monkeypatch.setattr(content_service, "check_and_fetch_authentic_pdf_on_demand", no_pdf_fetch)

    reader_session = session_factory()
    document = (
        reader_session.query(Document)
        .filter(Document.id == 950, Document.chat_id == "content-race-chat")
        .one()
    )
    content_task = asyncio.create_task(
        content_service.get_document_full_content("content-race-chat", document, reader_session)
    )

    try:
        await asyncio.wait_for(extraction_started.wait(), timeout=5)
        rename_session = session_factory()
        try:
            rename = persist_chat_source_rename(
                rename_session,
                chat_id="content-race-chat",
                doc_id=950,
                source_number=1,
                expected_title="paper",
                previous_title="paper",
                new_title="User exact title",
                success_response="Renamed",
                conflict_response="Conflict",
                unchanged_response="Unchanged",
            )
            assert rename.event is not None
        finally:
            rename_session.close()
    finally:
        continue_extraction.set()

    try:
        content = await content_task
    finally:
        reader_session.close()

    verification_session = session_factory()
    try:
        saved_title = (
            verification_session.query(Document.title)
            .filter(Document.id == 950, Document.chat_id == "content-race-chat")
            .scalar()
        )
        assert content["title"] == "User exact title"
        assert saved_title == "User exact title"
        saved_document = (
            verification_session.query(Document)
            .filter(Document.id == 950, Document.chat_id == "content-race-chat")
            .one()
        )
        assert saved_document.authors == '["Registry Author"]'
        assert saved_document.year == "2024"
    finally:
        verification_session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.mark.asyncio
async def test_metadata_lookup_does_not_overwrite_rename_for_blank_title(tmp_path, monkeypatch):
    engine, session_factory = _make_database(tmp_path, None)
    file_path = tmp_path / "paper.pdf"
    file_path.write_text("Fixture document content", encoding="utf-8")
    loop = asyncio.get_running_loop()
    lookup_started = asyncio.Event()
    continue_lookup = threading.Event()

    def blocked_metadata_lookup(*_args, **_kwargs):
        loop.call_soon_threadsafe(lookup_started.set)
        if not continue_lookup.wait(timeout=5):
            raise TimeoutError("Metadata lookup was not released by the test.")
        return {
            "title": "Registry title",
            "authors": ["Registry Author"],
            "publication_date": "2024",
            "year": "2024",
            "journal": "Registry Journal",
            "journal_metric": "Peer-Reviewed",
            "quality_tier": 2,
            "citations": 5,
            "doi": "10.1234/example",
            "url": "https://doi.org/10.1234/example",
            "pdf_url": "",
            "abstract": "A registry abstract with enough detail to store as metadata.",
            "abstract_type": "official",
        }

    monkeypatch.setattr(
        content_service,
        "get_doc_file_path",
        lambda _chat_id, _filename: str(file_path),
    )
    monkeypatch.setattr(
        rag.parsers,
        "parse_document_to_markdown",
        lambda _path: "Fixture content",
    )
    monkeypatch.setattr(
        heuristic_metadata_extractor,
        "extract_heuristic_metadata",
        lambda _content, _filename: {
            "title": "Parsed title",
            "year": "",
            "doi": "10.1234/example",
            "url": "https://doi.org/10.1234/example",
            "abstract": "",
            "clean_filename_title": "paper",
        },
    )
    monkeypatch.setattr(content_service.rag, "resolve_paper_metadata_by_doi", blocked_metadata_lookup)

    reader_session = session_factory()
    document = (
        reader_session.query(Document)
        .filter(Document.id == 950, Document.chat_id == "content-race-chat")
        .one()
    )
    content_task = asyncio.create_task(
        content_service.get_document_full_content("content-race-chat", document, reader_session)
    )

    try:
        await asyncio.wait_for(lookup_started.wait(), timeout=5)
        rename_session = session_factory()
        try:
            rename = persist_chat_source_rename(
                rename_session,
                chat_id="content-race-chat",
                doc_id=950,
                source_number=1,
                expected_title=None,
                previous_title="paper",
                new_title="User exact title",
                success_response="Renamed",
                conflict_response="Conflict",
                unchanged_response="Unchanged",
            )
            assert rename.event is not None
        finally:
            rename_session.close()
    finally:
        continue_lookup.set()

    try:
        content = await content_task
    finally:
        reader_session.close()

    verification_session = session_factory()
    try:
        saved_document = (
            verification_session.query(Document)
            .filter(Document.id == 950, Document.chat_id == "content-race-chat")
            .one()
        )
        assert content["title"] == "User exact title"
        assert saved_document.title == "User exact title"
        assert saved_document.authors == '["Registry Author"]'
        assert saved_document.year == "2024"
    finally:
        verification_session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()
