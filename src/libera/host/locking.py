"""Lock files: telling other programs that a document is open here, and
learning that it is open there.

The format is LibreOffice's, so that each sees the other's locks: a file
`.~lock.NAME#` beside the document, holding one line of five comma-separated
fields -- full name, login, host, local time as `DD.MM.YYYY HH:MM`, profile
URL -- ended by `;` and no newline. Measured from a lock LibreOffice wrote on
2026-10-03. LibreOffice escapes `,`, `;` and `\\` inside a field with a
backslash; that part is from its sources, not observed.

A lock with our login, host and profile is ours. One this process did not take
is left over from a crash, and is taken over rather than obeyed.
"""

from __future__ import annotations

import logging
import os
import re
import socket
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from libera.host import desktop, hooks
from libera.host.session import Session, is_inside, write_atomically
from libera.payload import locate

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

FIELDS = 5
# A backslash before any character keeps it literal; a bare `,` or `;` ends a field.
_FIELD = re.compile(r"((?:\\.|[^,;\\])*)([,;])", re.DOTALL)


@dataclass(frozen=True)
class LockOwner:
    """Who holds a document, as the lock file says."""

    name: str
    login: str
    host: str
    since: str
    profile: str

    def is_us(self) -> bool:
        return (self.login, self.host, self.profile) == (
            desktop.lookup_local_user()[0],
            socket.gethostname(),
            this_profile(),
        )


# Whoever holds a lock nobody can read: not free, because opening the document
# for editing could overwrite their work.
UNKNOWN = LockOwner("someone", "", "", "", "")


def lock_path(document: Path) -> Path:
    return document.with_name(f".~lock.{document.name}#")


def this_profile() -> str:
    """Our counterpart of LibreOffice's profile URL: where our state lives."""
    return locate.get_state_dir().as_uri()


def _escape(field: str) -> str:
    return re.sub(r"([,;\\])", r"\\\1", field)


def _unescape(field: str) -> str:
    return re.sub(r"\\(.)", r"\1", field, flags=re.DOTALL)


def format_owner(owner: LockOwner) -> bytes:
    fields = (owner.name, owner.login, owner.host, owner.since, owner.profile)
    return (",".join(_escape(f) for f in fields) + ";").encode()


def parse_owner(data: bytes) -> LockOwner:
    """The owner a lock file names, or `UNKNOWN` if it cannot be read."""
    try:
        text = data.decode()
    except UnicodeDecodeError:
        return UNKNOWN
    fields = [_unescape(m.group(1)) for m in _FIELD.finditer(text)]
    if len(fields) != FIELDS:
        return UNKNOWN
    return LockOwner(*fields)


def read_owner(document: Path) -> LockOwner | None:
    """Who holds the document, or None when nobody does."""
    try:
        return parse_owner(lock_path(document).read_bytes())
    except FileNotFoundError:
        return None


def _make_owner() -> LockOwner:
    login, name = desktop.lookup_local_user()
    return LockOwner(
        name,
        login,
        socket.gethostname(),
        time.strftime("%d.%m.%Y %H:%M"),
        this_profile(),
    )


def take(document: Path) -> LockOwner | None:
    """Lock the document for us. None when it is ours now; otherwise whoever
    holds it, and their lock is left as it was.

    A folder we cannot write to locks nothing, and stops nothing: refusing to
    open a document because we cannot announce it would be worse than not
    announcing it.
    """
    path = lock_path(document)
    line = format_owner(_make_owner())
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError:
        holder = read_owner(document) or UNKNOWN
        if not holder.is_us():
            return holder
        # ponytail: "ours" is login, host and profile, with no process id, so a
        # second Libera Suite on this account (when the hand-off to the first
        # failed) takes over the first one's lock instead of opening read-only.
        logger.info("taking over our own stale lock on %s", document)
        write_atomically(path, line.decode())
        return None
    except OSError as e:
        logger.warning("could not lock %s: %s", document, e)
        return None
    with os.fdopen(fd, "wb") as f:
        f.write(line)
    return None


def release(document: Path) -> None:
    """Remove our lock on the document. Anyone else's stays."""
    holder = read_owner(document)
    if holder is not None and holder.is_us():
        lock_path(document).unlink(missing_ok=True)


def hold(session: Session, document: Path) -> None:
    """Lock the document this window now shows, and note who else holds it.

    Only for a document in a window: `libera --serve` and the tests open
    documents nobody else could be editing. Not for an untitled document,
    which lives in our own scratch folder.
    """
    if not hooks.shell.windowed or is_inside(session.scratch, document):
        return
    holder = take(document)
    session.locked_by = (
        None if holder is None else f"{holder.name}, since {holder.since}"
    )


def let_go(session: Session) -> None:
    """Release the lock of the document a closing window shows."""
    document = session.read_current_document()
    if document is not None:
        release(document)
