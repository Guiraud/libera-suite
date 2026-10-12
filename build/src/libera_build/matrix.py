"""`lb release matrix`: does the Linux converter about to be published run
where we say it runs?

For each architecture and each image, it unpacks that architecture's core into
a clean container and has x2t convert a docx to odt, the way the host runs it,
then looks for the document's text in what came out. `lb release check` proves
the bytes arrived; this proves they are usable. The glibc floor was wrong once
already: the x86_64 core built on noble needed GLIBC 2.38 and would not load on
Ubuntu 22.04 or Debian 12 (notes/13). Its first run found the install page
claiming Fedora 35 and RHEL 9, where glibc 2.34 cannot load a core that needs
2.35.

The Flatpak is not what this checks. It carries its own runtime and does not
care what the distribution is; this is the payload the wheel installs.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

from libera_build import repo, versions
from libera_build.artifacts import core_name
from libera_build.buildbox import exported_dist
from libera_build.containers import Engine, Mount, Run, host_arch, linux_platform
from libera_build.process import run_quietly
from libera_build.repo import REPO
from libera_build.report import RefusedError, say, step

# The floor of every family docs/src/main/install.md names, and the newest
# Ubuntu LTS. Fully qualified: podman otherwise resolves short names through an
# alias table and says so on stderr, which is where the loader's error goes too.
DISTROS = (
    "docker.io/library/ubuntu:22.04",
    "docker.io/library/debian:12",
    "docker.io/library/fedora:36",
    "docker.io/library/almalinux:9",
    "docker.io/library/ubuntu:24.04",
)
ARCHES = ("x86_64", "arm64")
# What the sample document says, so what a conversion must still say.
NEEDLE = "Second paragraph"


@dataclass(frozen=True)
class MatrixOptions:
    dist: Path | None = None
    distros: tuple[str, ...] = ()
    arches: tuple[str, ...] = ()


def holds_text(odt: Path, needle: str) -> bool:
    """Whether a converted document says what it should. The text, not the
    exit status: x2t has written well-formed empty documents and exited 0
    before (CLAUDE.md, "things that fail silently")."""
    try:
        xml = zipfile.ZipFile(odt).read("content.xml").decode("utf-8", "replace")
    except (OSError, KeyError, zipfile.BadZipFile):
        return False
    return needle in re.sub(r"<[^>]+>", "", xml)


def choose(options: MatrixOptions) -> tuple[Path, tuple[str, ...]]:
    """The artifacts, and the architectures to try.

    The release's collected directory, with both architectures; on a builder,
    which has none, its own container build, and its own architecture.
    """
    dist = options.dist or repo.dist(versions.payload_version(REPO))
    if dist.is_dir():
        return dist, options.arches or ARCHES
    own = host_arch()
    found = exported_dist(own)
    if found is None:
        msg = f"no artifacts in {dist}, and no container build here: --dist DIR"
        raise RefusedError(msg)
    return found, options.arches or (own,)


def make_sample(dist: Path, work: Path) -> Path:
    """The sample docx, built on the blank the payload itself ships, so that
    nothing but the artifacts is needed: a builder keeps its sources inside
    the container build."""
    editors = dist / "editors.tar.gz"
    if not editors.is_file():
        msg = f"no {editors}"
        raise RefusedError(msg)
    with tarfile.open(editors) as tar:
        tar.extract("empty/new.docx", work, filter="data")
    sample = work / "in.docx"
    run_quietly(
        [sys.executable, str(REPO / "tests/support/make_sample_docx.py"), str(sample)],
        "the sample document",
        env={**os.environ, "LIBERA_BLANK": str(work / "empty" / "new.docx")},
    )
    return sample


def convert_in(
    engine: Engine, image: str, arch: str, core: Path, work: Path
) -> str | None:
    """Convert the sample in one clean container: None if the text came
    through, else the first thing the container said, which is where the
    loader names a missing symbol version."""
    out = f"out-{arch}-{image.replace(':', '-').replace('/', '-')}.odt"
    run_ = Run(
        image,
        ("/core/bin/x2t", "/w/in.docx", f"/w/{out}"),
        arch,
        mounts=(Mount(core, "/core", read_only=True), Mount(work, "/w")),
        env={"LD_LIBRARY_PATH": "/core/bin", "APPLICATION_NAME": "Libera Suite"},
        extra=("--quiet",),
    )
    done = subprocess.run(
        engine.run_argv(run_), capture_output=True, text=True, check=False
    )
    if holds_text(work / out, NEEDLE):
        return None
    lines = (done.stdout + done.stderr).strip().splitlines()
    return lines[0] if lines else "no output"


def run(options: MatrixOptions, engine: Engine | None = None) -> int:
    engine = engine or Engine.here()
    dist, arches = choose(options)
    distros = options.distros or DISTROS
    failed = 0
    with tempfile.TemporaryDirectory(prefix="libera-matrix-") as scratch:
        work = Path(scratch)
        make_sample(dist, work)
        for arch in arches:
            tarball = dist / core_name(linux_platform(arch))
            if not tarball.is_file():
                msg = f"no {tarball}"
                raise RefusedError(msg)
            core = work / f"core-{arch}"
            core.mkdir()
            with tarfile.open(tarball) as tar:
                tar.extractall(core, filter="data")
            step(f"{arch}, from {tarball}")
            for image in distros:
                said = convert_in(engine, image, arch, core, work)
                name = image.rsplit("/", 1)[-1]
                if said is None:
                    say(f"    {name:<16} ok")
                else:
                    failed += 1
                    say(f"    {name:<16} FAIL: {said}")
    say()
    if failed:
        msg = f"{failed} combination(s) could not convert"
        raise RefusedError(msg)
    say("PASS")
    return 0
