from __future__ import annotations

import pytest

from bobby_hedgefund.archive.fetch import Fetcher, FetchError


def test_plain_download(site, fetcher: Fetcher) -> None:
    site.add(
        "/f",
        {"body": b"hello", "headers": {"Last-Modified": "Mon, 16 Nov 2026 08:00:00 GMT", "X-Other": "1"}},
    )
    resp = fetcher.get(site.base + "/f")
    assert resp.body == b"hello" and resp.status == 200
    assert resp.headers["last-modified"] == "Mon, 16 Nov 2026 08:00:00 GMT"
    assert "x-other" not in resp.headers  # only a fixed set of headers is kept
    assert site.user_agents == ["test-agent/1"]


def test_gzip_transfer_is_decoded(site, fetcher: Fetcher) -> None:
    site.add("/f", {"body": b"abc" * 1000, "gzip": True})
    assert fetcher.get(site.base + "/f").body == b"abc" * 1000


def test_retries_on_server_error_then_succeeds(site, fetcher: Fetcher, waits: list[float]) -> None:
    site.add("/f", {"status": 503}, {"status": 500}, {"body": b"ok"})
    assert fetcher.get(site.base + "/f").body == b"ok"
    assert waits == [1.0, 2.0]


def test_gives_up_after_the_last_retry(site, fetcher: Fetcher, waits: list[float]) -> None:
    site.add("/f", {"status": 503})
    with pytest.raises(FetchError, match="gave up after 3 tries"):
        fetcher.get(site.base + "/f")
    assert len(site.hits) == 3 and waits == [1.0, 2.0]


def test_too_many_requests_waits_as_asked_but_not_forever(site, fetcher: Fetcher, waits: list[float]) -> None:
    site.add(
        "/f",
        {"status": 429, "headers": {"Retry-After": "40"}},
        {"status": 429, "headers": {"Retry-After": "99999"}},
        {"body": b"ok"},
    )
    assert fetcher.get(site.base + "/f").body == b"ok"
    assert waits == [40.0, 300.0]


def test_not_found_fails_at_once(site, fetcher: Fetcher, waits: list[float]) -> None:
    with pytest.raises(FetchError, match="HTTP 404"):
        fetcher.get(site.base + "/missing")
    assert len(site.hits) == 1 and waits == []


def test_cut_off_download_is_not_accepted(site, fetcher: Fetcher) -> None:
    site.add("/f", {"body": b"only part of the file", "cut": True})
    with pytest.raises(FetchError, match=r"incomplete|IncompleteRead"):
        fetcher.get(site.base + "/f")
    assert len(site.hits) == 3  # it was retried first


def test_cut_off_download_recovers_on_retry(site, fetcher: Fetcher) -> None:
    site.add("/f", {"body": b"only part", "cut": True}, {"body": b"the whole file"})
    assert fetcher.get(site.base + "/f").body == b"the whole file"


def test_size_limit(site, waits: list[float]) -> None:
    small = Fetcher(timeout=5, max_bytes=100, backoff=(), sleep=waits.append)
    site.add("/big", {"body": b"x" * 101})
    site.add("/bomb", {"body": b"x" * 100_000, "gzip": True})  # small on the wire, large once unpacked
    site.add("/fits", {"body": b"x" * 100})
    with pytest.raises(FetchError, match="larger than the limit"):
        small.get(site.base + "/big")
    with pytest.raises(FetchError, match="larger than the limit"):
        small.get(site.base + "/bomb")
    assert len(small.get(site.base + "/fits").body) == 100


@pytest.mark.parametrize("url", ["file:///etc/hostname", "ftp://example.org/x", "/etc/hostname"])
def test_only_web_addresses(fetcher: Fetcher, url: str) -> None:
    with pytest.raises(FetchError, match="only http"):
        fetcher.get(url)


def test_unreachable_server(fetcher: Fetcher, waits: list[float]) -> None:
    with pytest.raises(FetchError, match="gave up"):
        fetcher.get("http://127.0.0.1:9/nothing-listens-here")
    assert waits == [1.0, 2.0]
