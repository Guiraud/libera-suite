"""The editor's own File menu offers Save As, as a desktop editor's does.

The editor shows Save As, where a web editor shows Download As, when it takes
itself for an offline desktop application. It decides that once, from
asc_isOffline(), when its permissions arrive. Over http only the SDK's desktop
half, sdk-all.js, said yes, and it loads by a <script> tag that raced the
permissions: Chromium lost every time, and WebKit -- the application's own
window -- whenever sdk-all.js was slow, which is how the menu lost Save As for
a user. The bridge now answers yes from the start.
"""

from __future__ import annotations

import pytest

SAVE_AS, DOWNLOAD_AS = "fm-btn-save-desktop", "fm-btn-download"


def visible_file_menu(editor) -> list[str]:
    editor.frame.click("#file")
    editor.frame.wait_for_selector("#file-menu-panel", state="visible")
    return editor.frame.eval_on_selector_all(
        '#file-menu-panel [id^="fm-btn-"]',
        "items => items.filter((b) => b.offsetParent !== null).map((b) => b.id)",
    )


@pytest.mark.parametrize("name", ["sample.docx", "list.csv"])
def test_the_file_menu_offers_save_as_not_download_as(editor_with, tmp_path, name):
    document = None
    if name.endswith(".csv"):
        document = tmp_path / name
        document.write_text("Name,Town\nÉlodie,Besançon\n", encoding="utf-8")

    items = visible_file_menu(editor_with([], document))

    assert SAVE_AS in items, f"no Save As in {items}"
    assert DOWNLOAD_AS not in items


def test_file_close_closes_the_window(editor_with, monkeypatch):
    """The editor's own File > Close sends editor:event file:close, which the
    bridge ignored: the menu hid itself, as Back does, and the window stayed.
    It reaches the host now, which closes the window the way its close button
    does, asking first about unsaved changes."""
    from support import ScriptedShell

    from libera.host import hooks

    editor = editor_with([])
    closed: list[str] = []
    monkeypatch.setattr(
        hooks, "shell", ScriptedShell(close_window=lambda s: closed.append(s.id))
    )

    visible_file_menu(editor)
    with editor.answered("close"):
        editor.frame.click("#fm-btn-exit")

    assert closed == ["0"]
