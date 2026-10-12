"""`update`: put this commit on every builder, checked out and clean.

Sent from here rather than pulled from a remote: a builder builds the commit
the driving checkout is at, on whatever branch, pushed or not. Pulling a named
branch meant pushing to it first, and forgetting to once built two 0.3.0
Flatpaks for 0.3.1. It lands as refs/heads/lb-build (hosts.BUILD_REF) and
is checked out detached.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from libera_build import repo
from libera_build.hosts import MARK, facts_from, remote_path
from libera_build.release import plan
from libera_build.report import problems, say, step

if TYPE_CHECKING:
    from libera_build.hosts import Host
    from libera_build.inventory import Builder
    from libera_build.release.context import Context


def run(ctx: Context) -> None:
    if not ctx.remotes:
        return
    step("sending this commit to the builders")
    here = repo.head(ctx.root)
    found: list[str] = []
    for b in ctx.remotes:
        host = ctx.host_for(b)
        if problem := send_commit(ctx, b, host, here):
            found.append(problem)
            continue
        out = host.capture(
            f"""
            cd {remote_path(b.repo)} || {{ echo "{MARK}=no such directory"; exit; }}
            git checkout --quiet --detach {here} 2>&1 \\
                || {{ echo "{MARK}=cannot check out {here[:9]}"; exit; }}
            echo "HEAD=$(git rev-parse HEAD)"
            echo "SHORT=$(git rev-parse --short HEAD)"
            echo "DIRTY=$(git status --porcelain | wc -l | tr -d ' ')"
            echo "{MARK}=ok"
            """
        )
        if wrong := plan.update_problems(b, facts_from(out), sent=here, mark=MARK):
            found += [f"{w}\n       {out}" for w in wrong]
            continue
        say(f"    {b.platform:<14} at {here[:9]}")
    problems(found, "no builder was started.")


def send_commit(ctx: Context, b: Builder, host: Host, commit: str) -> str | None:
    """Push one commit to a builder's checkout, making the checkout if there is
    none: it holds nothing but the commits it is sent. A complaint, or None."""
    made = host.capture(
        f"""
        [ -d {remote_path(b.repo)}/.git ] || git init --quiet {remote_path(b.repo)} 2>&1
        [ -d {remote_path(b.repo)}/.git ] && echo "{MARK}=ok"
        """
    )
    if facts_from(made).get(MARK) != "ok":
        return (
            f"{b.platform}: no checkout at {b.repo} on {b.target}, and none "
            f"could be made\n       {made}"
        )
    status, out = host.receive(ctx.root, commit, b.repo)
    if status != 0:
        return (
            f"{b.platform}: could not send {commit[:9]} to {b.target}\n"
            f"       {out.strip()}"
        )
    return None
