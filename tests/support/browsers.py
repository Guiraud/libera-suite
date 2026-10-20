"""A Playwright browser, installed by the suite the first time it is wanted."""

from __future__ import annotations

import subprocess
import sys

import pytest
from playwright.sync_api import Error


def launch(play, engine: str = "chromium"):
    """`engine`, launched; installed first if Playwright has not downloaded it.

    The e2e tier skipped on every machine that had not run `playwright
    install`, which a fresh checkout has not. A browser that cannot be
    installed (offline, or a system missing what it needs) still skips, and
    says why.
    """
    browser_type = getattr(play, engine)
    try:
        return browser_type.launch()
    except Error:
        pass
    print(f"installing Playwright's {engine} for the tests", file=sys.stderr)
    done = subprocess.run(
        [sys.executable, "-m", "playwright", "install", engine],
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        return browser_type.launch()
    except Error as e:
        said = (done.stderr or done.stdout).strip().splitlines()[-1:] or [str(e)]
        pytest.skip(f"Playwright's {engine} could not be installed: {said[0]}")
