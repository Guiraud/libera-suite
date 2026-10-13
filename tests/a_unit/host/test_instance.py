"""One running Libera Suite: a second launch hands its documents to the first.

The hand-off is what double-clicking a second document does on Windows, where
every double-click is a new process. What can go wrong is who gets to open a
file (the key), what a stale announcement costs (nothing but a start), and
whose announcement goes when an instance exits (only its own).
"""

from __future__ import annotations

import json
import socket
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from support import ScriptedShell

from libera.host import hooks, instance, session as sessions
from libera.host.server import adapter, listener, opening
from libera.host.server.api import Refused, Request
from libera.host.session import Session
from libera.payload import locate


@pytest.fixture
def state(tmp_path, monkeypatch):
    """A temporary state directory, with instance.json inside it.

    The suite's own setup (pytest_runtest_setup, in tests/conftest.py) points
    instance.get_path at a temporary file of its own; these tests also need
    get_state_dir, so both point at the same directory here -- which is where
    the real path() would put it.
    """
    monkeypatch.setattr(locate, "get_state_dir", lambda: tmp_path)
    monkeypatch.setattr(instance, "get_path", lambda: tmp_path / "instance.json")
    return tmp_path


@pytest.fixture
def running(state):
    """A stand-in for the first instance's server: records what it is sent."""
    received: list[dict] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            received.append({
                "path": self.path,
                **json.loads(self.rfile.read(int(self.headers["Content-Length"]))),
            })
            body = b'{"opened": true}'
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    instance.announce(server.server_address[1])
    yield received
    server.shutdown()
    server.server_close()


def test_nothing_announced_means_start_here(state):
    assert instance.hand_off([]) is False


def test_a_stale_announcement_means_start_here(state):
    """A crash leaves the file behind, and nothing listens on its port."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        dead_port = s.getsockname()[1]
    instance.announce(dead_port)

    assert instance.hand_off([state / "a.docx"]) is False


def test_a_running_instance_takes_the_documents(running, tmp_path):
    doc = tmp_path / "Report.docx"

    assert instance.hand_off([doc]) is True
    assert running == [
        {
            "path": f"/__host__/hand-off?key={instance.TOKEN}",
            "documents": [str(doc)],
        }
    ]


def test_withdraw_leaves_another_instances_announcement(state):
    """The first instance to exit must not orphan the one still running."""
    (state / "instance.json").write_text(
        json.dumps({"port": 1, "token": "someone-else", "pid": 1}), encoding="utf-8"
    )
    instance.withdraw()
    assert (state / "instance.json").is_file()

    instance.announce(2)
    instance.withdraw()
    assert not (state / "instance.json").exists()


@pytest.fixture
def handler(tmp_path):
    """A hand-off request with that body. Any session: the hand-off reads none."""

    def make(body: dict) -> Request:
        anyone = Session(payload=tmp_path / "payload", work=tmp_path / "s")
        return Request(anyone, json.dumps(body).encode())

    return make


class Opened:
    """What the shell was asked to open, on the hand-off's own thread."""

    def __init__(self) -> None:
        self.documents: list = []
        self.asked = threading.Event()

    def wait(self) -> list:
        assert self.asked.wait(5), "nothing was opened"
        return self.documents

    def open_window(self, doc, _app=None) -> bool:
        self.documents.append(doc)
        self.asked.set()
        return True

    def show_start_window(self) -> None:
        self.documents.append("start")
        self.asked.set()


@pytest.fixture
def opened(monkeypatch):
    calls = Opened()
    monkeypatch.setattr(
        hooks,
        "shell",
        ScriptedShell(
            open_window=calls.open_window, show_start_window=calls.show_start_window
        ),
    )
    return calls


def test_the_right_key_opens_each_file_that_exists(handler, opened, tmp_path):
    doc = tmp_path / "Report.docx"
    doc.write_bytes(b"PK")
    # The missing one first: by the time the other opens, it has been passed.
    h = handler({"documents": [str(tmp_path / "gone.docx"), str(doc)]})

    answer = opening.take_hand_off(h)

    assert json.loads(answer.body)["opened"] is True
    assert opened.wait() == [doc]


def test_no_documents_puts_the_start_window_up(handler, opened):
    """The icon clicked while Libera Suite is already open."""
    h = handler({"documents": []})

    opening.take_hand_off(h)

    assert opened.wait() == ["start"]


@pytest.mark.parametrize(
    "body",
    [
        {"documents": "/a/Report.docx"},
        {"documents": [1]},
    ],
    ids=["documents a string", "a path a number"],
)
def test_a_body_of_the_wrong_shape_is_a_400(handler, opened, body):
    """A string for documents was one path per character."""
    with pytest.raises(Refused) as refused:
        opening.take_hand_off(handler(body))

    assert refused.value.status == 400
    assert opened.documents == []


@pytest.fixture
def serving(state, tmp_path):
    """This instance's real server, announced where a second launch looks."""
    sessions.configure(Session(payload=tmp_path / "payload", work=tmp_path / "s"))
    server = listener.Server(("127.0.0.1", 0), listener.QuietHandler)
    server.set_app(adapter.make_app(tmp_path / "payload"))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    instance.announce(server.server_address[1])
    yield server.server_address[1]
    server.shutdown()
    server.server_close()


def test_the_answer_does_not_wait_for_the_window(serving, monkeypatch, tmp_path):
    """Opening is a conversion, and a recovery or an error dialog waits on the
    user. A sender left waiting past its timeout took that for no instance
    and started a second, which swept this one's session directories."""
    doc = tmp_path / "Report.docx"
    doc.write_bytes(b"PK")
    asked, release = threading.Event(), threading.Event()

    def open_window(_doc, _app=None) -> bool:
        asked.set()
        release.wait(5)
        return True

    monkeypatch.setattr(hooks, "shell", ScriptedShell(open_window=open_window))
    monkeypatch.setattr(instance, "HAND_OFF_TIMEOUT", 1.0)
    try:
        assert instance.hand_off([doc]) is True
        assert asked.wait(5)
    finally:
        release.set()


def test_a_hand_off_without_the_key_opens_nothing(serving, opened, tmp_path):
    """Any process on this machine, and any page in any browser, can POST to
    127.0.0.1; the key, which only this user can read, is the fence."""
    doc = tmp_path / "Report.docx"
    doc.write_bytes(b"PK")
    body = json.dumps({"documents": [str(doc)]}).encode()
    for query in ("", "?key=guessed"):
        request = urllib.request.Request(
            f"http://127.0.0.1:{serving}/__host__/hand-off{query}",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with pytest.raises(urllib.error.HTTPError) as refused:
            urllib.request.urlopen(request, timeout=5)

        assert refused.value.code == 403
    assert opened.documents == []
