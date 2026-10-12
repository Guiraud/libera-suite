"""collect: every builder's core here, the shared pair from one of them, and
the manifest stamped over the lot.

The shared pair -- editors.tar.gz and fonts-core.tar.gz -- is built from the
same pinned sources everywhere, which makes it tempting to take whichever copy
arrives last. It is not byte-identical: tar records modes and order, gzip
records a timestamp, and two machines produce two different SHA-256 for the
same content. The manifest names one hash, so a second copy over one it
already describes is a hash mismatch on a tester's machine, reported there,
hours later, as a corrupt download. So exactly one builder, the neutral one,
supplies them.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from libera import manifest
from libera_build import repo
from libera_build.artifacts import core_name
from libera_build.inventory import dist_of
from libera_build.report import RefusedError, say, step

if TYPE_CHECKING:
    from collections.abc import Callable

    from libera_build.hosts import Host
    from libera_build.inventory import Builder

SHARED = ("editors.tar.gz", "fonts-core.tar.gz")
FONT_SET = "core"


def neutral_of(builders: list[Builder]) -> Builder:
    """The builder that supplies the shared pair: the one marked neutral, else
    the first, which collect says it is doing."""
    if not builders:
        msg = "no builders listed in build/builders.toml"
        raise RefusedError(msg)
    return next((b for b in builders if b.neutral), builders[0])


def fetch(b: Builder, host: Host, remote: str, local: Path, *, dry: bool) -> bool:
    """One file from a builder; False if it did not arrive, so that one
    unreachable builder does not throw away the transfers that worked.

    scp and not rsync: a build machine is whatever its platform gives, and
    Windows ships OpenSSH without rsync. These are whole files that either
    transfer or do not, so rsync's delta buys nothing.
    """
    if not b.remote:
        source = Path(remote).expanduser()
        if source.resolve() == local.resolve():
            say(f"    have  {local.name}")
            return True
        if not source.is_file():
            say(f"    MISSING {source}")
            return False
        if not dry:
            shutil.copyfile(source, local)
        say(f"    {'would copy' if dry else 'local'} {source}")
        return True
    if dry:
        say(f"    would scp {b.target}:{remote}")
        return True
    say(f"    scp   {b.target}:{remote}")
    # The previous release's copy goes first, and the size is what is
    # believed: scp reports success for a transfer that wrote nothing, and a
    # file already there would then pass for this release's.
    local.unlink(missing_ok=True)
    status, _ = host.fetch(remote, local)
    if status == 0 and local.is_file() and local.stat().st_size > 0:
        return True
    say("          failed -- is the payload built there for this version,")
    say("          and is the path in build/builders.toml right?")
    return False


def collect(
    root: Path,
    version: str,
    builders: list[Builder],
    host_for: Callable[[Builder], Host],
    *,
    dry: bool,
) -> None:
    """Into $BUILD_ROOT/out/dist/<version>, where push uploads from."""
    dist = repo.dist(version)
    step(f"collecting into {dist}")
    dist.mkdir(parents=True, exist_ok=True)
    missing = gather(version, builders, host_for, dist, dry=dry)
    show(dist)
    # A builder that was down is worth carrying on past. Stamping the manifest
    # anyway is not: a manifest with no arm64 core publishes cleanly and tells
    # an arm64 user "manifest has no core artifact for linux-arm64" days later.
    if missing:
        msg = (
            f"did not arrive: {' '.join(missing)}\n"
            "  The manifest is left as it was. Fix those and run collect again."
        )
        raise RefusedError(msg)
    step("manifest, over everything collected")
    if dry:
        say("    would stamp it, and copy it into the wheel (src/libera/manifest.json)")
        return
    stamp_into(root, dist, version)


def gather(
    version: str,
    builders: list[Builder],
    host_for: Callable[[Builder], Host],
    dist: Path,
    *,
    dry: bool,
) -> list[str]:
    """Every core, and the shared pair from the neutral builder: the names that
    did not arrive."""
    missing = []
    for b in builders:
        name = core_name(b.platform)
        remote = f"{dist_of(b)}/{version}/{name}"
        if not fetch(b, host_for(b), remote, dist / name, dry=dry):
            missing.append(name)
    neutral = neutral_of(builders)
    if not any(b.neutral for b in builders):
        say("    no builder marked 'neutral'; the shared artifacts come from the first")
    say(f"    shared artifacts from {neutral.target}")
    for name in SHARED:
        remote = f"{dist_of(neutral)}/{version}/{name}"
        if not fetch(neutral, host_for(neutral), remote, dist / name, dry=dry):
            missing.append(name)
    return missing


def show(dist: Path) -> None:
    step(f"what is in {dist}")
    for f in sorted(dist.iterdir()):
        if f.is_file():
            say(f"    {f.stat().st_size / 1e6:6.1f} MB  {f.name}")


def stamp_into(root: Path, dist: Path, version: str) -> None:
    """The manifest over the directory, and its copy in the wheel, which is
    what the installer verifies downloads against."""
    stamped = manifest.stamp(
        dist, payload_version=version, font_set=FONT_SET, repo=root
    )
    text = stamped.to_json()
    (dist / "manifest.json").write_text(text, encoding="utf-8")
    (root / repo.MANIFEST).write_text(text, encoding="utf-8")
    for a in stamped.artifacts:
        say(f"    {a.name:26} {a.size / 1e6:7.1f} MB  {a.sha256[:16]}…")
    if stamped.dirty:
        say("    WARNING: stamped from a dirty tree; provenance is not reproducible")
    say(f"    platforms: {', '.join(stamped.core_platforms)}")
    say("    manifest installed into the wheel")
