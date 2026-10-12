"""Running a command on this machine.

Here, unlike on a builder over ssh, an exit status means what it says, so
these are allowed to believe it.
"""

from __future__ import annotations

import shlex
import subprocess
from typing import TYPE_CHECKING

from libera_build.report import RefusedError, say

if TYPE_CHECKING:
    from pathlib import Path


def capture(
    argv: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None
) -> tuple[int, str]:
    """Run a command to its end, and return its status and everything it said."""
    done = subprocess.run(
        argv, cwd=cwd, env=env, capture_output=True, text=True, check=False
    )
    return done.returncode, done.stdout + done.stderr


def run_here(
    argv: list[str], what: str, *, cwd: Path, env: dict[str, str] | None = None
) -> None:
    """Run a command, its output streaming to ours, and refuse if it fails,
    naming the phase it was for."""
    say(f"    {' '.join(argv)}")
    status = subprocess.run(argv, cwd=cwd, env=env, check=False).returncode
    if status != 0:
        msg = f"{what}: `{' '.join(argv)}` failed ({status})."
        raise RefusedError(msg)


def run_quietly(
    argv: list[str],
    what: str,
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> None:
    """Run a command whose output matters only if it fails, and refuse then
    with that output: check=True would raise a CalledProcessError, whose
    traceback carries the command line and drops what the tool said."""
    status, out = capture(argv, cwd=cwd, env=env)
    if status != 0:
        msg = f"{what}: `{shlex.join(argv)}` failed ({status})\n{out.strip()}"
        raise RefusedError(msg)
