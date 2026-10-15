"""One Libera Suite per user: a second launch hands its documents to the first.

Double-clicking a second document starts a second process. That process
cannot share the first one's port, so it would come up on another origin,
which is another localStorage, which is an editor that has forgotten
its theme, its units and every tip it has shown. It would also be a second
icon in the taskbar for what the user thinks of as one application.

So the running instance says where it is, in `instance.json` under the state
directory, and a later `libera FILE...` posts the paths to it and exits.

Saying where it is comes late -- the window has to exist first -- so two
launches at once both find no instance to hand off to: Explorer starts a process
per file of a multi-selection. One instance at a time is therefore claimed
first, with a lock the operating system holds for the process and drops
when it ends, however it ends. The others wait for the claimant to say where
it is, and hand off to it. Two instances once shared a session directory, and
each swept away the other's live sessions.

The file holds the instance's token, which is also the key every request to
its server needs (see `server.admission`): the windows have it in their URLs,
and a second launch reads it here. The server is on 127.0.0.1, which any
process on the machine and any web page the user visits can reach; only a
process running as this user can read the file, which `write_atomically`
creates readable by its owner alone.
"""

from __future__ import annotations

import contextlib
import ctypes
import json
import logging
import os
import secrets
import sys
import time
import urllib.request
from typing import IO, TYPE_CHECKING

from libera.host.session import write_atomically
from libera.payload import locate

if sys.platform == "win32":
    import msvcrt
else:
    import fcntl

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

# Long enough for a busy instance to answer, short enough that a stale file
# (left by a crash, with nothing listening on that port now) costs a user
# double-clicking a document no noticeable wait.
HAND_OFF_TIMEOUT = 3.0

# How long a launch that lost the claim waits for the claimant to say where
# it is: as long as a first document takes to convert, and a dialog about it
# to be answered.
CLAIM_WAIT = 60.0
CLAIM_POLL = 0.25

TOKEN = secrets.token_urlsafe(32)


def get_path() -> Path:
    return locate.get_state_dir() / "instance.json"


def announce(port: int) -> None:
    """Say where this instance is. Called once the server is listening."""
    target = get_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    write_atomically(
        target, json.dumps({"port": port, "token": TOKEN, "pid": os.getpid()})
    )
    logger.info("instance: announced on port %d", port)


class BusyError(RuntimeError):
    """Another launch holds the claim and has not said where it is."""


def claim() -> IO[bytes] | None:
    """The claim to be the instance, held for as long as the file stays open;
    None when another process holds it."""
    path = get_path().with_name("instance.lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    held = path.open("a+b")
    try:
        _lock(held)
    except OSError:
        held.close()
        return None
    return held


def _lock(held: IO[bytes]) -> None:
    """Lock the file without waiting, or raise OSError."""
    if sys.platform == "win32":
        # The first byte, whatever the position: every process must ask for
        # the same one.
        held.seek(0)
        msvcrt.locking(held.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        fcntl.flock(held.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def become(documents: list[Path]) -> IO[bytes] | None:
    """The claim, for this process to run as the instance; or None, once the
    documents are with the instance that has it.

    Raises BusyError when the claimant has neither said where it is nor ended
    within CLAIM_WAIT.
    """
    deadline = time.monotonic() + CLAIM_WAIT
    while (held := claim()) is None:
        if hand_off(documents):
            return None
        if time.monotonic() > deadline:
            msg = "another Libera Suite is starting and has not answered; try again"
            raise BusyError(msg)
        time.sleep(CLAIM_POLL)
    return held


def withdraw() -> None:
    """Remove the announcement, if it is still ours. Called on the way out.

    Only ours: a second instance that could not reach this one (it was busy
    starting) announces itself over the top. Whichever exits first must not
    take the other's announcement with it.
    """
    with contextlib.suppress(OSError, ValueError):
        if json.loads(get_path().read_text(encoding="utf-8")).get("token") == TOKEN:
            get_path().unlink()


def hand_off(documents: list[Path]) -> bool:
    """Give the documents to a running instance. True means it took them.

    False means there is none to take them -- no announcement, or one that
    nothing answers -- and the caller starts the application itself. With no
    documents the running instance puts its start window up, which is what
    clicking the icon of an application that is already open does elsewhere.
    """
    try:
        known = json.loads(get_path().read_text(encoding="utf-8"))
        port, token = int(known["port"]), str(known["token"])
    except (OSError, ValueError, KeyError, TypeError):
        return False

    _allow_foreground()
    body = json.dumps({"documents": [str(d) for d in documents]})
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/__host__/hand-off?key={token}",
        data=body.encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=HAND_OFF_TIMEOUT) as answer:
            took = json.loads(answer.read()).get("opened") is True
    except (OSError, ValueError) as e:
        logger.info("instance: none answering on port %d (%s)", port, e)
        return False
    logger.info("instance: handed %d document(s) to port %d", len(documents), port)
    return took


def _allow_foreground() -> None:
    """Let the running instance bring its new window to the front.

    Windows gives foreground rights to the process the user just started --
    this one -- and refuses them to a background process that asks for them,
    so a window the first instance opens would otherwise appear behind
    whatever was in front, with a flashing taskbar button. ASFW_ANY hands the
    right on. Elsewhere there is nothing to hand.
    """
    # A block, not an early return: see desktop._start.
    if sys.platform == "win32":
        asfw_any = -1
        with contextlib.suppress(OSError, AttributeError):
            ctypes.windll.user32.AllowSetForegroundWindow(asfw_any)
