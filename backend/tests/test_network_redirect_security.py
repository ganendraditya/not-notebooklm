import io
import urllib.error
import urllib.request
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from types import SimpleNamespace

import pytest

import journal_indexer
from services.search import scopus_compiler


@contextmanager
def local_redirect_server():
    class RedirectHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.server.request_paths.append(self.path)
            if self.path == "/redirect":
                self.send_response(302)
                self.send_header(
                    "Location",
                    f"http://127.0.0.1:{self.server.server_port}/internal",
                )
                self.end_headers()
                return

            body = b"internal target reached"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), RedirectHandler)
    server.request_paths = []
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_http_client_defaults_follow_loopback_redirects():
    with local_redirect_server() as server:
        url = f"http://127.0.0.1:{server.server_port}/redirect"
        response = journal_indexer.requests.get(url, timeout=2)
        response.close()
        assert server.request_paths == ["/redirect", "/internal"]

    with local_redirect_server() as server:
        url = f"http://127.0.0.1:{server.server_port}/redirect"
        with urllib.request.urlopen(url, timeout=2) as response:
            response.read()
        assert server.request_paths == ["/redirect", "/internal"]


def test_sinta_lookup_blocks_redirect_to_loopback(monkeypatch):
    calls = []
    redirect = SimpleNamespace(
        status_code=302,
        headers={"Location": "http://127.0.0.1/internal"},
        close=lambda: None,
    )

    monkeypatch.setattr(journal_indexer, "_read_sinta_cache", lambda _: None)
    monkeypatch.setattr(
        journal_indexer,
        "safe_external_get",
        lambda url, **kwargs: calls.append((url, kwargs)) or redirect,
    )

    assert journal_indexer.lookup_sinta_live("12345678") is None
    assert len(calls) == 1


def test_sinta_http_client_does_not_reach_a_loopback_target(monkeypatch):
    with local_redirect_server() as server:
        base_url = f"http://127.0.0.1:{server.server_port}"

        monkeypatch.setattr(journal_indexer, "_read_sinta_cache", lambda _: None)

        assert journal_indexer.lookup_sinta_live("12345678") is None
        assert server.request_paths == []


def test_sinta_lookup_follows_safe_redirect_manually(monkeypatch):
    source_url = "https://sinta.kemdiktisaintek.go.id/journals?q=12345678"
    redirect_url = "https://sinta.kemdiktisaintek.go.id/journals/12345678"
    responses = [
        SimpleNamespace(
            status_code=302,
            headers={"Location": "/journals/12345678"},
            close=lambda: None,
        ),
        SimpleNamespace(status_code=200, headers={}, text="<html></html>"),
    ]
    calls = []

    monkeypatch.setattr(journal_indexer, "_read_sinta_cache", lambda _: None)
    monkeypatch.setattr(
        journal_indexer,
        "is_safe_external_url",
        lambda url: url == redirect_url,
    )
    monkeypatch.setattr(
        journal_indexer,
        "safe_external_get",
        lambda url, **kwargs: calls.append((url, kwargs)) or responses.pop(0),
    )

    assert journal_indexer.lookup_sinta_live("12345678") is None
    assert [call[0] for call in calls] == [source_url, redirect_url]
    assert all(call[1]["timeout"] == 3.0 for call in calls)


def test_scopus_redirect_handler_rejects_loopback(monkeypatch):
    monkeypatch.setattr(scopus_compiler, "is_safe_external_url", lambda _: False)
    handler = scopus_compiler.SafeExternalRedirectHandler()
    request = urllib.request.Request("https://raw.example.test/index.csv")

    with pytest.raises(urllib.error.HTTPError, match="Blocked unsafe redirect"):
        handler.redirect_request(
            request,
            io.BytesIO(),
            302,
            "Found",
            {},
            "http://127.0.0.1/internal",
        )


def test_scopus_redirect_handler_allows_validated_public_target(monkeypatch):
    redirect_url = "https://downloads.example.test/index.csv"
    monkeypatch.setattr(
        scopus_compiler,
        "is_safe_external_url",
        lambda url: url == redirect_url,
    )
    handler = scopus_compiler.SafeExternalRedirectHandler()
    request = urllib.request.Request("https://raw.example.test/index.csv")

    redirected = handler.redirect_request(
        request,
        io.BytesIO(),
        302,
        "Found",
        {},
        redirect_url,
    )

    assert redirected.full_url == redirect_url


def test_scopus_compiler_registers_safe_redirect_handler(monkeypatch, tmp_path):
    handlers = []

    class OfflineOpener:
        def open(self, request, timeout):
            raise OSError("offline test")

    def build_opener(*configured_handlers):
        handlers.extend(configured_handlers)
        return OfflineOpener()

    monkeypatch.setattr(scopus_compiler.urllib.request, "build_opener", build_opener)

    assert not scopus_compiler.build_scopus_index_db(str(tmp_path / "scopus.db"))
    assert len(handlers) == 1
    assert isinstance(handlers[0], scopus_compiler.SafeExternalRedirectHandler)


def test_scopus_http_client_does_not_follow_loopback_redirect(monkeypatch, tmp_path):
    with local_redirect_server() as server:
        monkeypatch.setattr(
            scopus_compiler,
            "OPENJOURNALS_CSV_URL",
            f"http://127.0.0.1:{server.server_port}/redirect",
        )

        assert not scopus_compiler.build_scopus_index_db(str(tmp_path / "scopus.db"))
        assert server.request_paths == ["/redirect"]
