"""Who may ask the host anything.

The server is on 127.0.0.1, which every page in every browser on this machine
can reach. `admission.admit` is the whole policy, and it is pure, so it is
tested here as a function; the integration tier tests it again over HTTP, but
skips without a payload.
"""

from __future__ import annotations

import http.client
import threading

import pytest

from libera.host import instance, session as sessions
from libera.host.server import adapter, admission, diagnostics, listener
from libera.host.server.api import Refused
from libera.host.session import Session

PORT = "43110"
OWN = f"127.0.0.1:{PORT}"


@pytest.fixture
def window(tmp_path) -> Session:
    found = Session(payload=tmp_path / "payload", work=tmp_path / "s")
    sessions.configure(found)
    return found


# The tests' names for the headers admit() reads.
HEADERS = {
    "host": "Host",
    "origin": "Origin",
    "fetch_site": "Sec-Fetch-Site",
    "cookie": "Cookie",
}


def admit(
    *, session: str = "s", key: str | None = instance.TOKEN, **asked: str | None
) -> Session:
    sent = {"host": OWN} | asked
    query = {"session": [session]} | ({} if key is None else {"key": [key]})
    return admission.admit(
        headers={HEADERS[name]: v for name, v in sent.items() if v is not None},
        port=PORT,
        query=query,
    )


@pytest.mark.parametrize(
    "asked",
    [
        {},
        {"origin": f"http://{OWN}"},
        {"fetch_site": "same-origin"},
        # A navigation the application started: the window's first page.
        {"fetch_site": "none"},
        {"origin": f"http://{OWN}", "fetch_site": "same-origin"},
    ],
    ids=["hand-off or test", "own origin", "same-origin", "navigation", "both"],
)
def test_our_own_pages_and_processes_are_let_in(window, asked):
    assert admit(**asked) is window


@pytest.mark.parametrize(
    "asked",
    [
        # DNS rebinding: a name the attacker controls, resolved to us.
        {"host": f"evil.example:{PORT}"},
        {"host": None},
        {"origin": "https://evil.example"},
        # A sandboxed frame, or a page opened from a file.
        {"origin": "null"},
        # Another port on this machine is another origin.
        {"origin": "http://127.0.0.1:8000"},
        # A GET has no Origin: another site's <script src> on our address.
        {"fetch_site": "cross-site"},
        {"fetch_site": "same-site"},
        {"origin": f"http://{OWN}", "fetch_site": "cross-site"},
    ],
    ids=[
        "rebound name",
        "no host",
        "foreign origin",
        "null origin",
        "another port",
        "cross-site",
        "same-site",
        "own origin, cross-site",
    ],
)
def test_anything_else_is_refused(window, asked):
    with pytest.raises(Refused) as refused:
        admit(**asked)

    assert refused.value.status == 403


def test_the_key_may_come_in_its_cookie(window):
    """Every request after a window's first: its frames, scripts and fonts."""
    cookie = f"theme=dark; {admission.cookie_name(PORT)}={instance.TOKEN}"

    assert admit(key=None, cookie=cookie) is window


@pytest.mark.parametrize(
    "asked",
    [
        {"key": None},
        {"key": ""},
        {"key": "guessed"},
        {"key": None, "cookie": f"{admission.cookie_name(PORT)}=guessed"},
        {"key": None, "cookie": f"other={instance.TOKEN}"},
        {"key": None, "cookie": f"{admission.cookie_name('43111')}={instance.TOKEN}"},
    ],
    ids=[
        "no key",
        "empty key",
        "wrong key",
        "wrong cookie",
        "another cookie",
        "another port's cookie",
    ],
)
def test_a_request_without_the_key_is_refused(window, asked):
    """Headers stop a browser, and no other client: curl, from any account on
    this machine, sends the Host and no Origin, and read the open document."""
    with pytest.raises(Refused) as refused:
        admit(**asked)

    assert refused.value.status == 403


def test_a_session_that_has_gone_is_not_found(window):
    with pytest.raises(Refused) as refused:
        admit(session="closed")

    assert refused.value.status == 404


@pytest.fixture
def port(window, tmp_path):
    """The host's real server, on a port of its own."""
    server = listener.Server(("127.0.0.1", 0), listener.QuietHandler)
    server.set_app(adapter.make_app(tmp_path / "payload"))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield server.server_address[1]
    server.shutdown()
    server.server_close()


def ask(
    port: int, method: str, path: str, headers: dict[str, str] | None = None
) -> http.client.HTTPResponse:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request(method, path, b"" if method == "POST" else None, headers or {})
    answer = conn.getresponse()
    answer.read()
    conn.close()
    return answer


def post(port: int, route: str, headers: dict[str, str] | None = None) -> int:
    path = f"/__host__/{route}?session=s&key={instance.TOKEN}"
    return ask(port, "POST", path, headers).status


def test_only_what_was_admitted_and_routed_is_counted(port):
    """The count is what the page asked the host to do, which the harness
    asserts on. Counted before admission, any site could add to it, under
    names of its own choosing."""
    assert post(port, "reveal") == 204
    assert post(port, "reveal", {"Origin": "https://evil.example"}) == 403
    assert post(port, "made-up-by-another-site") == 404

    assert diagnostics.ASKED == {"reveal": 1}


@pytest.mark.parametrize(
    "path",
    ["/__host__/current", "/__host__/opened", "/__host__/recents", "/sdkjs/x.js"],
)
def test_no_route_answers_a_request_without_the_key(port, path):
    """The measurement this check came from, every address of it: the host's
    endpoints and the payload alike."""
    assert ask(port, "GET", path).status == 403


def test_the_first_page_hands_its_key_to_a_cookie(port):
    """A window's URL carries the key once; the cookie carries it after."""
    first = ask(port, "POST", f"/__host__/reveal?session=s&key={instance.TOKEN}")
    cookie = first.getheader("Set-Cookie", "")
    later = ask(port, "POST", "/__host__/reveal?session=s", {"Cookie": cookie})

    assert f"{admission.cookie_name(str(port))}={instance.TOKEN}" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=Strict" in cookie
    assert later.status == 204
    assert later.getheader("Set-Cookie") is None
