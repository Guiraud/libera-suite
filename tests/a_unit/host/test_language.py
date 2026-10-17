"""The editor's language, and the blank a new document starts from.

The two answers are kept apart because the systems keep them apart: a Mac
with English menus and French regional settings says `en-FR`, and its user
wants English menus and A4 paper.
"""

from __future__ import annotations

import re
import urllib.parse
from pathlib import Path

import pytest

from libera.host import apps, language, server
from libera.host.session import Session
from libera.payload import locate


@pytest.fixture
def config(tmp_path, monkeypatch):
    """A config.toml of the test's own, and the cached answers forgotten."""
    path = tmp_path / "config.toml"
    monkeypatch.setattr(locate, "get_config_file", lambda: path)
    language.get_language.cache_clear()
    yield path
    language.get_language.cache_clear()


def test_the_system_says_a_language_and_the_editor_is_told_it(config):
    url = server.make_editor_url(
        43110,
        Session(payload=Path("/payload"), work=Path("/abc"), app=apps.WORDS),
        "Note.docx",
    )
    query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)

    assert query["lang"] == [language.get_language()]
    assert re.fullmatch(r"[a-z]{2,3}(-[A-Za-z0-9]+)*", language.get_language())
    assert re.fullmatch(r"([A-Z]{2})?", language.get_region())


def test_a_configured_language_comes_first(config):
    config.write_text('ui_language = "it-IT"\n', encoding="utf-8")
    assert language.get_language() == "it-IT"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("fr_FR.UTF-8", ("fr-FR", "FR")),
        ("de_DE@euro", ("de-DE", "DE")),
        ("pt_BR", ("pt-BR", "BR")),
        ("es", ("es", "")),
        ("C.UTF-8", ("", "")),
        ("POSIX", ("", "")),
        ("", ("", "")),
    ],
)
def test_a_posix_locale_is_read_as_a_tag_and_a_region(value, expected):
    assert language.parse_posix_locale(value) == expected


@pytest.fixture
def blanks(tmp_path):
    """The payload's empty/, with a few of its 45 locales."""
    root = tmp_path / "empty"
    for name in ("en-US", "en-GB", "fr-FR", "de-DE", "sr-Cyrl-RS", "sr-Latn-RS"):
        (root / name).mkdir(parents=True)
    return root


@pytest.mark.parametrize(
    ("said", "region", "chosen"),
    [
        ("fr-FR", "FR", "fr-FR"),
        ("en-FR", "FR", "en-GB"),  # English menus, A4
        ("en-US", "US", "en-US"),
        ("en", "", "en-GB"),
        ("fr-CA", "CA", "fr-FR"),  # the language's, where its region has none
        ("de", "AT", "de-DE"),
        ("sr-Cyrl-RS", "RS", "sr-Cyrl-RS"),
        ("eo", "", "."),  # no blank in the language: empty/'s own, US English
    ],
)
def test_the_blank_follows_the_language_and_the_region(
    blanks, monkeypatch, said, region, chosen
):
    monkeypatch.setattr(language, "get_language", lambda: said)
    monkeypatch.setattr(language, "get_region", lambda: region)
    assert language.find_blank_dir(blanks) == blanks / chosen


def test_a_payload_with_no_locale_folders_keeps_its_one_blank(tmp_path, monkeypatch):
    """A payload before 0.5 has empty/new.docx and nothing under it."""
    monkeypatch.setattr(language, "get_language", lambda: "fr-FR")
    monkeypatch.setattr(language, "get_region", lambda: "FR")
    assert language.find_blank_dir(tmp_path) == tmp_path
