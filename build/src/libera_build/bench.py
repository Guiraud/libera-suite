"""How long Libera takes to put a document on screen, stage by stage.

    lb bench [DOC...] [--runs N] [--app PATH/Libera.app]

Starts the real application (its window, its webview) on each document, and
reads the stages it reaches from the trace LIBERA_STARTUP_TRACE asks it to
write (src/libera/timeline.py):

    python         the interpreter is up and `libera` imported
    host           the GUI host's modules imported, run() started
    converted      x2t has made Editor.bin
    window         the first window exists
    gui-loop       the toolkit's event loop runs
    first-request  the webview asked the server for something
    editor-ready   the editor says the document is laid out

Each document runs in a home directory of its own, so nothing touches your
sessions or a Libera you have open. That does not empty WebKit's cache, which
macOS keeps under the real home whatever HOME says, by bundle ID: for this
checkout's interpreter, ~/Library/Caches/org.python.python/WebKit, shared with
every `libera` run from a terminal. So these are usual launches, cache warm;
run 1 differs only by what the system itself has cached.

Without DOCs: the blank Words document and the test sample with a picture.
With --app, the bundle's own executable instead of this checkout's
interpreter, and its own payload. See notes/21-startup-and-size.md.
"""

from __future__ import annotations

import argparse
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from libera import payload
from libera_build.repo import REPO

STAGES = (
    "python",
    "host",
    "converted",
    "window",
    "gui-loop",
    "first-request",
    "editor-ready",
)
# Long enough for a cold first launch on a slow machine; a run that takes it is
# reported, not hidden.
TIMEOUT = 90.0


def make_default_documents(into: Path) -> list[Path]:
    blank = into / "blank.docx"
    shutil.copy(payload.resolve().root / "empty" / "new.docx", blank)
    sample = into / "sample-with-picture.docx"
    subprocess.run(
        [
            sys.executable,
            str(REPO / "tests/support/make_sample_docx.py"),
            str(sample),
            "--image",
        ],
        check=True,
    )
    return [blank, sample]


def run_once(command: list[str], document: Path, home: Path) -> dict[str, float]:
    trace = home / "startup.trace"
    trace.unlink(missing_ok=True)
    env = {**os.environ, "HOME": str(home), "LIBERA_STARTUP_TRACE": str(trace)}
    started = time.time()
    process = subprocess.Popen(
        [*command, str(document)],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    reached: dict[str, float] = {}
    try:
        while time.time() - started < TIMEOUT and "editor-ready" not in reached:
            if trace.exists():
                for line in trace.read_text(encoding="utf-8").splitlines():
                    at, stage = line.split(" ", 1)
                    reached[stage] = float(at) - started
            time.sleep(0.02)
    finally:
        process.terminate()
        process.wait(timeout=10)
    return reached


def show(name: str, runs: list[dict[str, float]]) -> None:
    print(f"\n{name}")
    print(f"  {'':14}" + "".join(f"{'run ' + str(i + 1):>9}" for i in range(len(runs))))
    for stage in STAGES:
        cells = "".join(
            f"{r[stage]:8.2f}s" if stage in r else f"{'--':>9}" for r in runs
        )
        print(f"  {stage:14}{cells}")
    ready = [r["editor-ready"] for r in runs if "editor-ready" in r]
    missed = len(runs) - len(ready)
    print(
        f"  editor ready, median {statistics.median(ready):.2f}s" if ready else "",
        f"({missed} run(s) not ready within {TIMEOUT:.0f}s)" if missed else "",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("documents", nargs="*", type=Path)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--app", type=Path, help="a built Libera.app")
    args = parser.parse_args(argv)

    with tempfile.TemporaryDirectory(prefix="libera-bench-") as scratch_name:
        scratch = Path(scratch_name)
        documents = [d.resolve() for d in args.documents] or make_default_documents(
            scratch
        )
        if args.app:
            command = [str(args.app.resolve() / "Contents" / "MacOS" / "Libera")]
        else:
            command = [sys.executable, "-m", "libera"]
            # The scratch home hides the installed payload: name it.
            os.environ.setdefault("LIBERA_PAYLOAD", str(payload.resolve().root))
        for document in documents:
            home = scratch / f"home-{document.stem}"
            home.mkdir()
            runs = [run_once(command, document, home) for _ in range(args.runs)]
            show(f"{document.name} ({document.stat().st_size // 1024} KB)", runs)
    return 0


if __name__ == "__main__":
    sys.exit(main())
