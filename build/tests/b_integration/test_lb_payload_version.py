"""Every reader of payload.version reads the same version.

The host reads it with tomllib, `lb` read it by splitting lines on `=`, and
each build script had a sed of its own: a trailing comment went into one
reader's version, and a CRLF checkout's carriage return into another's.
"""

from __future__ import annotations

import subprocess

import pytest
from libera_build import versions
from libera_build.repo import PAYLOAD_VERSION, REPO

VARIANTS = {
    "plain": b'version = "0.4.1"\n',
    "commented": b'# why\nversion = "0.4.1"  # pinned\n',
    "crlf": b'# why\r\nversion = "0.4.1"\r\n',
}


@pytest.mark.parametrize("text", VARIANTS.values(), ids=list(VARIANTS))
def test_the_build_scripts_and_lb_read_the_same_version(tmp_path, text):
    (tmp_path / PAYLOAD_VERSION).parent.mkdir(parents=True)
    (tmp_path / PAYLOAD_VERSION).write_bytes(text)

    shell = subprocess.run(
        [
            "sh",
            "-c",
            '. "$0/build/engine/common.sh"; payload_version "$1"',
            REPO,
            tmp_path,
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout

    assert shell == "0.4.1\n"
    assert versions.payload_version(tmp_path) == "0.4.1"
