"""x2t, run out of the payload for real.

The unit tests can check what job file we write; only this can check that x2t
accepts it. Every conversion here starts from the Editor.bin the `opened`
fixture produced, which is the same thing a save does.
"""

from __future__ import annotations

import csv
import io
import re
import zipfile
from typing import TYPE_CHECKING

import pytest
from support import ScriptedShell

from libera import payload as payload_mod
from libera.host import apps, hooks, opening, session as sessions
from libera.host.convert import ConversionError, export
from libera.host.saving import SaveRequest, save_document
from libera.host.session import Session

if TYPE_CHECKING:
    import pathlib


def test_opening_a_document_produces_an_editor_bin(opened: Session):
    assert opened.editor_bin.stat().st_size > 0


OFFERED = [
    (app, ext) for app in apps.ALL if app.editable for _, ext in app.save_formats
]


@pytest.mark.parametrize(
    ("app", "ext"), OFFERED, ids=[f"{a.name}-{e}" for a, e in OFFERED]
)
def test_every_format_every_editor_offers_is_one_x2t_writes(
    open_blank, tmp_path: pathlib.Path, app: apps.App, ext: str
):
    """The Save As popup promises these, for each editor in turn.

    x2t refuses a fair few ids sitting right beside the ones it accepts -- xls
    (258), ppt (130), odg (140), every legacy binary and flat-XML format -- so
    the only way to know which is which is to ask it.
    """
    blank = open_blank(app)
    out = tmp_path / f"out.{ext}"
    export(blank, out, app.ids_by_ext[ext], None)
    assert out.stat().st_size > 0


@pytest.mark.parametrize("app", apps.ALL, ids=lambda a: a.name)
def test_no_editor_offers_a_format_its_converter_does_not_know(app: apps.App):
    assert {ext for _, ext in app.save_formats} <= set(app.ids_by_ext)


def test_plain_save_overwrites_the_document_that_is_open(opened: Session):
    """fileType 0 means "whatever it already was", and no dialog is involved."""
    before = opened.document.stat().st_mtime_ns
    result = save_document(opened, SaveRequest())

    assert result == {"error": 0, "path": str(opened.document)}
    assert opened.document.stat().st_mtime_ns != before
    # Saved means nothing left to recover.
    assert not opened.unsaved_marker.is_file()


def test_save_as_follows_the_extension_the_user_typed(
    opened: Session, tmp_path: pathlib.Path, monkeypatch
):
    """The chooser's suffix wins over the format the editor asked for.

    The popup and the typed name can disagree; the name is what the user sees,
    so it decides, and the format follows it.
    """
    chosen = tmp_path / "elsewhere.odt"
    monkeypatch.setattr(
        hooks,
        "shell",
        ScriptedShell(choose_save_path=lambda _name, _formats, _start_in: str(chosen)),
    )

    result = save_document(opened, SaveRequest(file_type=65, save_as=True))

    assert result == {"error": 0, "path": str(chosen)}
    assert chosen.read_bytes()[:2] == b"PK"  # an ODF package, not a docx
    # Save As moves the session onto the new file; a plain Save now goes there.
    assert opened.current_file.read_text() == str(chosen)


def test_a_failed_save_as_leaves_the_session_on_the_open_document(
    opened: Session, tmp_path: pathlib.Path, monkeypatch
):
    """Until the new file exists, the document is still where it was.

    The session used to move first, so after a failed Save As the next plain
    Save wrote to a path the user had abandoned, and the recovery marker
    named a file that did not exist.
    """
    elsewhere = str(tmp_path / "elsewhere.odt")
    monkeypatch.setattr(
        hooks,
        "shell",
        ScriptedShell(choose_save_path=lambda _name, _formats, _start_in: elsewhere),
    )

    def fails(*_a):
        msg = "x2t could not write elsewhere.odt (exit status 1)"
        raise ConversionError(msg)

    monkeypatch.setattr("libera.host.convert.export", fails)

    result = save_document(opened, SaveRequest(file_type=65, save_as=True))

    assert result["error"] == 2
    assert opened.current_file.read_text() == str(opened.document)


def test_a_cancelled_save_as_writes_nothing_and_says_nothing(
    opened: Session, monkeypatch
):
    """Error 1 is DesktopOfflineAppDocumentEndSave's "stay quiet"."""
    monkeypatch.setattr(
        hooks,
        "shell",
        ScriptedShell(choose_save_path=lambda _name, _formats, _start_in: ""),
    )
    before = opened.document.stat().st_mtime_ns

    assert save_document(opened, SaveRequest(file_type=65, save_as=True)) == {
        "error": 1
    }
    assert opened.document.stat().st_mtime_ns == before


