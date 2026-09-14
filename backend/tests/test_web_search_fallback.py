import pytest
from unittest.mock import MagicMock, patch
from providers.academic.duckduckgo import (
    clean_web_title,
    extract_authors_from_snippet,
    extract_venue_from_url,
    unwrap_bing_redirect,
    fetch_duckduckgo_fallback,
)
from rag.search import search_academic_papers_planned


def test_clean_web_title_sanitization():
    """Verify various SERP title artifacts are cleanly stripped."""
    assert clean_web_title("[PDF] Attention Is All You Need - arXiv.org") == "Attention Is All You Need"
    assert clean_web_title("YOLOv4: Optimal Speed and Accuracy | ScienceDirect") == "YOLOv4: Optimal Speed and Accuracy"
    assert clean_web_title("BERT: Deep Bidirectional Transformers – ResearchGate") == "BERT: Deep Bidirectional Transformers"
    assert clean_web_title("[HTML] Quantum Computing Fault Tolerance - PubMed") == "Quantum Computing Fault Tolerance"
    assert clean_web_title("<b>Deep Residual Learning</b> for Image Recognition") == "Deep Residual Learning for Image Recognition"


def test_extract_authors_and_venue():
    """Verify authors and venue extraction from snippet and domain."""
    snippet_with_authors = "by Ashish Vaswani, Noam Shazeer and Niki Parmar - 2017 - Abstract: The dominant sequence..."
    authors = extract_authors_from_snippet(snippet_with_authors)
    assert len(authors) >= 2
    assert "Ashish Vaswani" in authors

    fallback_authors = extract_authors_from_snippet("General snippet with no author attribution.")
    assert fallback_authors == ["Web Scholar Source"]

    assert extract_venue_from_url("https://arxiv.org/abs/1706.03762") == "arXiv"
    assert extract_venue_from_url("https://www.sciencedirect.com/science/article/pii/123") == "ScienceDirect"
    assert extract_venue_from_url("https://ieeexplore.ieee.org/document/9123456") == "IEEE Xplore"
    assert extract_venue_from_url("https://custom-repo.org/paper.pdf") == "Custom-repo.org"


def test_unwrap_bing_redirect():
    """Verify Bing click redirect decoding."""
    # Test unencoded URL returns as-is
    direct_url = "https://arxiv.org/abs/1706.03762"
    assert unwrap_bing_redirect(direct_url) == direct_url

    # Test encoded u parameter
    # aHR0cHM6Ly9hcnhpdi5vcmcvYWJzLzE3MDYuMDM3NjI = https://arxiv.org/abs/1706.03762
    encoded = "https://www.bing.com/ck/a?!&&p=123&u=a1aHR0cHM6Ly9hcnhpdi5vcmcvYWJzLzE3MDYuMDM3NjI&ntb=1"
    assert unwrap_bing_redirect(encoded) == "https://arxiv.org/abs/1706.03762"


def test_fetch_duckduckgo_fallback_success():
    """Verify successful parsing and mapping of DDGS search results into PaperCandidate dicts."""
    mock_ddg_results = [
        {
            "title": "[PDF] Attention Is All You Need - arXiv.org",
            "href": "https://arxiv.org/abs/1706.03762",
            "body": "by Ashish Vaswani, Noam Shazeer - 2017 - We introduce the Transformer model. DOI: 10.48550/arXiv.1706.03762"
        },
        {
            "title": "Machine Learning in Medicine | ScienceDirect",
            "href": "https://www.sciencedirect.com/science/article/pii/S1234",
            "body": "Published in 2021. Comprehensive review of clinical machine learning applications."
        },
        {
            "title": "Cat Video Compilation - YouTube",
            "href": "https://www.youtube.com/watch?v=123456",
            "body": "Watch cute cats playing."
        }
    ]

    seen = set()

    with patch("duckduckgo_search.DDGS") as mock_ddgs_class:
        mock_instance = MagicMock()
        mock_instance.text.return_value = mock_ddg_results
        mock_instance.__enter__.return_value = mock_instance
        mock_ddgs_class.return_value = mock_instance

        results = fetch_duckduckgo_fallback(
            term="machine learning",
            target_count=5,
            min_year=None,
            open_access_only=False,
            is_valid_academic_title_fn=lambda t: len(t) > 5,
            is_candidate_duplicate_fn=lambda t, d: False,
            is_matching_topic_fn=lambda t, s: True,
            mark_candidate_seen_fn=lambda t, d: seen.add(t)
        )

        assert len(results) == 2  # YouTube result should be ignored
        paper1 = results[0]
        assert paper1["title"] == "Attention Is All You Need"
        assert paper1["doi"] == "10.48550/arXiv.1706.03762"
        assert paper1["year"] == "2017"
        assert paper1["venue"] == "arXiv"
        assert paper1["pdf_url"] == "https://arxiv.org/pdf/1706.03762.pdf"
        assert paper1["is_oa"] is True
        assert paper1["journal_metric"] == "Web Search Fallback"

        paper2 = results[1]
        assert paper2["title"] == "Machine Learning in Medicine"
        assert paper2["year"] == "2021"
        assert paper2["venue"] == "ScienceDirect"


