import sys
from datetime import timedelta
from types import ModuleType, SimpleNamespace

import pytest

import journal_indexer
from services.search import scopus_compiler


@pytest.mark.parametrize(
    "journal_title",
    [
        "CVPR Conference Proceedings",
        "arXiv preprint cs.AI",
        "Journal of Conference Medicine",
    ],
)
def test_journal_title_does_not_determine_venue_type(journal_title):
    result = journal_indexer.lookup_journal_index(
        journal_title=journal_title,
        venue_type="journal",
    )

    assert result["indexing_type"] == "Peer-Reviewed"
    assert result["is_conference"] is False
    assert result["is_preprint"] is False


def test_crossref_proceedings_article_is_not_looked_up_as_a_journal(monkeypatch):
    monkeypatch.setattr(
        journal_indexer,
        "lookup_scopus_db",
        lambda _: pytest.fail("conference proceedings must not use the journal index"),
    )
    monkeypatch.setattr(
        journal_indexer,
        "lookup_sinta_live",
        lambda _: pytest.fail("conference proceedings must not use the SINTA journal lookup"),
    )

    result = journal_indexer.lookup_journal_index(
        issn_list=["0302-9743"],
        journal_title="Lecture Notes in Computer Science",
        venue_type="proceedings-article",
    )

    assert result["is_conference"] is True
    assert result["quartile"] is None
    assert result["indexing_type"] == "Conference Proceedings"


def test_doi_crossref_fallback_preserves_proceedings_type(monkeypatch):
    from services.search import metadata_resolver_service as resolver

    monkeypatch.setattr(
        resolver,
        "fetch_openalex_metadata_by_doi",
        lambda *_args, **_kwargs: {
            "title": "Conference paper",
            "authors": ["Author"],
            "journal": "Proceedings Journal",
            "src_type": "journal",
            "issns": ["0302-9743"],
        },
    )
    monkeypatch.setattr(
        resolver,
        "fetch_crossref_metadata_by_doi",
        lambda *_args, **_kwargs: {
            "title": "Conference paper",
            "journal": "Proceedings Journal",
            "src_type": "proceedings-article",
        },
    )
    monkeypatch.setattr(resolver, "fetch_semantic_scholar_metadata_by_doi", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(resolver, "scrape_doi_landing_page_metadata", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(
        resolver,
        "audit_paper_metadata_with_ai",
        lambda **_kwargs: {
            "journal_metric": "Conference Proceedings (Indexed)",
            "quality_tier": 4,
        },
    )
    received_types = []

    def fake_index(issns, journal, venue_type, publisher=""):
        received_types.append(venue_type)
        return {
            "journal_metric": "Conference Proceedings (Indexed)",
            "indexing_type": "Conference Proceedings",
            "quality_tier": 4,
            "is_conference": True,
            "is_preprint": False,
            "quartile": None,
        }

    monkeypatch.setattr(journal_indexer, "lookup_journal_index", fake_index)

    resolver.resolve_paper_metadata_by_doi(
        doi="10.1234/example",
        cache={},
    )

    assert received_types == ["proceedings-article"]


def test_missing_scopus_bundle_does_not_trigger_runtime_download(monkeypatch, tmp_path):
    monkeypatch.setattr(journal_indexer, "SCOPUS_DB_PATH", str(tmp_path / "missing.db"))
    monkeypatch.setattr(
        scopus_compiler,
        "build_scopus_index_db",
        lambda _: pytest.fail("runtime lookup must not download the Scopus index"),
    )

    assert journal_indexer.lookup_scopus_db("12345678") is None


def test_sinta_no_result_response_is_cached_as_a_short_lived_miss(monkeypatch):
    cache = {}
    requests = []
    response = SimpleNamespace(
        status_code=200,
        text="<html><body>No matching journal</body></html>",
    )
    monkeypatch.setattr(journal_indexer, "_read_sinta_cache", lambda issn: cache.get(issn))
    monkeypatch.setattr(
        journal_indexer,
        "_write_sinta_cache",
        lambda issn, entry: cache.__setitem__(issn, entry),
    )
    monkeypatch.setattr(
        journal_indexer.requests,
        "get",
        lambda *_args, **_kwargs: requests.append(1) or response,
    )

    assert journal_indexer.lookup_sinta_live("12345678") is None
    assert journal_indexer.lookup_sinta_live("12345678") is None
    assert len(requests) == 1
    assert journal_indexer.SINTA_NEGATIVE_CACHE_TTL == timedelta(minutes=5)


def test_sinta_http_error_is_not_cached(monkeypatch):
    requests = []
    response = SimpleNamespace(status_code=503, headers={})
    writes = []
    monkeypatch.setattr(journal_indexer, "_read_sinta_cache", lambda _: None)
    monkeypatch.setattr(
        journal_indexer,
        "_write_sinta_cache",
        lambda *args: writes.append(args),
    )
    monkeypatch.setattr(
        journal_indexer.requests,
        "get",
        lambda *_args, **_kwargs: requests.append(1) or response,
    )

    assert journal_indexer.lookup_sinta_live("12345678") is None
    assert journal_indexer.lookup_sinta_live("12345678") is None
    assert len(requests) == 2
    assert writes == []


def test_metadata_auditor_uses_supplied_venue_type_not_journal_title(monkeypatch):
    rag_package = ModuleType("rag")
    rag_package.__path__ = []
    llm_factory = ModuleType("rag.llm_factory")
    llm_factory.get_fast_llm = lambda: None
    llm_factory.get_main_llm = lambda: None
    llm_factory.get_fallback_llm = lambda: None
    monkeypatch.setitem(sys.modules, "rag", rag_package)
    monkeypatch.setitem(sys.modules, "rag.llm_factory", llm_factory)

    captured = {}

    def fake_lookup(**kwargs):
        captured.update(kwargs)
        return {"journal_metric": "Peer-Reviewed Journal", "quality_tier": 4}

    monkeypatch.setattr(journal_indexer, "lookup_journal_index", fake_lookup)

    from services.search.metadata_auditor import audit_paper_metadata_with_ai

    audit_paper_metadata_with_ai(
        paper_title="Paper title",
        raw_authors=[],
        raw_journal="arXiv preprint cs.AI",
        raw_year="2025",
        raw_doi="",
        raw_citations=0,
        raw_abstract_or_html="",
        venue_type="journal",
    )

    assert captured["venue_type"] == "journal"
