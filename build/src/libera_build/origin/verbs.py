"""The six verbs, as `lb release <verb>` and `ship`'s phases call them."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from libera.manifest import Manifest
from libera_build import inventory, repo, versions
from libera_build.hosts import ssh_host
from libera_build.origin import check, collect, place, publish, status
from libera_build.repo import REPO
from libera_build.report import RefusedError

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from libera_build.hosts import Host
    from libera_build.inventory import Builder


@dataclass(frozen=True)
class OriginOptions:
    verb: str
    dry_run: bool = False
    quick: bool = False  # check: sizes only
    wheel: str | None = None  # check: the manifest from a wheel, or "pypi"
    root: Path = REPO
    host_for: Callable[[Builder], Host] = field(default=ssh_host)


def run(options: OriginOptions) -> int:
    root, dry = options.root, options.dry_run
    where = place.here(root)
    dist = repo.dist(where.version)
    if options.verb == "status":
        status.status(root, where, dist)
    elif options.verb == "collect":
        builders = inventory.read(root / repo.BUILDERS)
        collect.collect(root, where.version, builders, options.host_for, dry=dry)
    elif options.verb == "push":
        publish.push(root, where, dist, dry=dry)
    elif options.verb == "check":
        check_against(root, where, options)
    elif options.verb == "extras":
        publish.extras(root, where, dry=dry)
    elif options.verb == "windows":
        publish.windows(root, where, dry=dry)
    else:
        msg = f"no such verb: {options.verb}"
        raise RefusedError(msg)
    return 0


def check_against(root: Path, where: place.Origin, options: OriginOptions) -> None:
    """Against the tree's manifest, or a wheel's: and in the directory *that*
    manifest names, not the tree's."""
    if options.wheel:
        manifest = check.wheel_manifest(options.wheel, versions.app_version(root))
    else:
        stamped = root / repo.MANIFEST
        if not stamped.is_file():
            msg = f"no {stamped} to check against: lb release collect"
            raise RefusedError(msg)
        manifest = Manifest.read(stamped)
    base = f"{where.cdn_url}/{where.zone}/{manifest.payload_version}"
    check.check(base, manifest, quick=options.quick)
