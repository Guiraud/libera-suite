"""What the page does with a keystroke the menu bar also owns.

Cmd-N has been wrong twice: once making two windows because the page acted as
well as the menu, once making none because the page claimed the key instead of
merely declining it. Both were in this JavaScript, and a browser can drive it.

What a browser cannot do is *be* AppKit. These tests cover the page's half of
the contract -- given what the host says the menu owns, does the page act or
not -- and nothing here says whether the menu then fires. That half needs a
real application; see notes/04-plan.md.

The server runs in-process rather than as `libera --serve`, because the whole
point is to vary what the host tells the page, and a subprocess with no window
always reports an empty list.
"""

from __future__ import annotations

import sys

import pytest

from libera.host import hooks, server, shortcuts


def test_the_page_yields_a_key_the_menu_bar_owns(editor_with):
    """Cmd-N with a menu bar: AppKit's job, so the page must not also ask."""
    editor = editor_with([s.as_json() for s in shortcuts.PAGE_YIELDS])
    editor.press("Meta+n")
    editor.wait_for_nothing()

    # Nothing asked is also what a key that never arrived looks like.
    assert editor.saw("n") > 0, "the keystroke reached no frame"
    assert editor.asked_for("new") == 0


@pytest.mark.xfail(
    not sys.platform.startswith("darwin"),
    strict=True,
    reason=(
        "Meta+n is the editor's own key on a Mac only. Measured in the"
        " container: it reaches the editor and no `new` request follows. Off a"
        " Mac the key is Ctrl-N, which the page runs itself: see"
        " test_ctrl_keys_run_the_file_menu below. strict, so this tells us if"
        " the editor ever starts handling Meta+n there."
    ),
)
def test_the_page_handles_the_key_when_nothing_else_will(editor_with):
    """The same key with no menu bar -- `libera --serve` -- must work.

    On macOS this is the real path for a serve-only run.
    """
    editor = editor_with([])
    editor.press("Meta+n")
    # Create New offers a choice now, with the editor's own kind in focus, so
    # Return is what makes the document the key used to make at once.
    editor.page.wait_for_selector("#libera-create-new button:focus")
    with editor.answered("new"):
        editor.page.keyboard.press("Enter")

    assert editor.asked_for("new") == 1


def test_the_page_declines_the_key_without_claiming_it(editor_with):
    """Declining and swallowing are one line apart and opposite.

    stopImmediatePropagation stops the editor's own handler, which is wanted.
    preventDefault marks the event handled, WKWebView reports that to AppKit as
    "the page took it", and the menu item does not fire either. Both together
    is the obvious thing to write, and it makes Cmd-N do nothing at all.
    """
    editor = editor_with([s.as_json() for s in shortcuts.PAGE_YIELDS])
    editor.press("Meta+n")
    editor.wait_for_nothing()

    assert editor.saw("n") > 0, "the keystroke reached no frame"
    assert editor.asked_for("new") == 0, "the page acted on a key the menu owns"
    assert not editor.claimed("n"), (
        "the page claimed the key, so the menu will not fire"
    )


@pytest.fixture
def running_page_keys(monkeypatch):
    """What the host tells the page off macOS, on any platform the suite runs
    on, and a shell that records what each key asked of it."""
    from support import ScriptedShell

    monkeypatch.setattr(
        server.editor,
        "list_page_keys",
        lambda: {n: k.as_json() for n, k in shortcuts.PAGE_RUNS.items()},
    )
    asked: list[str] = []
    shell = ScriptedShell(
        open_window=lambda document, app=None: (
            asked.append(f"new {document} {app}") or True
        ),
        choose_open_path=lambda kind: asked.append(f"open {kind}"),
        close_window=lambda session: asked.append(f"close {session.id}"),
    )
    return shell, asked


@pytest.mark.parametrize(
    ("combination", "expected"),
    [
        # The request the key makes, and what the shell is then asked to do.
        ("Control+n", ("new", "new None None")),
        ("Control+o", ("open-document", "open documents")),
        ("Control+w", ("close", "close 0")),
    ],
)
def test_ctrl_keys_run_the_file_menu(
    editor_with, monkeypatch, running_page_keys, combination, expected
):
    """Off macOS no menu bar has these keys and the editor handles none of
    them: Ctrl-N did nothing on Linux. The page runs File > New, Open and
    Close itself, once per keystroke."""
    route, action = expected
    shell, asked = running_page_keys
    editor = editor_with([])
    monkeypatch.setattr(hooks, "shell", shell)

    with editor.answered(route):
        editor.press(combination)

    assert asked == [action]


def test_a_key_not_in_the_table_is_left_to_the_editor(
    editor_with, monkeypatch, running_page_keys
):
    """Matched exactly, Shift included: Ctrl-Shift-N is not Ctrl-N."""
    shell, asked = running_page_keys
    editor = editor_with([])
    monkeypatch.setattr(hooks, "shell", shell)

    editor.press("Control+Shift+n")
    editor.wait_for_nothing()

    assert asked == []


def test_ctrl_shift_s_is_the_editors_own_save_as(editor_with, monkeypatch):
    """Not in PAGE_RUNS because the editor handles it: offline, its shortcut
    runs asc_DownloadAs, which reaches the host as a Save As."""
    from support import ScriptedShell

    editor = editor_with([])
    asked: list[str] = []
    monkeypatch.setattr(
        hooks,
        "shell",
        ScriptedShell(
            choose_save_path=lambda suggested, _formats, _start: asked.append(suggested)
        ),
    )

    with editor.answered("save"):
        editor.press("Control+Shift+s")

    assert len(asked) == 1


def test_the_page_yields_close_and_quit_without_claiming_them(editor_with):
    """Cmd-W and Cmd-Q stopped reaching the menu once a slideshow had ended,
    in WebKit. Yielding keeps every page handler off them, and must not claim
    them, or the menu would not fire at all. Chromium cannot show the WebKit
    failure itself, only that the page leaves the keys to the menu."""
    editor = editor_with([s.as_json() for s in shortcuts.PAGE_YIELDS])
    for key in ("w", "q"):
        editor.press(f"Meta+{key}")

        assert editor.saw(key) > 0, "the keystroke reached no frame"
        assert not editor.claimed(key), "the page claimed it: the menu will not fire"
