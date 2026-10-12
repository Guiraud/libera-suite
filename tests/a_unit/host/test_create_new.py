"""File > New, for a new document of any kind, and the start window.

The editor's own File > Create New asks for its own kind; the bridge offers the
choice (bridge-desktop.js, chooseNewKind) and asks the host for the one chosen,
which is what these send.
"""

from __future__ import annotations

import json

import pytest
from support import ScriptedShell

from libera.host import app, apps, hooks, session
from libera.host.server import opening
from libera.host.server.api import Refused, Request
from libera.host.session import Session
from libera.host.window import windows


@pytest.fixture
def host(tmp_path):
    payload = tmp_path / "payload"
    (payload / "empty").mkdir(parents=True)
    for editor in apps.ALL:
        if editor.blank:
            (payload / "empty" / editor.blank).write_bytes(b"PK")
    session.configure(Session(payload=payload, work=tmp_path / "work"))


@pytest.fixture
def opened(monkeypatch):
    calls: list = []
    monkeypatch.setattr(
        hooks,
        "shell",
        ScriptedShell(
            open_window=lambda doc, kind=None: calls.append((doc, kind)) is None,
            show_start_window=lambda: calls.append("start"),
        ),
    )
    return calls


def request(**fields) -> Request:
    return Request(session.lookup(""), body=json.dumps(fields).encode())


def test_each_kind_opens_in_a_window_of_its_own(host, opened):
    for doctype in ("word", "cell", "slide"):
        answer = opening.create_new(request(type=doctype))
        assert json.loads(answer.body) == {"opened": True, "here": False}
    assert opened == [(None, apps.WORDS), (None, apps.TABLES), (None, apps.SLIDES)]


def test_a_kind_nobody_makes_is_refused(host, opened):
    """It made the window's own kind, so the page got something it never asked
    for and no way to tell."""
    with pytest.raises(Refused) as refused:
        opening.create_new(request(type="template:letter"))

    assert refused.value.status == 400
    assert opened == []


def test_a_window_that_did_not_open_is_not_reported_open(host, monkeypatch):
    """The start window keeps its buttons only if it hears that nothing opened."""
    monkeypatch.setattr(
        hooks, "shell", ScriptedShell(open_window=lambda _doc, _kind=None: False)
    )
    answer = opening.create_new(request(type="word"))

    assert json.loads(answer.body) == {"opened": False, "here": False}


def test_without_windows_another_kind_is_refused(host, opened, monkeypatch):
    """`libera --serve` has one window, and a spreadsheet cannot replace it."""
    monkeypatch.setattr(hooks, "shell", hooks.HeadlessShell())
    with pytest.raises(Refused) as refused:
        opening.create_new(request(type="cell"))

    assert refused.value.status == 409


class FakeWindow:
    def __init__(self):
        self.shown = 0

    def show(self):
        self.shown += 1


@pytest.fixture
def start_windows(monkeypatch):
    made: list = []
    monkeypatch.setattr(windows, "_start_windows", [])
    monkeypatch.setattr(app, "_open_start_window", lambda *a: made.append(a))
    return made


def test_asking_twice_brings_the_start_window_forward(start_windows):
    app.WindowedShell(8080).show_start_window()
    assert start_windows == [(8080,)]

    window = FakeWindow()
    windows.remember_start_window(window)
    app.WindowedShell(8080).show_start_window()

    assert start_windows == [(8080,)]
    assert window.shown == 1


def test_a_start_window_closed_by_hand_is_not_brought_back(start_windows):
    window = FakeWindow()
    windows.remember_start_window(window)

    windows.forget_start_window(window)
    app.WindowedShell(8080).show_start_window()

    assert window.shown == 0
    assert start_windows == [(8080,)]