def test_printing_makes_a_pdf_beside_the_session_not_over_the_document(
    opened: Session, monkeypatch
):
    """Print is a PDF save with no destination: it must not touch the docx."""
    monkeypatch.setattr("libera.host.desktop.open_externally", lambda _p: True)
    before = opened.document.stat().st_mtime_ns

    result = save_document(opened, SaveRequest(file_type=513, printing=True))

    assert result["error"] == 0
    assert result["path"].endswith(f"{opened.document.stem}.pdf")
    assert opened.document.stat().st_mtime_ns == before


def printing_where(monkeypatch, answer):
    """A windowed shell whose save panel answers `answer`, recording what it
    was asked; and the viewer, recording what it was handed."""
    asked: list = []
    shown: list = []

    def choose(name, formats, start_in):
        asked.append((name, formats, start_in))
        return answer

    monkeypatch.setattr(hooks, "shell", ScriptedShell(choose_save_path=choose))
    monkeypatch.setattr(
        "libera.host.desktop.open_externally", lambda path: shown.append(path) or True
    )
    return asked, shown


def test_a_print_asks_where_starting_beside_the_document(
    opened: Session, monkeypatch, tmp_path
):
    chosen = tmp_path / "elsewhere" / "Printed.pdf"
    chosen.parent.mkdir()
    asked, shown = printing_where(monkeypatch, str(chosen))

    result = save_document(opened, SaveRequest(file_type=513, printing=True))

    [(name, formats, start_in)] = asked
    assert name == f"{opened.document.stem}.pdf"
    assert start_in == opened.document.parent
    assert [ext for _, ext in formats] == ["pdf"], "a print offers PDF only"
    assert chosen.read_bytes()[:5] == b"%PDF-"
    assert shown == [chosen], "the viewer is handed the file the user kept"
    assert result["path"] == str(chosen)
    assert opened.read_current_document() == opened.document, (
        "a print is not a Save As: the window stays on its document"
    )


def test_a_cancelled_print_makes_nothing(opened: Session, monkeypatch):
    _asked, shown = printing_where(monkeypatch, "")

    assert (
        save_document(opened, SaveRequest(file_type=513, printing=True))["error"] == 1
    )
    assert shown == []


def test_a_print_is_a_pdf_whatever_name_was_typed(
    opened: Session, monkeypatch, tmp_path
):
    _asked, shown = printing_where(monkeypatch, str(tmp_path / "Printed"))

    save_document(opened, SaveRequest(file_type=513, printing=True))

    assert shown == [tmp_path / "Printed.pdf"]
    assert (tmp_path / "Printed.pdf").read_bytes()[:5] == b"%PDF-"


def test_a_print_nothing_opens_is_a_failed_print(opened: Session, monkeypatch):
    """The PDF is made, but nothing will show it: that is not a print."""
    monkeypatch.setattr("libera.host.desktop.open_externally", lambda _p: False)

    assert (
        save_document(opened, SaveRequest(file_type=513, printing=True))["error"] == 2
    )


@pytest.mark.parametrize("app", apps.ALL, ids=lambda a: a.name)
def test_the_format_table_is_what_x2t_really_does(app: apps.App):
    """The tables are documented as measured, not copied out of the header."""
    for wanted, (ext, fmt) in app.formats.items():
        if wanted == 0:
            continue
        assert wanted == fmt, f"{ext} maps to a different id than it is asked for"


def test_a_viewer_refuses_to_save(opened: Session, tmp_path: pathlib.Path):
    """Diagrams has no format x2t will write, so saving stops at the door.

    Error 1 is DesktopOfflineAppDocumentEndSave's "not saved, say nothing".
    """
    viewer = Session(
        payload=opened.payload,
        work=tmp_path / "viewer",
        document=opened.document,
        app=apps.DIAGRAMS,
    )
    sessions.configure(viewer)
    assert save_document(viewer, SaveRequest()) == {"error": 1}


def open_in(app: apps.App, document: pathlib.Path, work: pathlib.Path) -> Session:
    session = Session(
        payload=payload_mod.resolve().root, work=work, document=document, app=app
    )
    sessions.configure(session)
    opening.open_document(session, document)
    return session


CSVS = {
    "utf8-commas.csv": ("Nom,Ville\nÉlodie,Besançon\nZoë,Łódź\n", "utf-8"),
    "cp1252-semicolons.csv": ("Nom;Ville\nÉlodie;Besançon\n", "cp1252"),
    "utf8-tabs.tsv": ("Nom\tVille\nÉlodie\tBesançon\n", "utf-8"),
}


