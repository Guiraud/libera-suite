"""Note each moment a process's window changes on screen, on macOS.

    python build/macos/watch-window.py PID TRACE [--new]

Appends "<time> screen" to TRACE whenever the process's largest window differs
from the frame before by more than 0.1% of its pixels, and returns when the
process has ended. With --new, only a window that was not on screen when it
started, and TRACE is created once those are known: a second watcher, started
before a running process is asked to open another document, watches that
document's window. A blinking caret is less than that, and so is the editor's
loading spinner.

`lb bench` reads it to say when a document has finished appearing, which the
editor's own "ready" precedes by a second or more: at that moment the window
still says "Loading document", and the toolbar is greyed out for half a second
after the text shows. Needs pyobjc's Quartz, which pywebview brings on macOS,
so it runs with the checkout's interpreter, not inside `lb`.
"""

from __future__ import annotations

import os
import pathlib
import sys
import time

import Quartz

# Every 7th pixel, green only: enough to see a toolbar fill or a page draw,
# and cheap enough not to slow what it is watching.
STRIDE = 4 * 7
CHANGED = 0.001


def find_window(pid: int, before: set[int]) -> int | None:
    own = [w for w in list_windows(pid) if w["kCGWindowNumber"] not in before]
    if not own:
        return None
    return max(own, key=_area)["kCGWindowNumber"]


def list_windows(pid: int) -> list[dict]:
    shown = Quartz.CGWindowListCopyWindowInfo(
        Quartz.kCGWindowListOptionOnScreenOnly, Quartz.kCGNullWindowID
    )
    return [
        w
        for w in shown or []
        if w["kCGWindowOwnerPID"] == pid and w.get("kCGWindowLayer") == 0
    ]


def _area(window: dict) -> float:
    return window["kCGWindowBounds"]["Width"] * window["kCGWindowBounds"]["Height"]


def grab(window: int) -> bytes | None:
    image = Quartz.CGWindowListCreateImage(
        Quartz.CGRectNull,
        Quartz.kCGWindowListOptionIncludingWindow,
        window,
        Quartz.kCGWindowImageBoundsIgnoreFraming
        | Quartz.kCGWindowImageNominalResolution,
    )
    if image is None:
        return None
    data = Quartz.CGDataProviderCopyData(Quartz.CGImageGetDataProvider(image))
    return bytes(data)[1::STRIDE]


def is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def main(pid: int, trace: str, *, new: bool) -> None:
    window, before = None, None
    already = {w["kCGWindowNumber"] for w in list_windows(pid)} if new else set()
    with pathlib.Path(trace).open("a", encoding="utf-8") as out:
        while is_running(pid):
            at = time.time()
            window = window or find_window(pid, already)
            frame = grab(window) if window else None
            if frame is not None:
                if before is None or len(frame) != len(before):
                    changed = True
                else:
                    differ = sum(a != b for a, b in zip(frame, before, strict=True))
                    changed = differ > len(frame) * CHANGED
                if changed:
                    out.write(f"{at} screen\n")
                    out.flush()
                before = frame
            time.sleep(0.03)


if __name__ == "__main__":
    main(int(sys.argv[1]), sys.argv[2], new="--new" in sys.argv[3:])
