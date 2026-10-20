"""What install.sh installs on Linux arm64, which 0.5 does not build.

Run for real, with `uname`, `curl`, `flatpak` and Python replaced by scripts
that record what they are asked for and then fail, which stops the install
where it would have fetched something.
"""

from __future__ import annotations

import os
import subprocess
from typing import TYPE_CHECKING

import pytest
from libera_build.repo import REPO

if TYPE_CHECKING:
    from pathlib import Path

SCRIPT = REPO / "build" / "install" / "install.sh"

FAKE_UNAME = """#!/bin/sh
case "$1" in -s) echo Linux ;; -m) echo "$FAKE_MACHINE" ;; esac
"""
# bundles/latest names 0.5.0; a download is recorded, then fails.
FAKE_CURL = """#!/bin/sh
for arg; do last="$arg"; done
case "$last" in
*/bundles/latest) echo 0.5.0 ;;
*) echo "$last" >> "$ASKED"; exit 22 ;;
esac
"""
# Python 3.14 that makes a venv of itself and records what pip installs.
FAKE_PYTHON = """#!/bin/sh
case "$1" in
-c) case "$2" in *platform*) echo 3.14.0 ;; esac; exit 0 ;;
-m) case "$2" in
    venv) for arg; do dir="$arg"; done
          mkdir -p "$dir/bin" && cp "$0" "$dir/bin/python" && : > "$dir/pyvenv.cfg"
          exit 0 ;;
    pip) for arg; do last="$arg"; done
         [ "$last" = pip ] && exit 0
         echo "pip $last" >> "$ASKED"; exit 1 ;;
    esac ;;
esac
"""


def run(tmp_path: Path, machine: str, *args: str) -> list[str]:
    fake = tmp_path / "bin"
    fake.mkdir()
    for name, text in (
        ("uname", FAKE_UNAME),
        ("curl", FAKE_CURL),
        ("flatpak", "#!/bin/sh\nexit 0\n"),
        ("python3.14", FAKE_PYTHON),
    ):
        (fake / name).write_text(text, encoding="utf-8")
        (fake / name).chmod(0o755)
    asked = tmp_path / "asked"
    env = {
        **os.environ,
        "PATH": f"{fake}:/usr/bin:/bin",
        "HOME": str(tmp_path / "home"),
        "FAKE_MACHINE": machine,
        "ASKED": str(asked),
    }
    subprocess.run(
        ["sh", str(SCRIPT), *args], env=env, capture_output=True, check=False
    )
    return asked.read_text(encoding="utf-8").split() if asked.is_file() else []


@pytest.mark.parametrize(
    ("machine", "bundle"),
    [
        ("aarch64", "libera-0.4.1-arm64.flatpak"),
        ("x86_64", "libera-0.5.0-amd64.flatpak"),
    ],
)
def test_the_flatpak_on_arm64_is_the_last_release_that_has_one(
    tmp_path, machine, bundle
):
    (asked,) = run(tmp_path, machine)
    assert asked.endswith(f"/bundles/{bundle}")


@pytest.mark.parametrize(
    ("machine", "spec"), [("aarch64", "libera==0.4.1"), ("x86_64", "libera")]
)
def test_pip_on_arm64_installs_the_last_release_that_has_editors(
    tmp_path, machine, spec
):
    assert run(tmp_path, machine, "--channel", "pip") == ["pip", spec]
