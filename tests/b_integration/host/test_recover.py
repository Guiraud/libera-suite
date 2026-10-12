"""Recovering from an editor that threw.

An uncaught exception leaves the editor's state a guess, and the window looks
alive while doing nothing. The host offers a reload; this is the half of that
which can lose work, so it is the half worth testing.

The editor works on Editor.bin plus a log of changes it streams as you type. A
reload hands it Editor.bin alone -- the document as it was opened -- so the
edits have to be folded into the base first, or reloading silently undoes
everything since the file was opened.

Whether a reload is offered at all needs no converter, and is in
tests/a_unit/host/test_editor_error.py.
"""

from __future__ import annotations

import re
import zipfile
from typing import TYPE_CHECKING

from libera.host import window
from libera.host.saving import SaveRequest, save_document

if TYPE_CHECKING:
    from libera.host.session import Session


def a_change(host: Session, raw: str) -> None:
    """What the editor streams as someone types."""
    host.change_log.record(raw, None, 1)


def test_folding_with_nothing_to_fold_is_a_no_op(opened: Session):
    before = opened.editor_bin.read_bytes()
    window.fold_changes_in(opened)
    assert opened.editor_bin.read_bytes() == before


def test_folding_rebuilds_editor_bin(opened: Session):
    """A log present means the base is rebuilt through the converter.

    This says the round trip ran and produced something, not that a particular
    edit survived it: the change records here are fabricated, and only the
    editor can make real ones. What a real edit survives is
    test_the_document_survives_the_round_trip below.
    """
    before = opened.editor_bin.read_bytes()
    a_change(opened, "AgAAAA==")

    window.fold_changes_in(opened)

    assert opened.editor_bin.stat().st_size > 0
    assert opened.editor_bin.read_bytes() != before, "the base was not rebuilt"


def test_folding_empties_the_log_it_folded(opened: Session):
    """Otherwise the next save applies them twice."""
    a_change(opened, "AgAAAA==")
    window.fold_changes_in(opened)

    assert not opened.change_log


def test_the_document_survives_the_round_trip(opened: Session):
    """Folding must not cost the document itself.

    Out through x2t and back in is two lossy-looking conversions in a row, on
    a document the user has not saved. If the text is not there afterwards,
    the recovery is worse than the fault it recovers from.
    """
    a_change(opened, "AgAAAA==")
    window.fold_changes_in(opened)

    assert save_document(opened, SaveRequest())["error"] == 0

    text = re.sub(
        r"<[^>]+>",
        "",
        zipfile
        .ZipFile(opened.document)
        .read("word/document.xml")
        .decode("utf-8", "replace"),
    )
    assert "Second paragraph" in text, "the round trip lost the document"
