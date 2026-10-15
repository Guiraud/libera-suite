"""The two versions, which move independently on purpose.

The application is the `libera` package; the payload is the editor build it
fetches. A host fix should not force a 120 MB re-download, so the wheel and the
Flatpak bundles are named for the first and the origin's directory for the
second.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import tomllib

from libera_build.repo import PAYLOAD_VERSION
from libera_build.report import RefusedError

if TYPE_CHECKING:
    from pathlib import Path


def payload_version(root: Path) -> str:
    """The payload version, as dist.sh and flatpak.py read it.

    payload.version is a commented TOML-ish file, not a bare number, and
    reading it whole once printed the file's comment block as the version.
    """
    text = (root / PAYLOAD_VERSION).read_text(encoding="utf-8")
    for line in text.splitlines():
        key, sep, value = line.partition("=")
        if sep and key.strip() == "version":
            return value.strip().strip('"')
    msg = f"no version in {root / PAYLOAD_VERSION}"
    raise RefusedError(msg)


def app_version(root: Path) -> str:
    doc = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    return str(doc["project"]["version"])


def is_prerelease(version: str) -> bool:
    """Anything but digits and dots: 0.4.0rc1, and a .post or a +local too.

    The rule is install.sh's, which refuses a pointer naming anything else, so
    a release that moved `latest` to one would stop every `curl | sh`. pip
    leaves such a version alone unless asked (`--pre`), and so the pointers
    and the install scripts do too: a pre-release is reached by its own name.
    """
    return not re.fullmatch(r"\d+(\.\d+)*", version)
