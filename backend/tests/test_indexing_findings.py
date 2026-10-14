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


def test_missing_current_source_list_does_not_claim_scopus(monkeypatch, tmp_path):
    monkeypatch.setattr(journal_indexer, "SCOPUS_DB_PATH", str(tmp_path / "missing.db"))
    monkeypatch.setattr(
        journal_indexer,
        "lookup_sinta_status",
        lambda _: {"status": "unknown", "record": None},
    )

    result = journal_indexer.lookup_journal_index(
        issn_list=["1234-5678"],
        journal_title="Journal with unavailable source data",
    )

    assert result["scopus_status"] == "unknown"
    assert result["indexing_type"] == "Peer-Reviewed"
    assert "Scopus" not in result["journal_metric"]


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
    assert journal_indexer.lookup_sinta_status("12345678")["status"] == "unlisted"
    assert len(requests) == 1
    assert journal_indexer.SINTA_NEGATIVE_CACHE_TTL == timedelta(minutes=5)


def test_sinta_listed_without_tier_status_survives_cache_hit(monkeypatch):
    cache = {}
    requests = []
    response = SimpleNamespace(status_code=200, text="matching listed row without accreditation tier")
    monkeypatch.setattr(journal_indexer, "_read_sinta_cache", lambda issn: cache.get(issn))
    monkeypatch.setattr(
        journal_indexer,
        "_write_sinta_cache",
        lambda issn, entry: cache.__setitem__(issn, entry.copy()),
    )
    monkeypatch.setattr(journal_indexer, "_get_sinta_response", lambda _url: requests.append(1) or response)
    monkeypatch.setattr(
        journal_indexer,
        "_parse_sinta_result",
        lambda *_args: {
            "row_found": True,
            "tier": None,
            "is_scopus": False,
            "journal_name": "Listed Journal",
        },
    )

    live = journal_indexer.lookup_sinta_status("12345678")
    cached = journal_indexer.lookup_sinta_status("12345678")

    assert live["status"] == "listed_without_tier"
    assert cached["status"] == "listed_without_tier"
    assert cached["record"]["row_found"] is True
    assert len(requests) == 1


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
    assert journal_indexer.lookup_sinta_status("12345678")["status"] == "unknown"
    assert len(requests) == 3
    assert writes == []


def _mock_index_status(monkeypatch, status, metric=None, sinta_status="unlisted"):
    source = {
        "status": status,
        "source_snapshot": "2026-09",
        "last_coverage_year": "2025" if status == "discontinued" else None,
    }
    monkeypatch.setattr(journal_indexer, "lookup_scopus_source", lambda *_args, **_kwargs: source)
    monkeypatch.setattr(journal_indexer, "lookup_scopus_db", lambda _: metric)
    monkeypatch.setattr(journal_indexer, "_read_sinta_cache", lambda _: None)
    monkeypatch.setattr(
        journal_indexer,
        "lookup_sinta_status",
        lambda _: {"status": sinta_status, "record": {"tier": "S2 Accredited"} if sinta_status == "accredited" else None},
    )


def test_active_scopus_status_can_exist_without_an_sjr_metric(monkeypatch):
    _mock_index_status(monkeypatch, "active", metric=None)

    result = journal_indexer.lookup_journal_index(
        issn_list=["1000-0001"],
        journal_title="Active Journal",
    )

    assert result["scopus_status"] == "active"
    assert result["indexing_type"] == "Scopus"
    assert result["journal_metric"] == "Scopus Indexed"
    assert result["quartile"] is None


def test_discontinued_scopus_source_does_not_claim_current_indexing(monkeypatch):
    _mock_index_status(
        monkeypatch,
        "discontinued",
        metric={"quartile": "Q3", "sjr": 0.33, "metric_year": "2024"},
    )

    result = journal_indexer.lookup_journal_index(
        issn_list=["1000-0003"],
        journal_title="Discontinued Journal",
    )

    assert result["scopus_status"] == "discontinued"
    assert result["scopus_last_coverage_year"] == "2025"
    assert result["historical_sjr_quartile"] == "Q3"
    assert result["historical_sjr_year"] == "2024"
    assert result["quartile"] is None
    assert result["indexing_type"] == "Peer-Reviewed"
    assert result["journal_metric"] == "Not currently indexed in Scopus (discontinued)"


