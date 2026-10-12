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

from libera.host import session as sessions
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


def admit(
    host: str | None = OWN,
    origin: str | None = None,
    fetch_site: str | None = None,
    session: str = "s",
) -> Session:
    return admission.admit(
        host=host,
        origin=origin,
        fetch_site=fetch_site,
        port=PORT,
        query={"session": [session]},
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


def post(port: int, route: str, headers: dict[str, str] | None = None) -> int:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request("POST", f"/__host__/{route}?session=s", b"", headers or {})
    status = conn.getresponse().status
    conn.close()
    return status


def test_only_what_was_admitted_and_routed_is_counted(port):
    """The count is what the page asked the host to do, which the harness
    asserts on. Counted before admission, any site could add to it, under
    names of its own choosing."""
    assert post(port, "reveal") == 204
    assert post(port, "reveal", {"Origin": "https://evil.example"}) == 403
    assert post(port, "made-up-by-another-site") == 404

    assert diagnostics.ASKED == {"reveal": 1}
