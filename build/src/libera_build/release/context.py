"""What one run of `lb release ship` is about."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from libera_build.hosts import ssh_host

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from libera_build.hosts import Host
    from libera_build.inventory import Builder


@dataclass(frozen=True)
class Context:
    root: Path  # the driving checkout: its HEAD is what the builders build
    builders: list[Builder]
    phases: list[str]
    yes: bool = False  # publish without asking
    # How a builder is reached. ssh, unless a test hands builders it made.
    host_for: Callable[[Builder], Host] = field(default=ssh_host)

    @property
    def logs(self) -> Path:
        return self.root / "tmp" / "remote"

    @property
    def remotes(self) -> list[Builder]:
        return [b for b in self.builders if b.remote]
