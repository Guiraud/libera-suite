"""The Libera.app that `libera --launcher-install` builds on macOS.

Compiling and registering need a Mac and are left to it. What can go wrong
anywhere is checked here: the document types drifting from the ones
macos-app.sh declares, a plist that does not parse, and a Homebrew path that
`brew upgrade` would delete under the bundle.
"""

from __future__ import annotations

import plistlib
import re
import sys
from pathlib import Path

from support import repo_root

from libera import macos_app


def test_the_plist_parses_and_names_the_bundle():
    info = plistlib.loads(macos_app.render_info_plist("14.0"))
    assert info["CFBundleIdentifier"] == "eu.liberasuite.Libera"
    assert info["CFBundleExecutable"] == "Libera"
    assert info["NSPrincipalClass"] == "NSApplication"
    assert info["LSMinimumSystemVersion"] == "14.0"
    assert all(t["LSHandlerRank"] == "Alternate" for t in info["CFBundleDocumentTypes"])


def test_the_document_types_match_macos_app_sh():
    """Two bundles, one list: a type added to one must reach the other."""
    script = (repo_root() / "build" / "macos" / "macos-app.sh").read_text()
    plist = script[script.index("<plist") : script.index("</plist>") + len("</plist>")]
    plist = re.sub(r"<!--.*?-->", "", plist, flags=re.DOTALL).replace("$VERSION", "0")
    plist = plist.replace("$MIN_MACOS", "14.0")
    declared = plistlib.loads(('<?xml version="1.0"?>' + plist).encode())
    expected = [
        (d["CFBundleTypeName"], d["LSItemContentTypes"])
        for d in declared["CFBundleDocumentTypes"]
    ]
    assert expected == macos_app.DOCUMENT_TYPES


def test_a_cellar_path_becomes_its_opt_link(tmp_path):
    opt = tmp_path / "opt" / "libera" / "libexec" / "bin" / "python3"
    opt.parent.mkdir(parents=True)
    opt.touch()
    cellar = tmp_path / "Cellar" / "libera" / "0.5.0" / "libexec" / "bin" / "python3"
    assert macos_app._stable(cellar) == opt


def test_a_cellar_path_with_no_opt_link_is_kept(tmp_path):
    cellar = tmp_path / "Cellar" / "libera" / "0.5.0" / "bin" / "python3"
    assert macos_app._stable(cellar) == cellar


def test_the_interpreter_is_not_resolved(monkeypatch, tmp_path):
    """A virtualenv's python3 is a link; its target has no libera."""
    real = tmp_path / "real-python"
    real.touch()
    venv = tmp_path / "venv" / "bin" / "python3"
    venv.parent.mkdir(parents=True)
    venv.symlink_to(real)
    monkeypatch.setattr(sys, "executable", str(venv))
    assert macos_app.get_interpreter() == venv


def test_no_compiler_is_explained(monkeypatch):
    monkeypatch.setattr(sys, "executable", "/usr/local/bin/python3")
    monkeypatch.setattr(macos_app, "find_compiler", lambda: None)
    assert "xcode-select --install" in (macos_app.explain_unsupported() or "")


def test_inside_a_bundle_there_is_nothing_to_build(monkeypatch):
    monkeypatch.setattr(
        sys,
        "executable",
        "/Applications/Libera.app/Contents/Resources/python/bin/python3",
    )
    assert "bundle" in (macos_app.explain_unsupported() or "")


def test_the_app_goes_in_the_users_applications(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert macos_app.get_app_path() == tmp_path / "Applications" / "Libera.app"
    assert macos_app.remove() == []
