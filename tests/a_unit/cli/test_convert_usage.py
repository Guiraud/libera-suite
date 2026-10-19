"""`libera --convert` refuses what it cannot do before it converts anything.

None of these reach x2t, so none needs a payload.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from libera import cli
from libera.cli import commands


def run(argv, capsys):
    code = cli.main(argv)
    return code, capsys.readouterr().err


@pytest.fixture
def docs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for name in ("a.docx", "b.docx", "a.odt", "d.vsdx"):
        (tmp_path / name).write_bytes(b"x")
    return tmp_path


@pytest.mark.parametrize(
    ("argv", "says"),
    [
        (["--convert", "-t", "pdf"], "at least one document"),
        (["--convert", "a.docx"], "-t FORMAT, or -o FILE"),
        (["--convert", "a.docx", "b.docx", "-o", "x.pdf"], "-o names one file"),
        (["--convert", "a.docx", "-o", "x.pdf", "--outdir", "o"], "cannot be used"),
        (["--convert", "a.docx", "-o", "-"], "no format in '-'"),
        (["--convert", "a.docx", "-o", "noext"], "no format in 'noext'"),
        (["a.docx", "-t", "pdf"], "--to goes with --convert"),
        (["a.docx", "--outdir", "o"], "--outdir goes with --convert"),
    ],
)
def test_usage_mistakes_are_refused(docs, capsys, argv, says):
    with pytest.raises(SystemExit) as e:
        cli.main(argv)
    assert e.value.code == 2
    assert says in capsys.readouterr().err


@pytest.mark.parametrize(
    ("argv", "says"),
    [
        (["--convert", "missing.docx", "-t", "pdf"], "no such file"),
        (["--convert", "a.docx", "-t", "xlsx"], "Libera Words cannot write .xlsx"),
        (["--convert", "d.vsdx", "-t", "pdf"], "writes none"),
        (["--convert", "a.docx", "-t", "docx"], "written over itself"),
        (["--convert", "a.docx", "-o", "./a.docx"], "written over itself"),
        (["--convert", "a.docx", "a.odt", "-t", "pdf"], "several documents"),
    ],
)
def test_impossible_conversions_are_refused_before_any_is_made(
    docs, capsys, argv, says
):
    code, err = run(argv, capsys)
    assert code == 1
    assert says in err
    assert not list(docs.glob("*.pdf"))


def test_the_plan_names_each_result_beside_or_in_outdir(docs):
    beside = argparse.Namespace(file=["a.docx"], to=".PDF", output=None, outdir=None)
    assert commands.plan_conversions(beside) == [(Path("a.docx"), Path("a.pdf"), "pdf")]
    into = argparse.Namespace(file=["a.docx"], to="odt", output=None, outdir="o")
    assert commands.plan_conversions(into) == [(Path("a.docx"), Path("o/a.odt"), "odt")]
    out = argparse.Namespace(file=["a.docx"], to="pdf", output="-", outdir=None)
    assert commands.plan_conversions(out) == [(Path("a.docx"), None, "pdf")]


@pytest.mark.parametrize("argv", [["--convert", "--help"], ["-h", "--conv"]])
def test_the_converter_has_a_help_page_of_its_own(capsys, argv):
    """Its options buried the rest of the general help, which now only points
    here."""
    assert cli.main(argv) == 0
    page = capsys.readouterr().out
    assert page.startswith("usage: libera --convert")
    assert "--outdir" in page
    assert "--serve" not in page

    with pytest.raises(SystemExit):
        cli.main(["--help"])
    general = capsys.readouterr().out
    assert "libera --convert --help" in general
    assert "--outdir" not in general


def test_the_help_page_lists_what_each_editor_reads_and_writes(capsys):
    """Read off the same tables the converter checks, so a format it lists is
    one it accepts."""
    cli.main(["--convert", "--help"])
    page = " ".join(capsys.readouterr().out.split())
    assert "Libera Tables reads csv fods numbers" in page
    assert "writes csv ods ots pdf tsv xlsm xlsx" in page
    assert "Libera Diagrams reads vsdm" in page