def test_active_status_is_not_inferred_from_old_coverage(monkeypatch):
    source = {
        "status": "active",
        "source_snapshot": "2026-09",
        "coverage": "2001-2012",
        "last_coverage_year": None,
    }
    monkeypatch.setattr(journal_indexer, "lookup_scopus_source", lambda *_args, **_kwargs: source)
    monkeypatch.setattr(
        journal_indexer,
        "lookup_scopus_db",
        lambda _: {"quartile": "Q2", "sjr": 0.44, "metric_year": "2024"},
    )
    monkeypatch.setattr(journal_indexer, "_read_sinta_cache", lambda _: None)

    result = journal_indexer.lookup_journal_index(
        issn_list=["1000-0001"],
        journal_title="Active Older Coverage Journal",
    )

    assert result["scopus_status"] == "active"
    assert result["indexing_type"] == "Scopus"
    assert "Scopus Indexed" in result["journal_metric"]
    assert "SJR Q2 (2024)" in result["journal_metric"]


def test_unlisted_scopus_source_only_claims_an_official_sinta_result(monkeypatch):
    _mock_index_status(monkeypatch, "unlisted", metric=None, sinta_status="accredited")

    result = journal_indexer.lookup_journal_index(
        issn_list=["1000-0005"],
        journal_title="SINTA Listed Journal",
    )

    assert result["scopus_status"] == "unlisted"
    assert result["sinta_status"] == "accredited"
    assert result["indexing_type"] == "SINTA"
    assert "Not indexed in Scopus" in result["journal_metric"]
    assert "SINTA S2" in result["journal_metric"]
    assert "Scopus Indexed" not in result["journal_metric"]


def test_unlisted_sinta_issn_does_not_receive_an_accreditation_claim(monkeypatch):
    _mock_index_status(monkeypatch, "unlisted", metric=None, sinta_status="unlisted")

    result = journal_indexer.lookup_journal_index(
        issn_list=["1000-0006"],
        journal_title="Unlisted Journal",
    )

    assert result["scopus_status"] == "unlisted"
    assert result["sinta_status"] == "unlisted"
    assert result["sinta_tier"] is None
    assert "SINTA" not in result["journal_metric"]
    assert "Not indexed in Scopus" in result["journal_metric"]


def test_metadata_resolver_does_not_restore_an_unverified_llm_index_claim(monkeypatch):
    from services.search import metadata_resolver_service as resolver

    for name in (
        "fetch_openalex_metadata_by_doi",
        "search_openalex_metadata_by_title",
        "fetch_crossref_metadata_by_doi",
        "fetch_semantic_scholar_metadata_by_doi",
    ):
        monkeypatch.setattr(resolver, name, lambda *_args, **_kwargs: None)
    monkeypatch.setattr(resolver, "scrape_doi_landing_page_metadata", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(
        resolver,
        "audit_paper_metadata_with_ai",
        lambda **_kwargs: {
            "title": "A paper",
            "journal": "Unlisted Journal",
            "abstract": "An authentic abstract for this paper.",
            "journal_metric": "Scopus Q1",
            "quality_tier": 1,
        },
    )
    monkeypatch.setattr(
        journal_indexer,
        "lookup_journal_index",
        lambda *_args, **_kwargs: {
            "journal_metric": "Not indexed in Scopus",
            "indexing_type": "Peer-Reviewed",
            "quality_tier": 4,
            "scopus_status": "unlisted",
            "sinta_status": "unlisted",
        },
    )

    result = resolver.resolve_paper_metadata_by_doi(
        doi="10.1234/unlisted",
        cache={},
    )

    assert result["journal_metric"] == "Not indexed in Scopus"
    assert result["scopus_status"] == "unlisted"


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
