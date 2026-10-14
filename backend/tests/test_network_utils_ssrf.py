import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest
import requests

from utils import network_utils


def test_safe_external_get_pins_the_validated_dns_answer(monkeypatch):
    resolved_hosts = []
    connect_targets = []

    def rebinding_dns(host, port, **_kwargs):
        if host == "rebind.test":
            resolved_hosts.append(host)
            ip = "93.184.216.34" if len(resolved_hosts) == 1 else "127.0.0.1"
            return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (ip, port))]
        raise AssertionError(f"Unexpected DNS lookup: {host}")

    def blocked_connect(address, *_args, **_kwargs):
        connect_targets.append(address)
        raise OSError("test connection blocked")

    monkeypatch.setattr(network_utils.socket, "getaddrinfo", rebinding_dns)
    monkeypatch.setattr(network_utils, "create_connection", blocked_connect)

    with pytest.raises(requests.exceptions.ConnectionError):
        network_utils.safe_external_get("http://rebind.test:8080/paper.pdf", timeout=0.1)

    assert resolved_hosts == ["rebind.test"]
    assert connect_targets == [("93.184.216.34", 8080)]


def test_safe_external_get_uses_the_pinned_ip_and_keeps_the_hostname(monkeypatch):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = self.headers["Host"].encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    hostname = "publisher.example.test"
    monkeypatch.setattr(
        network_utils,
        "_resolve_public_endpoint",
        lambda _url: (hostname, server.server_port, "127.0.0.1"),
    )

    try:
        response = network_utils.safe_external_get(
            f"http://{hostname}:{server.server_port}/paper.pdf",
            timeout=2,
        )

        assert response.status_code == 200
        assert response.content == f"{hostname}:{server.server_port}".encode()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_safe_external_get_rejects_mixed_public_and_private_dns_answers(monkeypatch):
    connect_attempts = []

    def mixed_dns(host, port, **_kwargs):
        return [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("93.184.216.34", port)),
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("127.0.0.1", port)),
        ]

    monkeypatch.setattr(network_utils.socket, "getaddrinfo", mixed_dns)
    monkeypatch.setattr(
        network_utils,
        "create_connection",
        lambda *args, **kwargs: connect_attempts.append(args),
    )

    with pytest.raises(ValueError, match="not safe"):
        network_utils.safe_external_get("http://mixed.test:8080/paper.pdf", timeout=0.1)

    assert connect_attempts == []