@pytest.mark.parametrize("name", CSVS)
def test_a_csv_opens_and_saves_the_way_it_was_written(tmp_path, name):
    """x2t refused every CSV (rc 88) until it was told how the text is written.

    Saved twice, because x2t's UTF-8 reader took the NULs it leaves past the
    end of the text for one more row: every save added an empty line.
    """
    text, encoding = CSVS[name]
    document = tmp_path / name
    document.write_bytes(text.encode(encoding))

    for n in range(2):
        table = open_in(apps.TABLES, document, tmp_path / f"session{n}")
        assert table.editor_bin.read_bytes()[:5] == b"XLSY;"
        assert save_document(table, SaveRequest()) == {
            "error": 0,
            "path": str(document),
        }

    # x2t starts UTF-8 with a byte-order mark; the rest is what was there.
    assert document.read_bytes().removeprefix(b"\xef\xbb\xbf") == text.encode(encoding)


def test_save_as_tsv_writes_tabs(tmp_path, monkeypatch):
    """The delimiter follows the file being written, not the one that is open."""
    text, encoding = CSVS["cp1252-semicolons.csv"]
    document = tmp_path / "a.csv"
    document.write_bytes(text.encode(encoding))
    chosen = tmp_path / "b.tsv"
    monkeypatch.setattr(
        hooks,
        "shell",
        ScriptedShell(choose_save_path=lambda _name, _formats, _start_in: str(chosen)),
    )
    table = open_in(apps.TABLES, document, tmp_path / "session")

    assert save_document(table, SaveRequest(save_as=True))["error"] == 0
    assert chosen.read_bytes().decode("cp1252") == text.replace(";", "\t")


@pytest.mark.parametrize(
    ("app", "ext"),
    [(apps.WORDS, "odt"), (apps.TABLES, "ods"), (apps.SLIDES, "odp")],
    ids=lambda v: getattr(v, "name", v),
)
def test_plain_save_writes_the_document_in_the_format_it_has(
    open_blank, tmp_path, app, ext
):
    """It used to go into the session as a .docx, and the .odt stayed as it was."""
    blank = open_blank(app)
    document = tmp_path / f"mine.{ext}"
    export(blank, document, app.ids_by_ext[ext], None)
    reopened = open_in(app, document, tmp_path / "reopened")
    before = document.stat().st_mtime_ns

    assert save_document(reopened, SaveRequest()) == {
        "error": 0,
        "path": str(document),
    }
    assert document.stat().st_mtime_ns != before


def test_closing_a_format_it_cannot_write_refuses_rather_than_asks(
    opened: Session, tmp_path
):
    """Closing saves on the GUI thread, where a save panel would wait for itself.

    x2t does not write .doc, so the save has to ask where; from there it fails
    instead, and the window stays open with the edits in it.
    """
    old = tmp_path / "Old.doc"
    old.write_bytes(b"")
    opened.current_file.write_text(str(old), encoding="utf-8")

    assert save_document(opened, SaveRequest(), may_ask=False) == {"error": 2}


def test_a_csv_with_an_emoji_saves_in_utf8(tmp_path):
    """A character outside the BMP, and x2t wrote one byte per character.

    Its converter to UTF-8 sized its buffer one unit per character, an emoji
    needs two, and the fallback wrote "é" as the single byte E9 throughout the
    file -- exiting 0. Patch 0030 fixes it; convert.export still refuses text
    that is not the UTF-8 it asked for, should it come back.
    """
    document = tmp_path / "list.csv"
    document.write_text("Nom,Description\nCleed,🎯 Échange sécurisé\n", "utf-8")
    table = open_in(apps.TABLES, document, tmp_path / "session")

    assert save_document(table, SaveRequest()) == {"error": 0, "path": str(document)}
    assert "Cleed,🎯 Échange sécurisé" in document.read_text(encoding="utf-8-sig")


def test_a_text_file_opens_past_an_emoji(tmp_path):
    """Without a byte-order mark, x2t's reader stopped at the first emoji: the
    same buffer as in the CSV writer, which patch 0030 sizes."""
    document = tmp_path / "notes.txt"
    document.write_text("avant\n🎯 cible\naprès\n", encoding="utf-8")
    notes = open_in(apps.WORDS, document, tmp_path / "session")
    docx = tmp_path / "out.docx"

    export(notes, docx, apps.WORDS.ids_by_ext["docx"], None)
    assert "après" in zipfile.ZipFile(docx).read("word/document.xml").decode()


def read_rtf_text(path: pathlib.Path) -> str:
    """The text of an RTF x2t wrote, which spells every character `\\uN*`."""
    body = path.read_text(encoding="ascii").split("\\fet2", 1)[1]
    return "".join(chr(int(n)) for n in re.findall(r"\\u(\d+)\*", body))


