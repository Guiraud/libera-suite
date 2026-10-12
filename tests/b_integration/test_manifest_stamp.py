"""`python3 -m libera.manifest stamp`, the way build/engine/dist.sh runs it: from
inside src/, with nothing installed (-S), in a directory of real tarballs."""

from __future__ import annotations

import json
import subprocess
import sys
import tarfile

from support import repo_root


def test_stamp_writes_the_manifest_with_nothing_installed(tmp_path):
    for name in ("core-linux-arm64.tar.gz", "editors.tar.gz"):
        with tarfile.open(tmp_path / name, "w:gz"):
            pass
    root = repo_root()
    done = subprocess.run(
        [
            sys.executable,
            "-S",
            "-m",
            "libera.manifest",
            "stamp",
            str(tmp_path),
            "--payload-version",
            "0.4",
            "--font-set",
            "core",
            "--repo",
            str(root),
        ],
        cwd=root / "src",
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    assert "platforms: linux-arm64" in done.stdout
    written = json.loads((tmp_path / "manifest.json").read_text())
    assert written["payload_version"] == "0.4"
    assert written["source"]["libera_commit"]
    assert [a["name"] for a in written["artifacts"]] == [
        "core-linux-arm64.tar.gz",
        "editors.tar.gz",
    ]
