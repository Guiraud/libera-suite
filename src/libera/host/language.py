"""The user's language and region: the editor's language, and the blank's.

Two answers, because the systems keep two. Measured on 2026-10-16: a Mac with
English menus and French regional settings reports `en-FR` as its language,
and its user wants English menus and A4 paper; the Windows builder reports
`en-GB` for its interface and `en-US` for its regional format. The editor
takes the language, and finds its own locale file from it -- `fr-FR` loads
`fr.json`, `pt-PT` loads `pt-pt.json`, and anything it has no file for loads
English. The blank, which carries the paper size and the language a new
document spell-checks in, takes both. See notes/24-interface-language.md.

Not the environment on macOS: an app started from the Finder has no `LANG`,
and `locale.getlocale()` is then `(None, 'UTF-8')`. Nor `locale.getlocale()`
on Windows, which answers `('English_United States', '1252')`.
"""

from __future__ import annotations

import functools
import os
import re
import sys
from typing import TYPE_CHECKING

from libera.payload import locate

if TYPE_CHECKING:
    from pathlib import Path

ENGLISH = "en"


@functools.cache
def get_language() -> str:
    """The language the editor runs in, as a tag: `fr-FR`, `de`, `en`.

    `ui_language` in config.toml comes first, the way `user_name` does.
    """
    chosen = (locate.read_config_string("ui_language") or "").strip()
    return chosen or _ask_system_language() or ENGLISH


@functools.cache
def get_region() -> str:
    """The system's region, as two capitals (`FR`), or "" when it says none."""
    return _ask_system_region().upper()


def find_blank_dir(blanks: Path) -> Path:
    """The folder of blanks for this user, under the payload's `empty/`.

    The language and region's own (`fr-FR`); else, in English, the US blank in
    the US and the British one, which is A4, everywhere else; else the first
    for the language (`fr-CA` gets `fr-FR`); else `empty/` itself, the US
    English one, which is all a payload before 0.5 has.
    """
    language = get_language().split("-")[0].lower()
    region = get_region()
    if language == ENGLISH:
        wanted = [f"en-{'US' if region == 'US' else 'GB'}"]
    else:
        wanted = [f"{language}-{region}"]
        wanted += sorted(p.name for p in blanks.glob(f"{language}-*"))
    for name in wanted:
        if (blanks / name).is_dir():
            return blanks / name
    return blanks


def parse_posix_locale(value: str) -> tuple[str, str]:
    """`fr_FR.UTF-8@euro` as (`fr-FR`, `FR`); `C` and `POSIX` as nothing."""
    tag = re.split(r"[.@]", value)[0]
    if tag in {"", "C", "POSIX"}:
        return "", ""
    language, _, region = tag.partition("_")
    return (f"{language}-{region}" if region else language), region


def _read_posix_variable(*names: str) -> str:
    """The first of these the environment sets, as gettext looks them up."""
    return next((os.environ[n] for n in names if os.environ.get(n)), "")


def _ask_system_language() -> str:
    if sys.platform == "darwin":
        import Foundation

        preferred = Foundation.NSLocale.preferredLanguages()
        return str(preferred[0]) if preferred else ""
    if sys.platform == "win32":
        return _ask_windows_language()
    variable = _read_posix_variable("LC_ALL", "LC_MESSAGES", "LANG")
    return parse_posix_locale(variable)[0]


def _ask_system_region() -> str:
    if sys.platform == "darwin":
        import Foundation

        return str(Foundation.NSLocale.currentLocale().countryCode() or "")
    if sys.platform == "win32":
        return _ask_windows_locale().rpartition("-")[2]
    variable = _read_posix_variable("LC_ALL", "LC_PAPER", "LANG")
    return parse_posix_locale(variable)[1]


def _ask_windows_language() -> str:
    """The first of the user's interface languages, or ""."""
    # Blocks, not early returns: a checker on another platform would find no
    # windll, as desktop._start explains.
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        count, size = wintypes.ULONG(), wintypes.ULONG()
        by_name = 8  # MUI_LANGUAGE_NAME
        ask = ctypes.windll.kernel32.GetUserPreferredUILanguages
        ask(by_name, ctypes.byref(count), None, ctypes.byref(size))
        buffer = ctypes.create_unicode_buffer(size.value)
        if ask(by_name, ctypes.byref(count), buffer, ctypes.byref(size)):
            # Names each ended by a NUL: the value stops at the first.
            return buffer.value
    return ""


def _ask_windows_locale() -> str:
    """The regional format's locale name, `en-US`, or ""."""
    if sys.platform == "win32":
        import ctypes

        buffer = ctypes.create_unicode_buffer(85)  # LOCALE_NAME_MAX_LENGTH
        if ctypes.windll.kernel32.GetUserDefaultLocaleName(buffer, len(buffer)):
            return buffer.value
    return ""
