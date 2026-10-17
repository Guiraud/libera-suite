"""Nothing in the host imports anything above it.

`host/__init__.py` has listed the layers since the beginning, and the list was
a description rather than a rule: two edges broke it -- `server` and `window`
both reached up to `menu` -- and the breakage was invisible because it was
done with function-level imports. A `from x import y` inside a function is
what a circular dependency looks like once somebody has worked around it.

So the order is read out of that docstring and checked against the real import
graph, function-level imports included. Adding a layer means adding a line to
the docstring, which is the point: the two cannot drift.

The packages inside the host -- `server`, `window`, `menu` -- each list an order
of their own in their `__init__.py`, and are held to it the same way. They were
not, at first: every `libera.host.server.X` counted only as `server`, and a
relative import was not counted at all.
"""

from __future__ import annotations

import ast
import re
from typing import TYPE_CHECKING

import pytest
from support import repo_root

if TYPE_CHECKING:
    from pathlib import Path

SRC = repo_root() / "src"
HOST = SRC / "libera" / "host"
# The host, and each package in it.
PACKAGES = [HOST, *sorted(p.parent for p in HOST.glob("*/__init__.py"))]


def dotted(package: Path) -> str:
    return ".".join(package.relative_to(SRC).parts)


def documented_order(package: Path) -> list[str]:
    """The layers, innermost first, as the package's __init__.py lists them."""
    text = (package / "__init__.py").read_text(encoding="utf-8")
    body = text.split('"""')[1]
    names = []
    for line in body.splitlines():
        m = re.match(r"^ {4}(\w+) {2,}\S", line)
        if m:
            names.append(m.group(1))
    return names


def find_sources(package: Path, module: str) -> list[Path]:
    """A module's file, or every file of a package.

    Every file, not the package's `__init__.py`: that one only re-exports,
    and reading it alone let an upward import anywhere else in `server`,
    `window` or `menu` through unseen.
    """
    single = package / f"{module}.py"
    return [single] if single.is_file() else sorted((package / module).glob("*.py"))


def imported_names(path: Path, package: str) -> set[str]:
    """Every module a file imports, by its full name, wherever the import is
    written. Relative imports are resolved against `package`, the file's own,
    and `from p import n` counts as both `p` and `p.n`, since `n` may be a
    module."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                parent = package.rsplit(".", node.level - 1)[0]
                base = f"{parent}.{base}" if base else parent
            found.add(base)
            found.update(f"{base}.{alias.name}" for alias in node.names)
    return found


def imports_of(package: Path, module: str) -> set[str]:
    """The layers of `package` that `module` imports: the part of each name
    right after the package's own."""
    prefix = dotted(package) + "."
    return {
        name.removeprefix(prefix).split(".")[0]
        for path in find_sources(package, module)
        for name in imported_names(path, dotted(path.parent))
        if name.startswith(prefix)
    }


@pytest.mark.parametrize("package", PACKAGES, ids=lambda p: p.name)
def test_the_docstring_lists_every_module(package):
    listed = set(documented_order(package))
    real = {
        p.stem if p.suffix == ".py" else p.name
        for p in package.iterdir()
        if (p.suffix == ".py" and p.stem != "__init__")
        or (p.is_dir() and (p / "__init__.py").is_file())
    }

    assert real - listed == set(), "modules missing from the layer list"
    assert listed - real == set(), "layers listed that do not exist"


@pytest.mark.parametrize("package", PACKAGES, ids=lambda p: p.name)
def test_nothing_imports_upward(package):
    order = documented_order(package)
    rank = {name: i for i, name in enumerate(order)}

    upward = [
        (module, imported)
        for module in order
        for imported in sorted(imports_of(package, module))
        if imported in rank and rank[imported] > rank[module]
    ]

    assert upward == [], "these import a layer above themselves:\n  " + "\n  ".join(
        f"{a} -> {b}" for a, b in upward
    )


def test_a_relative_import_is_resolved(tmp_path):
    """Nothing in the host imports relatively today, so the case is made here:
    without it, the first one written would be invisible to the check above."""
    module = tmp_path / "api.py"
    module.write_text("from . import adapter\nfrom ..menu import gtk\n")

    assert imported_names(module, "libera.host.server") >= {
        "libera.host.server.adapter",
        "libera.host.menu.gtk",
    }


def test_only_the_handler_knows_the_web_framework():
    """Endpoints take a `api.Request` and return a `api.Response`.

    Bottle's `request` belongs to the thread serving it, the shape every thread
    bug in this host had (notes/lessons-learned/threads.md). Read only in
    `server/adapter.py`, it cannot leak into code that runs on another thread,
    and the framework can be swapped by changing that one module.
    """
    src = SRC / "libera"
    importers = sorted(
        p.relative_to(src).as_posix()
        for p in src.rglob("*.py")
        if re.search(
            r"(?m)^\s*(import bottle|from bottle\b)", p.read_text(encoding="utf-8")
        )
    )
    assert importers == ["host/server/adapter.py"]
