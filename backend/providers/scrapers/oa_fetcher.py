import os
import re
import logging
from typing import Optional
import requests
from utils.pdf_utils import is_authentic_pdf_bytes

logger = logging.getLogger("uvicorn.error")

def try_fetch_open_access_pdf(pdf_url: str, timeout_sec: float = 12.0) -> Optional[bytes]:
    """
    Attempts to download an authentic Open Access PDF from publisher or repository.
    Includes browser headers, redirect handling, SSL fallback, and %PDF- verification.
    """
    if not pdf_url or not isinstance(pdf_url, str) or not pdf_url.startswith("http"):
        return None
        
    user_agent = os.getenv(
        "SCRAPER_USER_AGENT", 
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    
    headers = {
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/pdf,application/octet-stream,*/*;q=0.8",
        "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Upgrade-Insecure-Requests": "1"
    }
    
    try:
        resp = requests.get(pdf_url, headers=headers, timeout=timeout_sec, allow_redirects=True)
        if resp.status_code == 200:
            data = resp.content
            if is_authentic_pdf_bytes(data, min_size=1000):
                return data
            # Check if HTML returned with citation_pdf_url redirect
            if b"<html" in data[:500].lower():
                html_text = data[:5000].decode("utf-8", errors="ignore")
                meta_pdf = re.search(r'<meta\s+[^>]*?name=["\'](?:citation_pdf_url|eprints\.document_url)["\'][^>]*?content=["\'](.*?)["\']', html_text, re.I)
                if meta_pdf and meta_pdf.group(1).startswith("http") and meta_pdf.group(1) != pdf_url:
                    return try_fetch_open_access_pdf(meta_pdf.group(1), timeout_sec=timeout_sec)
    except Exception as e:
        logger.debug(f"Failed to fetch OA PDF from {pdf_url}: {e}")

    return None
