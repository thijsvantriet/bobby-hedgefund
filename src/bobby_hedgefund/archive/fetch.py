"""Polite HTTP downloads with the standard library only: a time limit, a size limit and a few retries."""

from __future__ import annotations

import functools
import http.client
import time
import urllib.error
import urllib.request
import zlib
from collections.abc import Callable
from dataclasses import dataclass, field
from urllib.parse import urlsplit

# The client name sent with every request. Deliberately generic: no personal or project details (CLAUDE.md).
DEFAULT_USER_AGENT = "public-data-archiver/0.1"
RETRY_STATUS = frozenset({429, 500, 502, 503, 504})
KEPT_HEADERS = ("content-type", "last-modified", "etag", "date", "content-length", "content-encoding")
MAX_RETRY_AFTER = 300.0


class FetchError(Exception):
    """A download failed for good (after retries, where retrying made sense)."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status  # the HTTP status, when the publisher answered with one


@dataclass(frozen=True)
class Response:
    url: str
    final_url: str
    status: int
    headers: dict[str, str]
    body: bytes


def _gunzip_bounded(raw: bytes, limit: int) -> bytes:
    """Unpack gzip data, refusing output above `limit` and data that stops early.

    A gzip stream may consist of several parts ("members") in a row; all of them belong to the body.
    """
    out = bytearray()
    rest = raw
    while rest:
        decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
        try:
            out += decoder.decompress(rest, limit + 1 - len(out))
        except zlib.error as exc:
            raise FetchError(f"broken gzip data: {exc}") from exc
        if len(out) > limit or decoder.unconsumed_tail:
            raise FetchError(f"response larger than the limit of {limit} bytes")
        if not decoder.eof:
            raise FetchError("gzip data ended early (incomplete download)")
        rest = decoder.unused_data
    return bytes(out)


class _SafeRedirects(urllib.request.HTTPRedirectHandler):
    """Follow redirects only to web addresses, and never from an encrypted address to an unencrypted one.

    With `allowed_hosts`, a redirect to any other host is refused: the request headers travel along with a
    redirect, and a header that declares who is asking must not reach a host it was not meant for."""

    allowed_hosts: frozenset[str] | None = None

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        old, new = urlsplit(req.full_url).scheme, urlsplit(newurl).scheme
        if new not in ("http", "https") or (old == "https" and new != "https"):
            raise urllib.error.HTTPError(newurl, code, f"refused redirect from {old} to {new}", headers, fp)
        if self.allowed_hosts is not None and (urlsplit(newurl).hostname or "") not in self.allowed_hosts:
            raise urllib.error.HTTPError(newurl, code, "refused redirect to another host", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


@functools.cache
def _opener(allowed_hosts: frozenset[str] | None) -> urllib.request.OpenerDirector:
    handler = _SafeRedirects()
    handler.allowed_hosts = allowed_hosts
    return urllib.request.build_opener(handler)


@dataclass
class Fetcher:
    # Not shown when a fetcher is printed: for some publishers the client name carries a contact address.
    user_agent: str = field(default=DEFAULT_USER_AGENT, repr=False)
    allowed_hosts: frozenset[str] | None = None  # when set: only these hosts are asked, also after a redirect
    # Extra request headers, for example a key. Never shown when a fetcher is printed, and never part of an error
    # message or a stored line. Give `allowed_hosts` along with a key: headers travel with a redirect.
    headers: dict[str, str] = field(default_factory=dict, repr=False)
    timeout: float = 120.0
    max_bytes: int = 300 * 1024 * 1024
    backoff: tuple[float, ...] = (5.0, 30.0, 90.0)  # waits before retry 1, 2, 3
    sleep: Callable[[float], None] = time.sleep

    def get(self, url: str, *, retry_refused: bool = True) -> Response:
        """Download one address. With retry_refused=False a "too many requests" answer (HTTP 429) is not retried
        here: the caller comes back much later, because quick retries can keep a publisher's block alive."""
        if urlsplit(url).scheme not in ("http", "https"):
            raise FetchError(f"only http(s) addresses are fetched, not {url!r}")
        if self.allowed_hosts is not None and (urlsplit(url).hostname or "") not in self.allowed_hosts:
            raise FetchError(f"{url}: this host is not on the list this fetcher may ask")
        attempt = 0
        while True:
            try:
                return self._get_once(url)
            except _Retryable as exc:
                if exc.refused and not retry_refused:
                    asked = "" if exc.retry_after is None else f", asked to wait {exc.retry_after:.0f} s"
                    raise FetchError(f"{url}: {exc.reason} (not retried at once{asked})") from None
                if attempt >= len(self.backoff):
                    raise FetchError(f"{url}: {exc.reason} (gave up after {attempt + 1} tries)") from None
                wait = self.backoff[attempt]
                if exc.retry_after is not None:
                    wait = max(wait, min(exc.retry_after, MAX_RETRY_AFTER))
                self.sleep(wait)
                attempt += 1

    def _get_once(self, url: str) -> Response:
        request = urllib.request.Request(
            url, headers={**self.headers, "User-Agent": self.user_agent, "Accept": "*/*", "Accept-Encoding": "gzip"}
        )
        try:
            with _opener(self.allowed_hosts).open(request, timeout=self.timeout) as resp:
                status = resp.status
                headers = {k.lower(): v for k, v in resp.headers.items()}
                final_url = resp.geturl()
                raw = resp.read(self.max_bytes + 1)
        except urllib.error.HTTPError as exc:
            if exc.code in RETRY_STATUS:
                waiting = _retry_after(exc.headers.get("Retry-After"))
                raise _Retryable(f"HTTP {exc.code}", waiting, refused=exc.code == 429) from None
            raise FetchError(f"{url}: HTTP {exc.code}", status=exc.code) from None
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
    def __init__(self, reason: str, retry_after: float | None, refused: bool = False):
        super().__init__(reason)
        self.reason = reason
        self.retry_after = retry_after
        self.refused = refused  # the publisher said "too many requests" (HTTP 429)


def _retry_after(value: str | None) -> float | None:
    try:
        return max(0.0, float(value)) if value else None
    except ValueError:
        return None  # the date form of Retry-After: fall back to our own waiting times
