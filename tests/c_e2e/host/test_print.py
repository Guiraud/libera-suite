"""Print from the editor, as far as the host's answer.

The bridge says so itself when a print fails, since nothing in the editor waits
for one. Cancelling the save dialog is not a failure: it alerted "could not
print" all the same.
"""

from __future__ import annotations

from support import ScriptedShell

from libera.host import hooks


def print_with_the_dialog_answering(editor_with, monkeypatch, answer) -> list[str]:
    editor = editor_with([])
    monkeypatch.setattr(
        hooks, "shell", ScriptedShell(choose_save_path=lambda *_: answer)
    )
    monkeypatch.setattr("libera.host.desktop.open_externally", lambda _path: True)
    alerts: list[str] = []
    editor.page.on("dialog", lambda d: (alerts.append(d.message), d.dismiss()))

    with editor.answered("save"):
        editor.frame.evaluate("() => window.Asc.editor.asc_Print()")
    # The alert, if any, comes from the answer's callback.
    editor.wait_for_nothing()
    return alerts


def test_a_cancelled_print_says_nothing(editor_with, monkeypatch):
    assert print_with_the_dialog_answering(editor_with, monkeypatch, "") == []


def test_a_print_that_fails_says_so(editor_with, monkeypatch, tmp_path):
    """The other half: a print that cannot happen still alerts. A folder that
    does not exist cannot be written to, and the PDF is made first, so the
    alert comes after the converter: waited for, not slept on."""
    editor = editor_with([])
    nowhere = str(tmp_path / "missing" / "Printed.pdf")
    monkeypatch.setattr(
        hooks, "shell", ScriptedShell(choose_save_path=lambda *_: nowhere)
    )
    monkeypatch.setattr("libera.host.desktop.open_externally", lambda _path: True)

    with editor.page.expect_event("dialog", timeout=60_000) as alert:
        editor.frame.evaluate("() => window.Asc.editor.asc_Print()")
    alert.value.dismiss()

    assert alert.value.message == "Libera Suite could not print this document."
