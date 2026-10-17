"""Startup, stage by stage, for `build/src/libera_build/bench.py`.

Off unless LIBERA_STARTUP_TRACE names a file; then each stage appends one line,
the wall-clock time and its name, the first time it is reached; with `again`,
every time, for the stages a document opened later goes through too.
Wall-clock, not monotonic, because the benchmark compares them with the moment
it started the process, which is in another process. See notes/21-startup-and-size.md.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

_PATH = os.environ.get("LIBERA_STARTUP_TRACE")
_REACHED: set[str] = set()


def mark(stage: str, *, again: bool = False) -> None:
    if not _PATH or (stage in _REACHED and not again):
        return
    _REACHED.add(stage)
    with Path(_PATH).open("a", encoding="utf-8") as trace:
        trace.write(f"{time.time():.3f} {stage}\n")
