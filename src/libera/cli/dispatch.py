"""The argument parser, and which command each spelling reaches.

Separate from the commands themselves because the surface is the part that has
to stay still: `libera FILE...` opens documents, `libera` alone opens the
start window, and everything else is a flag. There is no `libera words` --
the file picks the editor.

Not `main.py`: `cli` re-exports `main`, and a module of that name would be
shadowed by the function.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import TYPE_CHECKING

from libera import logs, timeline
from libera.cli import commands
from libera.host import about

if TYPE_CHECKING:
    from collections.abc import Callable


def main(argv: list[str] | None = None) -> int:
    timeline.mark("python")
    parser = _make_parser()
    args = parser.parse_args(argv)
    logs.setup(args.verbose, quiet=args.quiet)
    return _choose_command(parser, args)(args)


def _make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="libera",
        description="Libera Suite -- a desktop office suite",
        epilog=(
            "libera FILE...    open documents, one window each\n"
            "libera            the start window: new, open, recent\n"
            "libera --convert *.docx -t pdf    convert, with no window\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("file", nargs="*", help="documents to open, one window each")
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=about.format_version(),
        help="print the version and exit",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="say more: -v what it is doing, -vv how, -vvv every request",
    )
    parser.add_argument("-q", "--quiet", action="store_true", help="errors only")
    _add_payload_options(parser)
    _add_launcher_options(parser)
    parser.add_argument(
        "--diagnose",
        action="store_true",
        help="print what a bug report needs: versions, payload, platform",
    )
    _add_convert_options(parser)
    _add_serve_options(parser)
    return parser


def _add_convert_options(parser: argparse.ArgumentParser) -> None:
    """Pandoc's spellings where pandoc has one: `-t` the format written, `-o`
    the file. No `-f`, which is pandoc's input format: here the extension
    decides that, as it decides the editor."""
    group = parser.add_argument_group("converting without a window")
    group.add_argument(
        "--convert",
        action="store_true",
        help="write each FILE in another format, beside it unless told otherwise",
    )
    group.add_argument(
        "-t", "--to", metavar="FORMAT", help="the format, by extension: pdf, odt, ..."
    )
    group.add_argument(
        "-o",
        "--output",
        metavar="FILE",
        help="for one document: where to write it, - for standard output",
    )
    group.add_argument("--outdir", metavar="DIR", help="write into DIR")


def _add_payload_options(parser: argparse.ArgumentParser) -> None:
    """The payload: fetched, verified and installed separately from the wheel,
    because it is ~120 MB of editor and native binaries. The start window shows
    the same information; these are for scripts and for a machine with no
    window system."""
    group = parser.add_argument_group("the editor payload")
    group.add_argument(
        "--payload-status", action="store_true", help="where the payload resolved from"
    )
    group.add_argument(
        "--payload-install",
        action="store_true",
        help="fetch, verify and install the payload",
    )
    group.add_argument(
        "--payload-remove", action="store_true", help="delete the installed payload"
    )
    group.add_argument(
        "--from",
        dest="source",
        metavar="DIR_OR_URL",
        help="local directory of artifacts, or a base URL (default: the public origin)",
    )
    group.add_argument(
        "--trust-manifest",
        action="store_true",
        help="accept the origin's manifest when the wheel ships none (unverified)",
    )


def _add_launcher_options(parser: argparse.ArgumentParser) -> None:
    """Linux has no application bundle to carry this, so it is a command. The
    Flatpak installs the same entry itself and says so rather than doing it
    twice."""
    group = parser.add_argument_group("the Linux launcher")
    group.add_argument(
        "--launcher-install",
        action="store_true",
        help="put Libera Suite in the launcher, with an icon and Open With",
    )
    group.add_argument(
        "--launcher-remove",
        action="store_true",
        help="take the desktop entry and its icon away",
    )


def _add_serve_options(parser: argparse.ArgumentParser) -> None:
    group = parser.add_argument_group("serving without a window")
    group.add_argument(
        "--serve",
        action="store_true",
        help="serve the editor over HTTP and print its URL; used by the tests",
    )
    group.add_argument("--port", type=int, help=f"default: {commands.SERVE_PORT}")
    group.add_argument("--work", help="session state directory")
    group.add_argument("--shot", help="where the page posts its own render")


def _choose_command(
    parser: argparse.ArgumentParser, args: argparse.Namespace
) -> Callable[[argparse.Namespace], int]:
    """The one command this run asked for: a flag, or opening documents.

    Checked here rather than made impossible by argparse, because
    mutually_exclusive_group cannot span argument groups and the error it
    gives is worse than these.
    """
    chosen = _find_command_flags(args)
    if len(chosen) > 1:
        names = " and ".join(flag for flag, _ in chosen)
        parser.error(f"{names} cannot be used together")
    flag, run = chosen[0] if chosen else (None, commands.open_documents)

    # Options that belong to one command, which every other ignored without a
    # word: `libera --from ./dist` opened the start window, and offered to
    # download from the default origin.
    owned = (
        ("--from", "--payload-install", args.source is not None),
        ("--trust-manifest", "--payload-install", args.trust_manifest),
        ("--port", "--serve", args.port is not None),
        ("--work", "--serve", args.work is not None),
        ("--shot", "--serve", args.shot is not None),
        ("--to", "--convert", args.to is not None),
        ("--output", "--convert", args.output is not None),
        ("--outdir", "--convert", args.outdir is not None),
    )
    for option, owner, given in owned:
        if given and owner != flag:
            parser.error(f"{option} goes with {owner}")

    # The one command whose arity the parser cannot express: `file` is
    # variadic because opening documents is the default.
    if flag == "--serve" and len(args.file) != 1:
        parser.error("--serve takes exactly one document")
    if flag == "--convert":
        _check_convert(parser, args)
    return run


def _check_convert(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    """What `--convert` needs, which is mostly what to call the result."""
    args.file = commands.expand_wildcards(args.file)
    if not args.file:
        parser.error("--convert needs at least one document")
    if args.output is None and args.to is None:
        parser.error("--convert needs -t FORMAT, or -o FILE")
    if args.output is None:
        return
    if len(args.file) > 1:
        parser.error("-o names one file; for several documents, use -t and --outdir")
    if args.outdir is not None:
        parser.error("-o and --outdir cannot be used together")
    if args.to is None and not Path(args.output).suffix:
        parser.error(f"no format in {args.output!r}: add -t FORMAT")


def _find_command_flags(
    args: argparse.Namespace,
) -> list[tuple[str, Callable[[argparse.Namespace], int]]]:
    """Every command flag given, with the command it runs.

    One table saying which spellings are commands, read by both the
    exclusivity check and the dispatch: they were two lists of the same names,
    and nothing made them agree. Built at the call, so a command replaced in
    `commands` is the one that runs.
    """
    table = (
        ("--diagnose", args.diagnose, commands.diagnose),
        ("--payload-status", args.payload_status, commands.show_payload_status),
        ("--payload-install", args.payload_install, commands.install_payload),
        ("--payload-remove", args.payload_remove, commands.remove_payload),
        ("--launcher-install", args.launcher_install, commands.install_launcher),
        ("--launcher-remove", args.launcher_remove, commands.remove_launcher),
        ("--serve", args.serve, commands.serve),
        ("--convert", args.convert, commands.convert_documents),
    )
    return [(flag, run) for flag, on, run in table if on]
