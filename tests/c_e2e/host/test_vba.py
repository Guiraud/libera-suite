"""A document's VBA survives an edit and a save.

Libera runs no macros, and must not take them out of the file either. Saving
replays the change log through sdkjs before x2t writes the package, so a
plain save with nothing changed proves less than one after typing: the
integration tier has that one.
"""

from __future__ import annotations

import shutil
import zipfile
from typing import TYPE_CHECKING

import pytest
from support import repo_root

if TYPE_CHECKING:
    import pathlib

DATA = "tests/b_integration/host/data"
# The editor batches its edits: typing reaches the host within a few seconds,
# not on the keystroke. Measured at under five.
FLUSH = 15_000
# Typed, then looked for in the saved file: a word no package holds already.
TYPED = "zqvz"


@pytest.mark.parametrize("name", ["SimpleMacro.docm", "SimpleMacro.xlsm"])
def test_an_edited_document_keeps_its_vba(
    editor_with, tmp_path: pathlib.Path, name: str
):
    document = tmp_path / name
    shutil.copy(repo_root() / DATA / name, document)
    vba = _read_vba(document)
    assert TYPED.encode() not in _read_text(document)
    editor = editor_with([], document=document)

    editor.press(TYPED[0])
    editor.page.keyboard.type(TYPED[1:])
    # Enter: a spreadsheet sends nothing until the cell is committed.
    editor.page.keyboard.press("Enter")
    editor.page.wait_for_function(
        "() => window.__libera_seen.has('LocalFileSaveChanges')", timeout=FLUSH
    )
    with editor.answered("save"):
        editor.press("ControlOrMeta+s")

    assert TYPED.encode() in _read_text(document)
    assert _read_vba(document) == vba


def _read_vba(document: pathlib.Path) -> bytes:
    with zipfile.ZipFile(document) as package:
        (name,) = (n for n in package.namelist() if n.endswith("/vbaProject.bin"))
        return package.read(name)


def _read_text(document: pathlib.Path) -> bytes:
    """Where the typing lands: the body of a document, a workbook's strings."""
    with zipfile.ZipFile(document) as package:
        parts = ("word/document.xml", "xl/sharedStrings.xml")
        return b"".join(package.read(n) for n in parts if n in package.namelist())
