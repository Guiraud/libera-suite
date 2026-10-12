"""`lb on PLATFORM COMMAND...`: any `lb` command, run on a builder.

The way `ship` runs its builds there: in the builder's checkout, as `python3 -m
libera_build`, since nothing is installed there and the `lb` script is not.
The output streams as it comes, and the status is read from the verdict line
the script prints, not from ssh's exit status, which describes the shell.

The builder runs whatever commit its checkout is at. This says which, warns
when it is not this checkout's, and with --update sends this one first.
"""

from __future__ import annotations

import shlex
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from libera_build import inventory, repo
from libera_build.hosts import LB, MARK, remote_path, ssh_host
from libera_build.release.context import Context
from libera_build.release.phases import update
from libera_build.repo import REPO
from libera_build.report import RefusedError, say, step

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from libera_build.hosts import Host
    from libera_build.inventory import Builder


@dataclass(frozen=True)
class OnOptions:
    platform: str
    command: tuple[str, ...]
    update: bool = False
    root: Path = REPO
    host_for: Callable[[Builder], Host] = field(default=ssh_host)


def script_for(b: Builder, command: tuple[str, ...]) -> str:
    """What the builder runs: its HEAD said first, then the command, then the
    verdict line the caller believes."""
    line = shlex.join(command)
    return f"""
cd {remote_path(b.repo)} || {{ echo "{MARK}=no checkout at {b.repo}"; exit; }}
echo "HEAD=$(git rev-parse HEAD)"
{LB} {line}
echo "{MARK}=$?"
"""


def status_of(platform: str, verdict: str) -> int:
    """The command's exit status, from the verdict line. Anything else there
    is why the command never ran ("no checkout at ~/x"), and nothing at all
    means the connection dropped: either is a refusal that says so."""
    if verdict.isdigit():
        return int(verdict)
    msg = f"{platform}: {verdict or 'the command stopped without saying how'}"
    raise RefusedError(msg)


def on(options: OnOptions) -> int:
    builders = inventory.read(options.root / repo.BUILDERS)
    (b,) = inventory.narrow(builders, [options.platform])
    if not b.remote:
        msg = (
            f"{b.platform} is this machine: run `lb {shlex.join(options.command)}` here"
        )
        raise RefusedError(msg)
    if options.update:
        update.run(
            Context(
                root=options.root,
                builders=[b],
                phases=["update"],
                host_for=options.host_for,
            )
        )
    here = repo.head(options.root)
    step(f"lb {shlex.join(options.command)}, on {b.platform} ({b.target})")
    process = options.host_for(b).start(script_for(b, options.command))
    assert process.stdout is not None  # ken: start() pipes stdout
    verdict, seen_head = "", False
    for line in process.stdout:
        # The first line is the builder's HEAD, which the script prints first.
        if not seen_head and line.startswith("HEAD="):
            seen_head = True
            if (there := line.split("=", 1)[1].strip()) != here:
                say(f"    note: {b.platform} is at {there[:9]}, here at {here[:9]};")
                say("    --update sends this commit first")
            continue
        if line.startswith(f"{MARK}="):
            verdict = line.split("=", 1)[1].strip()
            continue
        print(line, end="", flush=True)
    process.wait()
    return status_of(b.platform, verdict)
