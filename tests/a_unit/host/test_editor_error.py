"""An editor that threw: whether the host offers a reload, and how often.

What reloading does to the document is tests/b_integration/host/test_recover.py,
which needs a real converter. Whether it is offered at all is a flag on the
session and a question to the shell, and needs neither a payload nor a document:
these were there, and skipped wherever no payload was installed.
"""

from __future__ import annotations

import pytest
from support import ScriptedShell

from libera.host import hooks, server
from libera.host.session import Session


@pytest.fixture
def session(tmp_path) -> Session:
    return Session(payload=tmp_path / "payload", work=tmp_path / "0")


@pytest.fixture
def offered(monkeypatch) -> list[str]:
    """What the shell was asked to offer a reload for."""
    asked: list[str] = []
    monkeypatch.setattr(
        hooks, "shell", ScriptedShell(offer_reload=lambda _s, m: asked.append(m))
    )
    return asked


def test_the_host_stays_quiet_when_the_editor_speaks(session, offered):
    """Two dialogs for one fault is what a user called confusing.

    asc_onError means the editor is already putting its own message up. File >
    Reload stays the way out, and it is always there.
    """
    server.handle_editor_error(
        session, "TypeError: endReporter is not a function", quiet=True
    )

    assert offered == []


def test_an_uncaught_error_the_editor_says_nothing_about_is_offered(session, offered):
    """Nothing else would tell the user anything at all."""
    server.handle_editor_error(session, "TypeError: x is not a function")

    assert offered == ["TypeError: x is not a function"]


def test_an_uncaught_error_is_offered_once(session, offered):
    """An editor that throws once throws again; a dialog per repeat is worse
    than the fault."""
    server.handle_editor_error(session, "TypeError: x is not a function")
    server.handle_editor_error(session, "TypeError: x is not a function")

    assert offered == ["TypeError: x is not a function"]


def test_nothing_is_offered_where_there_is_no_window(session, monkeypatch):
    """`libera --serve` and the harness have no way to ask, and must not
    block waiting to."""
    monkeypatch.setattr(hooks, "shell", hooks.HeadlessShell())

    server.handle_editor_error(session, "TypeError: x is not a function")

    # And it got as far as the shell, which is what declined.
    assert session.reload_offered
