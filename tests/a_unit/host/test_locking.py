"""Lock files: what tells LibreOffice, and another copy of Libera Suite, that a
document is open here -- and tells us that it is open there.

The format is LibreOffice's, measured from a lock it wrote on 2026-10-03 (the
line below): five fields separated by commas, ended by a semicolon, no newline.
"""

from __future__ import annotations

import os
import sys

import pytest

from libera.host import locking
from libera.host.saving import SaveRequest

LIBREOFFICE = (
    b"Stefane Fermigier,fermigier,stefanes-mac-mini.home,03.10.2026 20:20,"
    b"file:///Users/fermigier/Library/Application%20Support/LibreOffice/4;"
)


@pytest.fixture
def here(tmp_path, monkeypatch):
    """This machine, this account and this profile, fixed."""
    monkeypatch.setattr(
        locking.desktop, "lookup_local_user", lambda: ("ada", "Ada Lovelace")
    )
    monkeypatch.setattr(locking.socket, "gethostname", lambda: "engine.local")
    monkeypatch.setattr(locking.locate, "get_state_dir", lambda: tmp_path / "state")
    document = tmp_path / "notes.docx"
    document.write_bytes(b"a document")
    return document


def test_libreoffice_lock_reads_as_libreoffice_wrote_it():
    owner = locking.parse_owner(LIBREOFFICE)

    assert owner.name == "Stefane Fermigier"
    assert (owner.login, owner.host) == ("fermigier", "stefanes-mac-mini.home")
    assert owner.since == "03.10.2026 20:20"
    assert owner.profile.endswith("/LibreOffice/4")


def test_ours_is_written_in_the_same_shape(here):
    assert locking.take(here) is None

    written = locking.lock_path(here).read_bytes()
    assert written.startswith(b"Ada Lovelace,ada,engine.local,")
    assert written.endswith(b"/state;"), "a newline or a missing ';' breaks LibreOffice"
    assert locking.lock_path(here).name == ".~lock.notes.docx#"


def test_a_comma_in_a_name_survives_the_round_trip(here, monkeypatch):
    monkeypatch.setattr(
        locking.desktop, "lookup_local_user", lambda: ("ada", "Lovelace, Ada; Countess")
    )
    locking.take(here)

    assert locking.read_owner(here).name == "Lovelace, Ada; Countess"


def test_a_document_open_in_libreoffice_is_not_taken(here):
    locking.lock_path(here).write_bytes(LIBREOFFICE)

    owner = locking.take(here)

    assert owner is not None
    assert owner.name == "Stefane Fermigier"
    assert locking.lock_path(here).read_bytes() == LIBREOFFICE, "their lock was touched"


def test_our_own_lock_left_by_a_crash_is_taken_over(here):
    stale = b"Ada Lovelace,ada,engine.local,01.01.2026 09:00," + (
        locking.this_profile().encode() + b";"
    )
    locking.lock_path(here).write_bytes(stale)

    assert locking.take(here) is None
    assert b"01.01.2026" not in locking.lock_path(here).read_bytes()


def test_closing_removes_our_lock_and_never_theirs(here, tmp_path):
    locking.take(here)
    locking.release(here)
    assert not locking.lock_path(here).exists()

    other = tmp_path / "theirs.docx"
    locking.lock_path(other).write_bytes(LIBREOFFICE)
    locking.release(other)
    assert locking.lock_path(other).read_bytes() == LIBREOFFICE


def test_a_lock_that_cannot_be_read_counts_as_someone_else(here):
    """Unknown is not free: opening it for editing could overwrite their work."""
    locking.lock_path(here).write_bytes(b"\xff\xfe garbage")

    assert locking.take(here) is not None


@pytest.mark.skipif(
    hasattr(os, "geteuid") and os.geteuid() == 0,
    reason="root writes into a read-only folder, and `lb linux test` runs as root",
)
@pytest.mark.skipif(
    sys.platform == "win32",
    reason="Windows ignores a folder's mode bits: only an ACL makes it read-only",
)
def test_a_folder_we_cannot_write_to_does_not_stop_the_document_opening(here):
    """None is also what take() returns when it wrote the lock, so the file
    is looked for too: as root, the write succeeded and this still passed."""
    here.parent.chmod(0o555)
    try:
        assert locking.take(here) is None
        assert not locking.lock_path(here).exists()
    finally:
        here.parent.chmod(0o755)


