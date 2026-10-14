import ipaddress
import socket
import urllib.parse
import logging
from typing import Optional, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.connection import HTTPConnection, HTTPSConnection
from urllib3.connectionpool import HTTPConnectionPool, HTTPSConnectionPool
from urllib3.exceptions import NewConnectionError
from urllib3.util.connection import create_connection

logger = logging.getLogger("uvicorn.error")


class _PinnedConnectionMixin:
    def __init__(self, *args, pinned_ip: str, **kwargs):
        self._pinned_ip = pinned_ip
        super().__init__(*args, **kwargs)

    def _new_conn(self):
        try:
            return create_connection(
                (self._pinned_ip, self.port),
                self.timeout,
                source_address=self.source_address,
                socket_options=self.socket_options,
            )
        except OSError as exc:
            raise NewConnectionError(
                self,
                f"Failed to connect to validated address {self._pinned_ip}: {exc}",
            ) from exc


class _PinnedHTTPConnection(_PinnedConnectionMixin, HTTPConnection):
    pass


class _PinnedHTTPSConnection(_PinnedConnectionMixin, HTTPSConnection):
    pass


class _PinnedHTTPConnectionPool(HTTPConnectionPool):
    ConnectionCls = _PinnedHTTPConnection


class _PinnedHTTPSConnectionPool(HTTPSConnectionPool):
    ConnectionCls = _PinnedHTTPSConnection


class _PinnedIPAdapter(HTTPAdapter):
    def __init__(self, pinned_ip: str):
        self._pinned_ip = pinned_ip
        self._request_pool = None
        super().__init__()

    def get_connection_with_tls_context(self, request, verify, proxies=None, cert=None):
        if proxies:
            raise ValueError("Proxies are disabled for validated outbound requests")

        parsed = urllib.parse.urlsplit(request.url)
        pool_class = _PinnedHTTPSConnectionPool if parsed.scheme == "https" else _PinnedHTTPConnectionPool
        default_port = 443 if parsed.scheme == "https" else 80
        self._request_pool = pool_class(
            host=parsed.hostname,
            port=parsed.port or default_port,
            pinned_ip=self._pinned_ip,
        )
        return self._request_pool

    def close(self):
        if self._request_pool is not None:
            self._request_pool.close()
            self._request_pool = None
        super().close()


def _resolve_public_endpoint(url: Optional[str]) -> Optional[Tuple[str, int, str]]:
    """
    Resolves a URL once and returns its hostname, port, and validated address.
    """
    if not url or not isinstance(url, str):
        return None
        
    trimmed = url.strip()
    try:
        parsed = urllib.parse.urlsplit(trimmed)
        if parsed.scheme.lower() not in ("http", "https"):
            return None

        hostname = parsed.hostname
        if not hostname or parsed.username is not None or parsed.password is not None:
            return None

        port = parsed.port if parsed.port is not None else (443 if parsed.scheme.lower() == "https" else 80)
        if not 1 <= port <= 65535:
            return None

        lower_host = hostname.lower()
        normalized_host = lower_host.rstrip(".")
        if normalized_host in ("localhost", "metadata.google.internal") or \
           normalized_host.endswith(".local") or normalized_host.endswith(".internal"):
            return None

        addr_info = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
        if not addr_info:
            return None

        validated_addresses = []
        for _, _, _, _, sockaddr in addr_info:
            ip_str = sockaddr[0]
            ip = ipaddress.ip_address(ip_str)
            if not ip.is_global or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
                logger.warning(f"[SSRF Guard] Blocked outbound request to non-public IP: {ip_str} for host: {hostname}")
                return None
            if ip_str not in validated_addresses:
                validated_addresses.append(ip_str)

        return hostname, port, validated_addresses[0]
    except Exception as e:
        logger.debug(f"[SSRF Guard] URL validation exception for {url}: {e}")
        return None


def is_safe_external_url(url: Optional[str]) -> bool:
    """Checks that a URL resolves exclusively to globally routable addresses."""
    return _resolve_public_endpoint(url) is not None


def safe_external_get(
    url: str,
    *,
    headers: Optional[dict] = None,
    timeout: float = 10.0,
) -> requests.Response:
    """GET a public URL using the exact IP address approved during validation."""
    endpoint = _resolve_public_endpoint(url)
    if endpoint is None:
        raise ValueError(f"Outbound URL is not safe: {url}")

    _, _, pinned_ip = endpoint
    session = requests.Session()
    session.trust_env = False
    adapter = _PinnedIPAdapter(pinned_ip)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    try:
        return session.get(
            url,
            headers=headers,
            timeout=timeout,
            allow_redirects=False,
        )
    finally:
        session.close()
