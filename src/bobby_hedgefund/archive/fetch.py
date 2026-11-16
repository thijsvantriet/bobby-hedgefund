"""Polite HTTP downloads with the standard library only: a time limit, a size limit and a few retries."""

from __future__ import annotations

import http.client
import time
import urllib.error
import urllib.request
import zlib
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlsplit

# The client name sent with every request. Deliberately generic: no personal or project details (CLAUDE.md).
DEFAULT_USER_AGENT = "public-data-archiver/0.1"
RETRY_STATUS = frozenset({429, 500, 502, 503, 504})
KEPT_HEADERS = ("content-type", "last-modified", "etag", "date", "content-length", "content-encoding")
MAX_RETRY_AFTER = 300.0


class FetchError(Exception):
    """A download failed for good (after retries, where retrying made sense)."""


@dataclass(frozen=True)
class Response:
    url: str
    final_url: str
    status: int
    headers: dict[str, str]
    body: bytes


def _gunzip_bounded(raw: bytes, limit: int) -> bytes:
    decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
    try:
        out = decoder.decompress(raw, limit + 1)
    except zlib.error as exc:
        raise FetchError(f"broken gzip data: {exc}") from exc
    if len(out) > limit or decoder.unconsumed_tail:
        raise FetchError(f"response larger than the limit of {limit} bytes")
    if not decoder.eof:
        raise FetchError("gzip data ended early (incomplete download)")
    return out


@dataclass
class Fetcher:
    user_agent: str = DEFAULT_USER_AGENT
    timeout: float = 120.0
    max_bytes: int = 300 * 1024 * 1024
    backoff: tuple[float, ...] = (5.0, 30.0, 90.0)  # waits before retry 1, 2, 3
    sleep: Callable[[float], None] = time.sleep

    def get(self, url: str) -> Response:
        if urlsplit(url).scheme not in ("http", "https"):
            raise FetchError(f"only http(s) addresses are fetched, not {url!r}")
        attempt = 0
        while True:
            try:
                return self._get_once(url)
            except _Retryable as exc:
                if attempt >= len(self.backoff):
                    raise FetchError(f"{url}: {exc.reason} (gave up after {attempt + 1} tries)") from None
                wait = self.backoff[attempt]
                if exc.retry_after is not None:
                    wait = max(wait, min(exc.retry_after, MAX_RETRY_AFTER))
                self.sleep(wait)
                attempt += 1

    def _get_once(self, url: str) -> Response:
        request = urllib.request.Request(
            url, headers={"User-Agent": self.user_agent, "Accept": "*/*", "Accept-Encoding": "gzip"}
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as resp:
                status = resp.status
                headers = {k.lower(): v for k, v in resp.headers.items()}
                final_url = resp.geturl()
                raw = resp.read(self.max_bytes + 1)
        except urllib.error.HTTPError as exc:
            if exc.code in RETRY_STATUS:
                raise _Retryable(f"HTTP {exc.code}", _retry_after(exc.headers.get("Retry-After"))) from None
            raise FetchError(f"{url}: HTTP {exc.code}") from None
        except (OSError, http.client.HTTPException) as exc:
            # OSError covers network errors, time-outs and TLS errors; HTTPException covers broken responses
            raise _Retryable(f"{type(exc).__name__}: {exc}", None) from None
        if status != 200:
            raise FetchError(f"{url}: unexpected HTTP status {status}")
        if len(raw) > self.max_bytes:
            raise FetchError(f"{url}: response larger than the limit of {self.max_bytes} bytes")
        # A connection that drops halfway is not reported by read() when a size limit is passed: check it here,
        # so a cut-off download is retried and never stored as if it were the whole file.
        announced = headers.get("content-length", "")
        if announced.isdigit() and int(announced) != len(raw):
            raise _Retryable(f"incomplete download ({len(raw)} of {announced} bytes)", None)
        encoding = headers.get("content-encoding", "").strip().lower()
        if encoding == "gzip":
            try:
                body = _gunzip_bounded(raw, self.max_bytes)
            except FetchError as exc:
                raise _Retryable(str(exc), None) from None
        elif encoding in ("", "identity"):
            body = raw
        else:
            raise FetchError(f"{url}: unsupported Content-Encoding {encoding!r}")
        kept = {k: headers[k] for k in KEPT_HEADERS if k in headers}
        return Response(url=url, final_url=final_url, status=status, headers=kept, body=body)


class _Retryable(Exception):
    def __init__(self, reason: str, retry_after: float | None):
        super().__init__(reason)
        self.reason = reason
        self.retry_after = retry_after


def _retry_after(value: str | None) -> float | None:
    try:
        return max(0.0, float(value)) if value else None
    except ValueError:
        return None  # the date form of Retry-After: fall back to our own waiting times
