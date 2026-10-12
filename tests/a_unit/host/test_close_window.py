"""Closing a window from inside the page: the editor's own File > Close."""

from __future__ import annotations

import pytest
from support import ScriptedShell

from libera.host import hooks
from libera.host.server import document
from libera.host.server.api import Request
from libera.host.session import Session


def test_the_page_asks_for_its_own_window_to_close(tmp_path, monkeypatch):
    closed: list[Session] = []
    monkeypatch.setattr(hooks, "shell", ScriptedShell(close_window=closed.append))
    asking = Session(payload=tmp_path / "payload", work=tmp_path / "1")

    answer = document.close_window(Request(asking))

    assert answer.status == 204
    assert closed == [asking]


@pytest.mark.skipif("sys.platform != 'darwin'")
def test_on_macos_closing_asks_first(monkeypatch):
    """performClose: goes through the window's delegate, which asks about
    unsaved changes; NSWindow.close, what pywebview's destroy() calls, does
    not ask at all."""
    from types import SimpleNamespace

    from libera.host.window import macos

    sent: list[str] = []
    native = SimpleNamespace(
        performClose_=lambda _sender: sent.append("performClose:"),
        close=lambda: sent.append("close"),
    )
    monkeypatch.setattr(macos.AppHelper, "callAfter", lambda f, *a: f(*a))

    macos.close_window(SimpleNamespace(native=native))

    assert sent == ["performClose:"]
