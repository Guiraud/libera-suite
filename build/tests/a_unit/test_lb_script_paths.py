"""Every path a build script names beside itself exists.

The scripts find each other through $HERE (their own directory) and $BUILD
(build/). When build/ was reorganised, build.sh went on sourcing
$HERE/msvc-env.sh, which had moved to windows/: every build would have stopped
at its first line, and nothing that ran after the move ran build.sh. This
reads the paths instead of running the scripts.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest
from libera_build.repo import REPO

if TYPE_CHECKING:
    from pathlib import Path

BUILD = REPO / "build"
SCRIPTS = sorted(
    p
    for d in ("engine", "macos", "windows", "install")
    for p in (BUILD / d).glob("*.sh")
)
# $HERE/x or $BUILD/x, up to the first quote, space, variable or glob.
NAMED = re.compile(r"\$(HERE|BUILD)/([A-Za-z0-9_./-]+)")
# Written by a build rather than committed.
MADE = ("out/",)


def named_paths(script: Path) -> list[Path]:
    found = []
    for anchor, rest in NAMED.findall(script.read_text(encoding="utf-8")):
        if rest.startswith(MADE) or rest.endswith("-") or rest.startswith(".."):
            continue
        base = script.parent if anchor == "HERE" else BUILD
        found.append(base / rest.rstrip("/"))
    return found


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: str(p.relative_to(BUILD)))
def test_what_a_script_names_beside_it_is_there(script):
    missing = [str(p.relative_to(BUILD)) for p in named_paths(script) if not p.exists()]
    assert missing == []


def test_the_check_sees_the_paths_it_is_for():
    """If the pattern found nothing, every test above would pass vacuously."""
    build_sh = BUILD / "engine" / "build.sh"
    assert BUILD / "windows" / "msvc-env.sh" in named_paths(build_sh)