def test_fetch_duckduckgo_fallback_open_access_filter():
    """Verify open_access_only filter excludes closed-access web results."""
    mock_results = [
        {
            "title": "Open Paper - arXiv",
            "href": "https://arxiv.org/abs/2101.00001",
            "body": "Open access study published in 2021."
        },
        {
            "title": "Closed Paywalled Paper - Publisher",
            "href": "https://paywalled-publisher.com/article/1",
            "body": "Subscription required to view full text."
        }
    ]

    with patch("duckduckgo_search.DDGS") as mock_ddgs:
        mock_inst = MagicMock()
        mock_inst.text.return_value = mock_results
        mock_inst.__enter__.return_value = mock_inst
        mock_ddgs.return_value = mock_inst

        oa_results = fetch_duckduckgo_fallback(
            term="test",
            target_count=5,
            min_year=None,
            open_access_only=True,
            is_valid_academic_title_fn=lambda t: True,
            is_candidate_duplicate_fn=lambda t, d: False,
            is_matching_topic_fn=lambda t, s: True,
            mark_candidate_seen_fn=lambda t, d: None
        )

        assert len(oa_results) == 1
        assert oa_results[0]["title"] == "Open Paper"


def test_fetch_duckduckgo_fallback_network_error_graceful():
    """Verify DuckDuckGo search exceptions are caught gracefully without crashing."""
    with patch("duckduckgo_search.DDGS") as mock_ddgs:
        mock_inst = MagicMock()
        mock_inst.text.side_effect = Exception("Mocked DDG rate limit or network error")
        mock_inst._get_url.side_effect = Exception("Mocked Bing fallback failure")
        mock_inst.__enter__.return_value = mock_inst
        mock_ddgs.return_value = mock_inst

        results = fetch_duckduckgo_fallback(
            term="failing query",
            target_count=5,
            min_year=None,
            open_access_only=False,
            is_valid_academic_title_fn=lambda t: True,
            is_candidate_duplicate_fn=lambda t, d: False,
            is_matching_topic_fn=lambda t, s: True,
            mark_candidate_seen_fn=lambda t, d: None
        )
        assert results == []


def test_search_academic_papers_planned_invokes_web_fallback(monkeypatch):
    """
    Verify search_academic_papers_planned calls fetch_duckduckgo_fallback
    when primary academic providers return fewer results than target_count.
    """
    # 1. Mock primary providers to return 0 results
    monkeypatch.setattr("rag.search.fetch_europe_pmc", lambda *args, **kwargs: [])
    monkeypatch.setattr("rag.search.fetch_openalex", lambda *args, **kwargs: [])
    monkeypatch.setattr("rag.search.fetch_crossref", lambda *args, **kwargs: [])

    # 2. Mock fetch_duckduckgo_fallback to return 2 fallback papers
    mock_fallback_papers = [
        {
            "title": "Fallback Paper 1",
            "year": "2024",
            "doi": "10.1234/fb1",
            "url": "https://example.com/fb1",
            "snippet": "Discovered via web search.",
            "authors": ["Web Author"],
            "venue": "Web Venue",
            "pdf_url": "",
            "is_oa": False,
            "journal_metric": "Web Search Fallback",
            "citations": 0
        },
        {
            "title": "Fallback Paper 2",
            "year": "2023",
            "doi": "10.1234/fb2",
            "url": "https://example.com/fb2",
            "snippet": "Another discovered paper.",
            "authors": ["Web Author 2"],
            "venue": "Web Venue",
            "pdf_url": "",
            "is_oa": False,
            "journal_metric": "Web Search Fallback",
            "citations": 0
        }
    ]
    fallback_called = []
    def mock_ddg_call(*args, **kwargs):
        fallback_called.append(kwargs.get("term"))
        return mock_fallback_papers

    monkeypatch.setattr("rag.search.fetch_duckduckgo_fallback", mock_ddg_call)

    plan = {
        "en_query": "rare niche topic",
        "id_query": "topik langka",
        "native_query": "rare niche topic",
        "target_count": 2,
        "language_preference": "en"
    }

    results = search_academic_papers_planned(plan)
    assert len(fallback_called) == 1
    assert len(results) == 2
    assert results[0]["title"] == "Fallback Paper 1"
    assert results[0]["journal_metric"] == "Web Search Fallback"


def test_search_academic_papers_planned_skips_fallback_when_quota_met(monkeypatch):
    """
    Verify fallback is NOT called when primary providers return enough papers.
    Ensures academic peer-reviewed sources are strictly prioritized.
    """
    primary_papers = [
        {
            "title": f"Academic Paper {i}",
            "year": "2023",
            "doi": f"10.1000/{i}",
            "url": f"https://doi.org/10.1000/{i}",
            "snippet": "Verified peer-reviewed study.",
            "authors": ["Author"],
            "venue": "Nature",
            "pdf_url": "",
            "is_oa": True,
            "journal_metric": "Q1 Scopus",
            "citations": 50
        }
        for i in range(5)
    ]
    monkeypatch.setattr("rag.search.fetch_europe_pmc", lambda *args, **kwargs: primary_papers)
    monkeypatch.setattr("rag.search.fetch_openalex", lambda *args, **kwargs: [])
    monkeypatch.setattr("rag.search.fetch_crossref", lambda *args, **kwargs: [])

    fallback_called = []
    monkeypatch.setattr("rag.search.fetch_duckduckgo_fallback", lambda *args, **kwargs: fallback_called.append(True))

    plan = {
        "en_query": "deep learning",
        "target_count": 5,
        "language_preference": "en"
    }

    results = search_academic_papers_planned(plan)
    assert len(results) == 5
    assert len(fallback_called) == 0  # Fallback was not triggered
    assert all(p["journal_metric"] == "Q1 Scopus" for p in results)
