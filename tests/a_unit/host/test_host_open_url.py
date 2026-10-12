"""The host opens URLs on the desktop, so the page must not choose the scheme.

The editor asks the host to open external links because WKWebView drops
script-opened windows. That hands page content a lever on the desktop, and the
only thing between the two is this check.

`desktop.open_url` is stubbed here rather than `subprocess`: the endpoint's job
is to decide *whether* a URL reaches the desktop, and that is the boundary
worth pinning. How the desktop is asked, and whether it agreed, belongs to
test_desktop_open_url.py beside it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from libera.host import desktop, server
from libera.host.server.api import Refused, Request
from libera.host.session import Session


def request(url: object) -> Request:
    """What open_url reads: the URL, in the body. It reads no session."""
    body = json.dumps({"url": url}).encode()
    return Request(Session(payload=Path("payload"), work=Path("work")), body)


@pytest.fixture
def launched(monkeypatch):
    """Every URL that reached the desktop."""
    urls: list[str] = []
    monkeypatch.setattr(desktop, "open_url", lambda url: urls.append(url) or True)
    return urls


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "javascript:alert(1)",
        "data:text/html,<script>x</script>",
        "  ",
        "https://example.com/ with space",
        "https://example.com/\n",
        "ssh://box/x",
        None,
    ],
)
def test_refuses_anything_but_http(url, launched):
    with pytest.raises(Refused) as refused:
        server.open_url(request(url))
    assert refused.value.status == 400
    assert launched == []


@pytest.mark.parametrize("url", ["https://example.com/x", "http://example.com/"])
def test_opens_http(url, launched):
    assert server.open_url(request(url)).status == 204
    assert launched == [url]


def test_the_page_is_told_nothing_when_the_desktop_refuses(monkeypatch):
    """A desktop with no handler is the desktop's business, not the page's.

    There is nothing useful a page can do about it, and telling it would hand
    page content a way to probe what the machine has installed.
    """
    monkeypatch.setattr(desktop, "open_url", lambda _url: False)
    assert server.open_url(request("https://example.com/x")).status == 204
