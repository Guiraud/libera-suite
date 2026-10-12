"""Opening a document into a session, and offering back what a crash left."""

from __future__ import annotations

import json
import logging
import pathlib
import shutil

from libera.host import convert, hooks, locking, recents
from libera.host.session import SESSIONS, Session

logger = logging.getLogger(__name__)


def open_document(session: Session, document: pathlib.Path) -> None:
    """Prepare the session for a document, converting it for the editor.

    Converting throws away the previous session, so this is the only moment at
    which edits that never reached the file can still be rescued.
    """
    stale = find_recoverable(session, document)
    if stale and hooks.shell.ask_to_recover(document):
        if stale != session.work:
            # The edits are in another window's old session; adopt them.
            shutil.rmtree(session.doc, ignore_errors=True)
            shutil.move(str(stale / "doc"), str(session.doc))
            shutil.copyfile(stale / "unsaved.json", session.unsaved_marker)
            shutil.rmtree(stale, ignore_errors=True)
        logger.info("recovered unsaved changes to %s", document)
        session.write_current_document(document)
        recents.remember_recent(session, document)
        locking.hold(session, document)
        return
    convert.convert_to_editor_bin(session, document)
    if stale and stale != session.work:
        # "Open Saved Version" declines the edits wherever they were. In this
        # session's directory the conversion has just replaced them; left in
        # another, they were offered again on every open.
        (stale / "unsaved.json").unlink(missing_ok=True)
    session.write_current_document(document)
    session.unsaved_marker.unlink(missing_ok=True)
    recents.remember_recent(session, document)
    locking.hold(session, document)


def has_unsaved_edits(found: Session, document: pathlib.Path) -> bool:
    """Does this session's directory hold unsaved edits to that document?"""
    marker = found.unsaved_marker
    if not (marker.is_file() and found.editor_bin.is_file() and found.change_log):
        return False
    try:
        return json.loads(marker.read_text(encoding="utf-8")).get("document") == str(
            document
        )
    except (ValueError, OSError) as e:
        # Answering False here means "nothing to recover", and the edits go
        # without the user being asked. That is the right answer for a marker
        # we cannot read -- there is nothing to offer them *about* -- but it
        # is never a right answer to give quietly.
        logger.warning("unreadable recovery marker at %s: %s", marker, e)
        return False


def find_recoverable(session: Session, document: pathlib.Path) -> pathlib.Path | None:
    """The session directory holding unsaved edits to this document, if any.

    Any of them, not just this window's: with a window per document the
    session that crashed is rarely the one being opened now.

    Except another window's. Its edits are not a crash's, they are live, and
    recovering them moved its files away and deleted its directory while the
    window was still writing to it -- which is what opening a document twice
    did.
    """
    here = session.work
    live = {found.work for found in list(SESSIONS.values())}
    others = (
        d
        for d in sorted(here.parent.glob("*"))
        if d.is_dir() and d != here and d not in live
    )
    for work in (here, *others):
        # Each read as a session, because where its files are is Session's to say.
        if has_unsaved_edits(Session(payload=session.payload, work=work), document):
            return work
    return None
