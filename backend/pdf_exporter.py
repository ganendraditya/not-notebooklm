"""
PDF Exporter and Open-Access Resolver Module.
Provides authentic PDF resolution and validation for academic literature.
"""

from utils.pdf_utils import is_authentic_pdf_bytes, is_binary_pdf
from providers.academic.pdf_racing_resolver import (
    resolve_and_fetch_authentic_pdf,
    try_fetch_open_access_pdf,
)

__all__ = [
    "is_authentic_pdf_bytes",
    "is_binary_pdf",
    "resolve_and_fetch_authentic_pdf",
    "try_fetch_open_access_pdf",
]
