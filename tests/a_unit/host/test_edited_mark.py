"""A window shows its document has unsaved edits, as Pages and Keynote do.

The editor reports its dirty flag on every change; the host keeps it for
recovery and passes it to the window: on macOS the dot in the close button and
"Edited" after the title, elsewhere a leading * as gedit and Notepad show.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from support import ScriptedShell

from libera.host import hooks
from libera.host.server import document
from libera.host.server.api import Request
from libera.host.session import Session
from libera.host.window import portable


def test_the_editors_dirty_flag_reaches_the_window(tmp_path, monkeypatch):
    shown: list[tuple[str, bool]] = []
    monkeypatch.setattr(
        hooks,
        "shell",
        ScriptedShell(
            show_edited=lambda session, edited: shown.append((session.id, edited))
        ),
    )
    session = Session(payload=tmp_path / "payload", work=tmp_path / "1")
    session.work.mkdir(parents=True)

    for modified in (True, False):
        document.record_modified(
            Request(session, body=json.dumps({"modified": modified}).encode())
        )

    assert shown == [("1", True), ("1", False)]


class TitledWindow:
    """A pywebview window, reduced to its title."""

    def __init__(self, title: str) -> None:
        self.title = title

    def set_title(self, title: str) -> None:
        self.title = title


def test_linux_and_windows_mark_the_title_with_a_star():
    window = TitledWindow("Report.docx — Libera Words")

    portable.show_edited(window, True)
    portable.show_edited(window, True)
    assert window.title == "*Report.docx — Libera Words", "one star, however often"

    portable.show_edited(window, False)
    assert window.title == "Report.docx — Libera Words"


@pytest.mark.skipif("sys.platform != 'darwin'")
def test_macos_shows_the_dot_and_edited(monkeypatch):
    from libera.host.window import macos

    sent: list = []
    native = SimpleNamespace(
        setDocumentEdited_=lambda v: sent.append(("dot", v)),
        setSubtitle_=lambda v: sent.append(("subtitle", v)),
    )
    monkeypatch.setattr(macos.AppHelper, "callAfter", lambda f, *a: f(*a))

    macos.show_edited(SimpleNamespace(native=native), True)
    macos.show_edited(SimpleNamespace(native=native), False)

    assert sent == [
        ("dot", True),
        ("subtitle", "Edited"),
        ("dot", False),
        ("subtitle", ""),
    ]
