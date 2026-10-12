"""What `lb` says while it works, and how it refuses.

A refusal is `RefusedError`, raised with a sentence that says what is wrong and what
to do about it. `lb` prints it and exits 1; nothing else catches it. The
scripts this replaces called `die()`, which exited from wherever it was, so no
caller, and no test, could see a refusal happen.
"""

from __future__ import annotations


class RefusedError(Exception):
    """A refusal: what is wrong, said so that the next step is obvious."""


def say(message: str = "") -> None:
    print(message, flush=True)


def step(message: str) -> None:
    print(f"\n==> {message}", flush=True)


def problems(found: list[str], verdict: str) -> None:
    """Say every problem, then refuse with the verdict, or do nothing."""
    if not found:
        return
    say()
    for problem in found:
        say(f"    - {problem}")
    raise RefusedError(verdict)
