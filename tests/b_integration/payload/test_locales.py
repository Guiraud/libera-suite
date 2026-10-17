"""The editor in every language the payload has, and a blank for each locale.

A string a language lacks is taken from the default in the editor's code, and
Euro-Office added strings with no default, in en.json alone: one of them,
tipSmartPicker, threw while Words loaded in French, Italian, Spanish and
Portuguese, which then never became editable. The payload fills every gap
with the English.
"""

from __future__ import annotations

import json
import zipfile

import pytest

# The four the host opens, by their directory in web-apps.
EDITORS = {"documenteditor", "spreadsheeteditor", "presentationeditor", "visioeditor"}


def read_strings(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_every_language_has_every_string(live_payload):
    folders = sorted((live_payload / "web-apps/apps").glob("*/main/locale"))
    editors = {folder.parent.parent.name for folder in folders}
    assert editors >= EDITORS, f"found only {editors}"
    for folder in folders:
        english = read_strings(folder / "en.json").keys()
        lacking = {
            path.name: len(english - read_strings(path).keys())
            for path in folder.glob("*.json")
        }
        assert set(lacking.values()) == {0}, f"{folder}: {lacking}"


@pytest.mark.parametrize(
    ("locale", "width"),
    [("en-US", "12240"), ("en-GB", "11906"), ("fr-FR", "11906"), ("de-DE", "11906")],
)
def test_each_locale_has_its_blanks(live_payload, locale, width):
    """Letter in the US, A4 elsewhere, and the locale's own language."""
    folder = live_payload / "empty" / locale
    assert {"new.docx", "new.pptx", "new.xlsx"} <= {p.name for p in folder.iterdir()}
    with zipfile.ZipFile(folder / "new.docx") as blank:
        document = blank.read("word/document.xml").decode()
        styles = blank.read("word/styles.xml").decode()
    assert f'<w:pgSz w:w="{width}"' in document
    assert f'w:lang w:val="{locale}"' in styles
