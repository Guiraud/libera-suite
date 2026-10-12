"""What the host has been asked for, and what it could not answer.

The bottom of the package: counters and sets that the endpoints write and
`build_report` reads back, for the regression harness, which also posts the
editor's own photograph of its canvas here. The regression harness reads
that report instead of a log, which is why this is state rather than logging
-- an assertion needs a value.
"""

from __future__ import annotations

import base64
import collections
import json
import threading
from typing import TYPE_CHECKING

from libera.host.server.api import NO_CONTENT, Refused, Request, Response, endpoint

if TYPE_CHECKING:
    from libera.host.session import Session

# AscDesktopEditor calls the page made, by name.
SEEN: dict[str, int] = {}
# Bounded: only `libera --serve` resets it, on a new document, so a process with
# windows added to it for its whole life. The newest are the ones worth keeping.
ERRORS: collections.deque[dict] = collections.deque(maxlen=1000)
MEDIA_SERVED: set[str] = set()
NOT_FOUND: set[str] = set()
# POSTs admitted to a route, by route: what the page asked the host to do.
ASKED: dict[str, int] = {}
NOT_FOUND_CODE = 404

# Every request has a thread, and `+=` on a dict entry is a read and a write.
_COUNTING = threading.Lock()


def count(table: dict[str, int], name: str) -> None:
    with _COUNTING:
        table[name] = table.get(name, 0) + 1


def reset() -> None:
    """Forget what the editor asked for: a new document is starting over."""
    MEDIA_SERVED.clear()
    SEEN.clear()
    ERRORS.clear()


def build_report(session: Session) -> bytes:
    with _COUNTING:
        calls, asked = dict(SEEN), dict(ASKED)
    return json.dumps(
        {
            "calls": calls,
            "errors": list(ERRORS),
            # Document media fails *silently* when the host gets it wrong: no
            # request, no console error, just a missing picture. Report what was
            # served so the check can compare it against what the document holds.
            "media_expected": sorted(p.name for p in session.media.glob("*"))
            if session.media.is_dir()
            else [],
            "media_served": sorted(MEDIA_SERVED),
            "not_found": sorted(NOT_FOUND),
            "routes": asked,
        },
        indent=2,
        sort_keys=True,
    ).encode()


@endpoint("GET", "report")
def serve_report(r: Request) -> Response:
    """The harness's report: what was asked for, and what went missing."""
    return Response(body=build_report(r.session))


@endpoint("POST", "shot")
def receive_shot(r: Request) -> Response:
    """The editor's own canvas, captured in the page and posted here.

    Replaces Chromium's --screenshot, which only fires when
    --virtual-time-budget expires and takes the browser down with it.
    """
    if r.session.shot is None:
        raise Refused(404)
    r.session.shot.write_bytes(base64.b64decode(r.body))
    return NO_CONTENT
