import ipaddress
import socket
import urllib.parse
import logging
from typing import Optional

logger = logging.getLogger("uvicorn.error")

def is_safe_external_url(url: Optional[str]) -> bool:
    """
    Validates whether an external URL is safe for server-side outbound requests (SSRF defense).
    Enforces HTTP/HTTPS and rejects loopback (127.0.0.0/8), RFC 1918 private subnets,
    link-local metadata (169.254.0.0/16), multicast, reserved, or internal hostnames.
    """
    if not url or not isinstance(url, str):
        return False
        
    trimmed = url.strip()
    try:
        parsed = urllib.parse.urlparse(trimmed)
        if parsed.scheme.lower() not in ("http", "https"):
            return False
            
        hostname = parsed.hostname
        if not hostname:
            return False
            
        lower_host = hostname.lower()
        # Block localhost and cloud metadata domain aliases
        if lower_host in ("localhost", "127.0.0.1", "::1", "metadata.google.internal") or \
           lower_host.endswith(".local") or lower_host.endswith(".internal"):
            return False

        # Resolve all DNS records (IPv4 & IPv6)
        addr_info = socket.getaddrinfo(hostname, None)
        for _, _, _, _, sockaddr in addr_info:
            ip_str = sockaddr[0]
            ip = ipaddress.ip_address(ip_str)
            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_multicast
                or ip.is_reserved
                or ip.is_unspecified
            ):
                logger.warning(f"[SSRF Guard] Blocked outbound request to non-public IP: {ip_str} for host: {hostname}")
                return False
                
        return True
    except Exception as e:
        logger.debug(f"[SSRF Guard] URL validation exception for {url}: {e}")
        return False
