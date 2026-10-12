"""collect, push, check, publish and verify: the origin and PyPI."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from libera_build import versions
from libera_build.origin.verbs import OriginOptions, run
from libera_build.process import run_here
from libera_build.report import RefusedError, say, step

if TYPE_CHECKING:
    from libera_build.release.context import Context


def origin(ctx: Context, verb: str, *, wheel: str | None = None) -> None:
    run(OriginOptions(verb, wheel=wheel, root=ctx.root, host_for=ctx.host_for))


def publish(ctx: Context) -> None:
    """PyPI, then the bundles and the install scripts. The one phase with no undo.

    PyPI refuses a version it has already seen, even after a yank, so a
    mistaken publish costs a version number. It asks unless told not to, and it
    asks on /dev/tty: this is sometimes run under tmux with its output
    redirected, and a prompt nobody can see is a hang.
    """
    app = versions.app_version(ctx.root)
    step(f"publishing libera {app}")
    if not ctx.yes:
        confirm(app)
    run_here(["make", "publish"], "publish", cwd=ctx.root)
    origin(ctx, "extras")


def confirm(app: str) -> None:
    say("    PyPI accepts a version once. There is no undo, and a yank")
    say("    does not free the number.")
    try:
        with Path("/dev/tty").open(encoding="utf-8") as tty:
            say("")
            print(f"    publish {app} to PyPI? [y/N] ", end="", flush=True)
            answer = tty.readline().strip().lower()
    except OSError as e:
        msg = "no terminal to ask on. Re-run with --yes when you mean it."
        raise RefusedError(msg) from e
    if answer not in {"y", "yes"}:
        msg = "nothing was published."
        raise RefusedError(msg)


def verify(ctx: Context) -> None:
    """Read the *published* wheel back and check it against the origin.

    Not the manifest in this tree, which is correct by construction. `libera`
    0.1.0 went up naming a payload that was rebuilt two days later, and every
    check that existed passed, because each read the copy that agreed with it.
    """
    step("the published wheel against the published payload")
    try:
        origin(ctx, "check", wheel="pypi")
    except RefusedError as e:
        msg = (
            "what PyPI serves and what the origin serves do not agree.\n"
            "       This is the check 0.1.0 never had; believe it."
        )
        raise RefusedError(msg) from e
