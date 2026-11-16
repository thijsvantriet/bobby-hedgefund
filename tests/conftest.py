"""A small local web server for the tests, so no test touches the internet."""

from __future__ import annotations

import gzip
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import pytest

from bobby_hedgefund.archive.fetch import Fetcher


class FakeSite:
    """Routes: path -> list of answers, used in order (the last one repeats).

    An answer is a dict: status, body, headers, gzip (bool), cut (announce more bytes than are sent).
    """

    def __init__(self) -> None:
        self.routes: dict[str, list[dict]] = {}
        self.hits: list[str] = []
        self.user_agents: list[str] = []
        # fake trial registry
        self.studies: list[dict] = []
        self.data_timestamp = "2026-11-13T10:00:06"
        self.stamp_after_pages: str | None = None  # the registry "refreshes" once the pages have been served
        self.lie_about_total: int | None = None
        self.exprs: list[str] = []

    def add(self, path: str, *answers: dict) -> None:
        self.routes[path] = list(answers)


def _handler(site: FakeSite) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args: object) -> None:  # keep test output clean
            pass

        def do_GET(self) -> None:
            parts = urlsplit(self.path)
            site.hits.append(self.path)
            site.user_agents.append(self.headers.get("User-Agent", ""))
            if parts.path == "/api/v2/version":
                self._send({"body": json.dumps({"apiVersion": "2.0.5", "dataTimestamp": site.data_timestamp}).encode()})
            elif parts.path == "/api/v2/studies":
                self._studies(parse_qs(parts.query))
            elif parts.path in site.routes:
                answers = site.routes[parts.path]
                self._send(answers.pop(0) if len(answers) > 1 else answers[0])
            else:
                self._send({"status": 404, "body": b"not found"})

        def _studies(self, query: dict[str, list[str]]) -> None:
            site.exprs.append(query["filter.advanced"][0])
            size = int(query["pageSize"][0])
            start = int(query.get("pageToken", ["0"])[0])
            doc: dict = {"studies": site.studies[start : start + size]}
            if start + size < len(site.studies):
                doc["nextPageToken"] = str(start + size)
            elif site.stamp_after_pages:
                site.data_timestamp = site.stamp_after_pages
            if query.get("countTotal") == ["true"]:
                doc["totalCount"] = len(site.studies) if site.lie_about_total is None else site.lie_about_total
            self._send({"body": json.dumps(doc).encode(), "gzip": True})

        def _send(self, answer: dict) -> None:
            body = answer.get("body", b"")
            if answer.get("gzip"):
                body = gzip.compress(body)
            self.send_response(answer.get("status", 200))
            for key, value in answer.get("headers", {}).items():
                self.send_header(key, value)
            if answer.get("gzip"):
                self.send_header("Content-Encoding", "gzip")
            self.send_header("Content-Length", str(len(body) + (50 if answer.get("cut") else 0)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


@pytest.fixture
def site():
    fake = FakeSite()
    server = ThreadingHTTPServer(("127.0.0.1", 0), _handler(fake))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    fake.base = f"http://127.0.0.1:{server.server_address[1]}"  # type: ignore[attr-defined]
    yield fake
    server.shutdown()
    server.server_close()


@pytest.fixture
def waits() -> list[float]:
    return []


@pytest.fixture
def fetcher(waits: list[float]) -> Fetcher:
    # no real waiting in tests; the requested waits are recorded instead
    return Fetcher(user_agent="test-agent/1", timeout=5, backoff=(1.0, 2.0), sleep=waits.append)