def write_docx_body(blank: pathlib.Path, document: pathlib.Path, body: str) -> None:
    """The blank's package, with `body` for the inside of its w:body."""
    with zipfile.ZipFile(blank) as src, zipfile.ZipFile(document, "w") as dst:
        for item in src.infolist():
            data = src.read(item)
            if item.filename == "word/document.xml":
                data = re.sub(
                    rb"<w:body>.*</w:body>",
                    f"<w:body>{body}</w:body>".encode(),
                    data,
                    flags=re.DOTALL,
                )
            dst.writestr(item, data)


PARAGRAPH = "<w:p><w:r><w:t>{}</w:t></w:r></w:p>"
BREAK = (
    '<w:p><w:pPr><w:sectPr><w:pgSz w:w="11906" w:h="16838"/></w:sectPr></w:pPr></w:p>'
)
SECTIONLESS = {
    "no section": PARAGRAPH.format("après"),
    "a break, then none": BREAK + PARAGRAPH.format("après"),
}


@pytest.mark.parametrize("body", SECTIONLESS.values(), ids=list(SECTIONLESS))
def test_save_as_rtf_keeps_the_text_after_the_last_section(open_blank, tmp_path, body):
    """x2t's RTF writer read paragraphs into sections, made from w:sectPr only.

    A body with no closing w:sectPr lost what followed the last one, all of it
    when there was none, and exited 0 over an RTF of headers. Patch 0033.
    """
    document = tmp_path / "sectionless.docx"
    blank = open_blank(apps.WORDS)
    write_docx_body(blank.document, document, body)
    opened = open_in(apps.WORDS, document, tmp_path / "session")
    rtf = tmp_path / "out.rtf"

    export(opened, rtf, apps.WORDS.ids_by_ext["rtf"], None)
    assert "après" in read_rtf_text(rtf)


def test_a_text_file_saves_as_rtf_with_its_text(tmp_path):
    """x2t's plain text reader writes a body with no w:sectPr, the case above."""
    document = tmp_path / "notes.txt"
    document.write_text("avant\naprès\n", encoding="utf-8")
    notes = open_in(apps.WORDS, document, tmp_path / "session")
    rtf = tmp_path / "out.rtf"

    export(notes, rtf, apps.WORDS.ids_by_ext["rtf"], None)
    assert "après" in read_rtf_text(rtf)


def test_markdown_opens_and_saves(tmp_path):
    """x2t refused every .md without an encoding (rc 88)."""
    document = tmp_path / "notes.md"
    document.write_text("Un *mot* et cœur 🎯\n", encoding="utf-8")
    notes = open_in(apps.WORDS, document, tmp_path / "session")

    assert save_document(notes, SaveRequest()) == {"error": 0, "path": str(document)}
    assert "cœur 🎯" in document.read_text(encoding="utf-8")


# --- x2t's CSV reader skipped a character every 500,000 --------------------
#
# CSVReader drops the text it has read once it passes 500,000 characters, and
# until patch 0029 never looked at the first character after the cut: a quote,
# a delimiter or a newline there split a cell or merged two. Payload 0.3's
# host modelled the loop to name the damaged rows; 0.4's converter reads them.

# 5000 rows of 100 characters: the last newline is character 499,999.
LONG = ("x" * 99 + "\n") * 5000
CUTS = {
    "a quoted cell": LONG + 'k,"a,b",z\n',
    "an empty cell": LONG + "k,,z\n",
    "a quoted row": LONG + 'k\n"a,b",z\n',
    "a blank line": LONG + "k\n\nlast\n",
    "a letter": LONG + "k,yes,z\n",
}


def read_rows(path: pathlib.Path) -> list[list[str]]:
    """The rows, without the empty cells x2t pads a short row with on saving."""
    rows = list(csv.reader(io.StringIO(path.read_text(encoding="utf-8-sig"))))
    for row in rows:
        while row and not row[-1]:
            row.pop()
    return rows


def rows_x2t_changes(document: pathlib.Path, work: pathlib.Path) -> list[int]:
    """The first row x2t's round trip reads differently from the file, if any."""
    table = open_in(apps.TABLES, document, work)
    out = work / "out.csv"
    export(table, out, apps.TABLES.ids_by_ext["csv"], document)
    wanted, got = read_rows(document), read_rows(out)
    for number, row in enumerate(wanted, 1):
        if number > len(got) or got[number - 1] != row:
            return [number]
    return [] if len(got) == len(wanted) else [len(wanted) + 1]


@pytest.mark.parametrize("case", CUTS)
def test_x2t_reads_every_row_of_a_large_csv(tmp_path, case):
    document = tmp_path / "list.csv"
    document.write_text(CUTS[case], encoding="utf-8")

    assert rows_x2t_changes(document, tmp_path / "s") == []
