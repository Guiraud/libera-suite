"""The build tooling's tests: `lb`, the package in build/src/libera_build.

Three tiers, as for the application's tests in tests/, marked by the directory
they sit in: a_unit (pure functions), b_integration (real processes and git),
c_e2e (the installed `lb`, running real scripts). Unlike the application's
upper tiers these need no payload and never skip for want of one: the tooling
is what makes a payload, and runs on builders that have none.

No __init__.py anywhere here, on purpose: packages named a_unit beside the
application's tests/a_unit would collide.
"""

from __future__ import annotations

from pathlib import Path

import pytest

HERE = Path(__file__).parent
TIERS = {
    "a_unit": pytest.mark.unit,
    "b_integration": pytest.mark.integration,
    "c_e2e": pytest.mark.e2e,
}


def pytest_collection_modifyitems(config, items):
    """Mark each of this directory's tests by its tier. pytest hands this hook
    every item collected, so it leaves the rest alone."""
    for item in items:
        path = Path(item.fspath)
        if HERE not in path.parents:
            continue
        item.add_marker(TIERS[path.relative_to(HERE).parts[0]])
