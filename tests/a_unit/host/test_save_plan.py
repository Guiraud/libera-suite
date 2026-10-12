"""What a save request means, decided before anything touches the disk.

save_document used to work this out inline, mixed with making directories,
running x2t, copying files out and opening a PDF viewer -- sixty lines and
fourteen branches that could only be tested with a session, a dialog hook and
a converter. The rules are the interesting part and they are pure, so they
live in plan_save and are checked here.
"""

from __future__ import annotations

import pathlib

import pytest

from libera.host import apps
from libera.host.saving import SaveRequest, plan_save

DOCX = pathlib.Path("/home/u/Rapport.docx")


def test_plain_save_overwrites_the_document_that_is_open():
    plan = plan_save(SaveRequest(), apps.WORDS, DOCX)

    assert plan.target == DOCX
    assert plan.ext == "docx"
    assert not plan.printing
    assert not plan.asks_where


def test_save_as_asks_even_though_the_format_matches():
    plan = plan_save(SaveRequest(save_as=True), apps.WORDS, DOCX)

    assert plan.asks_where


def test_a_different_format_is_a_save_as_whatever_the_editor_called_it():
    """Asking for .odt from an open .docx must not overwrite the .docx."""
    odt = next(fid for fid, (ext, _) in apps.WORDS.formats.items() if ext == "odt")

    plan = plan_save(SaveRequest(file_type=odt), apps.WORDS, DOCX)

    assert plan.ext == "odt"
    assert plan.target is None, "it would have written .odt over the open .docx"


def test_printing_asks_where_the_pdf_goes():
    """It went into the session's own directory, where nobody could find it
    and which is swept when the session ends. Never over the document."""
    plan = plan_save(SaveRequest(printing=True), apps.WORDS, DOCX)

    assert plan.printing
    assert plan.target is None
    assert plan.asks_where


def test_printing_asks_whatever_else_the_editor_says():
    plan = plan_save(SaveRequest(save_as=True, printing=True), apps.WORDS, DOCX)

    assert plan.asks_where
    assert plan.target is None


def test_an_untitled_document_has_nothing_to_overwrite():
    plan = plan_save(SaveRequest(), apps.WORDS, None)

    assert plan.target is None


@pytest.mark.parametrize("app", [apps.WORDS, apps.TABLES, apps.SLIDES])
def test_an_unknown_format_id_falls_back_to_the_editors_own(app):
    """fileType 0 is what the editor sends when it means "the usual"."""
    plan = plan_save(SaveRequest(file_type=99999), app, None)

    assert (plan.ext, plan.fmt) == app.formats[0]


@pytest.mark.parametrize(
    ("app", "name"),
    [
        (apps.WORDS, "Rapport.odt"),
        (apps.TABLES, "Budget.ods"),
        (apps.TABLES, "Export.csv"),
        (apps.SLIDES, "Deck.odp"),
        (apps.WORDS, "RAPPORT.DOCX"),
    ],
)
def test_plain_save_keeps_the_format_the_document_has(app, name):
    """fileType 0 is the editor's plain Save: the format the document already has.

    Read as the editor's first format, it wrote a .docx or .xlsx into the
    session and said it had saved, and the document stayed as it was.
    """
    document = pathlib.Path("/home/u") / name
    plan = plan_save(SaveRequest(), app, document)

    assert plan.target == document
    assert plan.ext == document.suffix.lstrip(".").lower()
    assert not plan.asks_where


def test_plain_save_of_a_format_it_cannot_write_asks_where():
    """x2t reads .doc and does not write it, so Save has to make a new file."""
    plan = plan_save(SaveRequest(), apps.WORDS, pathlib.Path("/home/u/Old.doc"))

    assert plan.target is None
    assert plan.asks_where
    assert plan.ext == "docx"


@pytest.mark.parametrize(
    ("body", "request_"),
    [
        ({}, SaveRequest()),
        ({"fileType": 65, "params": "saveas=true"}, SaveRequest(65, save_as=True)),
        ({"fileType": 513, "isPrint": True}, SaveRequest(513, printing=True)),
        ({"fileType": None, "params": None}, SaveRequest()),
    ],
)
def test_a_save_request_is_read_from_the_editor_body(body, request_):
    assert SaveRequest.from_body(body) == request_


@pytest.mark.parametrize("file_type", ["65", True, 6.5])
def test_a_format_that_is_not_an_id_is_refused(file_type):
    with pytest.raises(TypeError, match="not a format id"):
        SaveRequest.from_body({"fileType": file_type})