# --- what a window does with locks


@pytest.fixture
def window(here, tmp_path, monkeypatch):
    """A session shown in a window, with `here` (notes.docx) open in it."""
    from support import ScriptedShell

    from libera.host import hooks
    from libera.host.session import Session

    monkeypatch.setattr(hooks, "shell", ScriptedShell())
    session = Session(payload=tmp_path / "payload", work=tmp_path / "sessions" / "1")
    session.work.mkdir(parents=True)
    session.write_current_document(here)
    return session


def test_a_window_locks_its_document_and_closing_it_unlocks(window, here):
    from libera.host import app

    locking.hold(window, here)
    assert locking.read_owner(here).name == "Ada Lovelace"
    assert window.locked_by is None

    app.close_session(window)
    assert not locking.lock_path(here).exists()


def test_a_document_open_elsewhere_says_by_whom(window, here):
    locking.lock_path(here).write_bytes(LIBREOFFICE)

    locking.hold(window, here)

    assert window.locked_by == "Stefane Fermigier, since 03.10.2026 20:20"


def test_without_a_window_nothing_is_locked(window, here, monkeypatch):
    """`libera --serve` and the tests open documents nobody else is editing."""
    from libera.host import hooks

    monkeypatch.setattr(hooks, "shell", hooks.HeadlessShell())

    locking.hold(window, here)

    assert not locking.lock_path(here).exists()


def test_an_untitled_document_is_not_locked(window):
    window.scratch.mkdir(parents=True)
    untitled = window.scratch / "Untitled.docx"
    untitled.write_bytes(b"a blank")

    locking.hold(window, untitled)

    assert not locking.lock_path(untitled).exists()


@pytest.fixture
def exported(monkeypatch):
    """x2t, stood in for: every export writes the same bytes."""
    from libera.host import saving

    def export(_session, staged, _fmt, _source):
        staged.write_bytes(b"the saved document")
        return True

    monkeypatch.setattr(saving.convert, "export", export)


def test_save_as_moves_the_lock_to_the_new_file(
    window, here, tmp_path, monkeypatch, exported
):
    from support import ScriptedShell

    from libera.host import hooks, saving

    copy = tmp_path / "copy.docx"
    monkeypatch.setattr(
        hooks, "shell", ScriptedShell(choose_save_path=lambda *_: str(copy))
    )
    locking.hold(window, here)

    saving.save_document(window, SaveRequest(file_type=65, save_as=True))

    assert copy.read_bytes() == b"the saved document"
    assert not locking.lock_path(here).exists(), "the old file stayed locked"
    assert locking.read_owner(copy).name == "Ada Lovelace"


def test_saving_a_document_someone_else_holds_asks_where(
    window, here, tmp_path, monkeypatch, exported
):
    """Their file is theirs: a plain Save would write over what they are editing."""
    from support import ScriptedShell

    from libera.host import hooks, saving

    locking.lock_path(here).write_bytes(LIBREOFFICE)
    locking.hold(window, here)
    asked: list = []
    copy = tmp_path / "mine.docx"
    monkeypatch.setattr(
        hooks,
        "shell",
        ScriptedShell(choose_save_path=lambda *a: asked.append(a) or str(copy)),
    )

    saving.save_document(window, SaveRequest())

    assert asked, "a plain Save went to their file without asking"
    assert here.read_bytes() == b"a document"
    assert copy.read_bytes() == b"the saved document"
    assert window.locked_by is None, "the copy is ours, and free"


def test_save_as_onto_a_file_someone_else_holds_is_refused(
    window, here, tmp_path, monkeypatch, exported
):
    from support import ScriptedShell

    from libera.host import hooks, saving

    theirs = tmp_path / "theirs.docx"
    theirs.write_bytes(b"their document")
    locking.lock_path(theirs).write_bytes(LIBREOFFICE)
    told: list = []
    monkeypatch.setattr(
        hooks,
        "shell",
        ScriptedShell(
            choose_save_path=lambda *_: str(theirs),
            tell=lambda heading, detail: told.append((heading, detail)),
        ),
    )

    result = saving.save_document(window, SaveRequest(save_as=True))

    assert theirs.read_bytes() == b"their document"
    assert result["error"] == saving.SaveOutcome.DECLINED
    assert "Stefane Fermigier" in told[0][1]
