from providers.academic.crossref import fetch_crossref
from providers.academic.openalex import fetch_openalex
from providers.academic.europe_pmc import fetch_europe_pmc
from providers.academic.pdf_racing_resolver import (
    resolve_and_fetch_authentic_pdf,
    resolve_arxiv_pdf,
    resolve_unpaywall_pdf,
    resolve_openalex_pdf,
    resolve_europe_pmc_pdf,
    resolve_semantic_scholar_pdf,
    resolve_landing_page_pdf,
)

__all__ = [
    "fetch_crossref",
    "fetch_openalex",
    "fetch_europe_pmc",
    "resolve_and_fetch_authentic_pdf",
    "resolve_arxiv_pdf",
    "resolve_unpaywall_pdf",
    "resolve_openalex_pdf",
    "resolve_europe_pmc_pdf",
    "resolve_semantic_scholar_pdf",
    "resolve_landing_page_pdf",
]
