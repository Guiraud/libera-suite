"""`libera --launcher-install` on macOS: a Libera.app for this install.

A `pipx`, `uv tool` or Homebrew install gets a command and nothing else: no
icon in Launchpad, no Libera Suite in Finder's Open With, and a double-clicked
`.docx` that opens in whatever had it before. `build/macos/macos-app.sh`
answers that from a checkout. This answers it from the wheel, for the
interpreter that is running now, so it needs neither the repository nor uv.

It writes one bundle, per user and never system-wide:

    ~/Applications/Libera.app

`~/Applications` is the folder Finder, Spotlight and Launchpad already index
for one account, and writing to /Applications would need an administrator for
something that belongs to one user.

**The executable is compiled here, from `launcher.m`.** It cannot be a script:
a script that exec's Python hands the process to Python.app, and the
open-document Apple Event goes to a bundle that no longer exists (the full
account is at the top of launcher.m). So this needs clang, which every
Homebrew machine has, since Homebrew requires the Command Line Tools. Without
it, `explain_unsupported()` says how to get it before anything is written.

**The paths baked in are the stable ones.** The bundle runs the interpreter of
the virtualenv that holds `libera`, not its resolved target: resolving it
would skip the pyvenv.cfg that finds the package. And under Homebrew both that
interpreter and the Python library sit in a versioned Cellar directory, which
`brew upgrade` deletes; their `opt/` links survive it, so the bundle names
those wherever they exist.
"""

from __future__ import annotations

import logging
import os
import plistlib
import re
import shutil
import subprocess
import sys
import sysconfig
import tempfile
from importlib import resources
from pathlib import Path

from libera.host import about

logger = logging.getLogger(__name__)

APP_ID = "eu.liberasuite.Libera"

LSREGISTER = Path(
    "/System/Library/Frameworks/CoreServices.framework/Frameworks/"
    "LaunchServices.framework/Support/lsregister"
)

# The last value measured on the shipped x2t, for when there is none to ask.
# See _read_min_macos.
FALLBACK_MIN_MACOS = "14.0"

# The same three dicts as the Info.plist macos-app.sh writes, which explains
# every choice in them; tests/a_unit/test_macos_app.py holds the two equal.
DOCUMENT_TYPES = [
    (
        "Word Document",
        [
            "org.openxmlformats.wordprocessingml.document",
            "org.oasis-open.opendocument.text",
            "public.rtf",
            "public.plain-text",
        ],
    ),
    (
        "Spreadsheet",
        [
            "org.openxmlformats.spreadsheetml.sheet",
            "org.oasis-open.opendocument.spreadsheet",
            "public.comma-separated-values-text",
            "public.tab-separated-values-text",
        ],
    ),
    (
        "Presentation",
        [
            "org.openxmlformats.presentationml.presentation",
            "org.oasis-open.opendocument.presentation",
        ],
    ),
]

# Icon sizes and inset, as in build/macos/macos-icon.py, which calls write_icns.
ICON_SIZES = [16, 32, 64, 128, 256, 512, 1024]
ICON_MARGIN = 100 / 1024


def get_app_path() -> Path:
    return Path.home() / "Applications" / "Libera.app"


def is_installed() -> bool:
    return (get_app_path() / "Contents" / "Info.plist").is_file()


def find_compiler() -> str | None:
    """clang, through xcrun when there is one, so the SDK comes with it."""
    xcrun = shutil.which("xcrun")
    if xcrun:
        result = subprocess.run(
            [xcrun, "--find", "clang"], capture_output=True, text=True, check=False
        )
        found = result.stdout.strip()
        if result.returncode == 0 and found:
            return found
    return shutil.which("clang")


def explain_unsupported() -> str | None:
    """None when a Libera.app can be made here; otherwise what to say."""
    if ".app/Contents/" in sys.executable:
        return "this is already running from an application bundle"
    if find_compiler() is None:
        return (
            "building Libera.app needs clang; install the Command Line Tools "
            "with: xcode-select --install"
        )
    return None


def _stable(path: Path) -> Path:
    """Homebrew's `opt/<name>` link for a path inside `Cellar/<name>/<version>`.

    `brew upgrade` removes the versioned directory, and a bundle naming it
    stops launching. Any other path is returned as it is.
    """
    match = re.match(
        r"^(?P<root>.*)/Cellar/(?P<name>[^/]+)/[^/]+/(?P<rest>.*)$", str(path)
    )
    if match is None:
        return path
    opt = Path(match["root"]) / "opt" / match["name"] / match["rest"]
    return opt if opt.exists() else path


def get_interpreter() -> Path:
    """The python3 the bundle runs as: this one, unresolved."""
    return _stable(Path(sys.executable).absolute())


def get_python_library() -> Path:
    """The library the launcher embeds: the framework binary, or libpython."""
    v = sysconfig.get_config_var
    if v("PYTHONFRAMEWORK"):
        lib = Path(sys.base_prefix) / v("PYTHONFRAMEWORK")
    else:
        lib = Path(v("LIBDIR")) / v("LDLIBRARY")
    return _stable(Path(os.path.realpath(lib)))


def _read_min_macos() -> str:
    """LSMinimumSystemVersion, read off x2t as macos-app.sh does."""
    try:
        from libera import payload

        x2t = payload.resolve().x2t
        out = subprocess.run(
            ["otool", "-l", str(x2t)], capture_output=True, text=True, check=True
        ).stdout
    except (RuntimeError, OSError, subprocess.CalledProcessError) as e:
        logger.info("no x2t to read a minimum macOS from (%s)", e)
        return FALLBACK_MIN_MACOS
    seen = False
    for line in out.splitlines():
        words = line.split()
        if "LC_BUILD_VERSION" in words:
            seen = True
        elif seen and words[:1] == ["minos"]:
            return words[-1]
    return FALLBACK_MIN_MACOS


def render_info_plist(min_macos: str) -> bytes:
    version = about.app_version()
    info = {
        "CFBundleName": "Libera",
        "CFBundleDisplayName": "Libera Suite",
        "CFBundleIdentifier": APP_ID,
        "CFBundleExecutable": "Libera",
        "CFBundleIconFile": "Libera.icns",
        "CFBundlePackageType": "APPL",
        # Without it AppKit never finishes launching and no document arrives.
        "NSPrincipalClass": "NSApplication",
        "CFBundleShortVersionString": version,
        "CFBundleVersion": version,
        "LSMinimumSystemVersion": min_macos,
        "NSHighResolutionCapable": True,
        "NSHumanReadableCopyright": about.COPYRIGHT,
        "CFBundleDocumentTypes": [
            {
                "CFBundleTypeName": name,
                "CFBundleTypeRole": "Editor",
                "LSHandlerRank": "Alternate",
                "LSItemContentTypes": types,
            }
            for name, types in DOCUMENT_TYPES
        ],
    }
    return plistlib.dumps(info)


def write_icns(out: Path) -> None:
    """Rasterise icon.svg into an .icns. NSImage reads SVG from macOS 13."""
    import AppKit
    import Foundation

    svg = resources.files("libera") / "icon.svg"
    image = AppKit.NSImage.alloc().initWithContentsOfFile_(str(svg))
    if image is None:
        msg = f"could not read {svg} as an image (macOS 13 or later)"
        raise RuntimeError(msg)

    def draw(size: int) -> bytes:
        rep = AppKit.NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(
            None, size, size, 8, 4, True, False, AppKit.NSDeviceRGBColorSpace, 0, 0
        )
        ctx = AppKit.NSGraphicsContext.graphicsContextWithBitmapImageRep_(rep)
        AppKit.NSGraphicsContext.saveGraphicsState()
        AppKit.NSGraphicsContext.setCurrentContext_(ctx)
        inset = round(size * ICON_MARGIN)
        body = Foundation.NSMakeRect(inset, inset, size - 2 * inset, size - 2 * inset)
        image.drawInRect_fromRect_operation_fraction_(
            body, Foundation.NSZeroRect, AppKit.NSCompositingOperationSourceOver, 1.0
        )
        AppKit.NSGraphicsContext.restoreGraphicsState()
        return bytes(rep.representationUsingType_properties_(AppKit.NSPNGFileType, {}))

    with tempfile.TemporaryDirectory() as tmp:
        iconset = Path(tmp) / "Libera.iconset"
        iconset.mkdir()
        for size in ICON_SIZES:
            png = draw(size)
            (iconset / f"icon_{size}x{size}.png").write_bytes(png)
            # Retina variants are the same pixels under another name.
            half = size // 2
            if half in ICON_SIZES:
                (iconset / f"icon_{half}x{half}@2x.png").write_bytes(png)
        subprocess.run(
            ["iconutil", "-c", "icns", str(iconset), "-o", str(out)], check=True
        )


def compile_launcher(out: Path, python: Path, library: Path) -> None:
    """launcher.m into `out`, embedding `library` and running as `python`."""
    clang = find_compiler()
    if clang is None:
        msg = "no clang: xcode-select --install"
        raise RuntimeError(msg)
    include = sysconfig.get_paths()["include"]
    with resources.as_file(resources.files("libera") / "launcher.m") as source:
        subprocess.run(
            [
                clang,
                "-O2",
                "-Wall",
                "-Werror",
                "-framework",
                "Cocoa",
                f"-I{include}",
                str(library),
                f'-DLIBERA_PYTHON="{python}"',
                "-o",
                str(out),
                str(source),
            ],
            check=True,
        )
    # The library records its install name, not the path it was linked from;
    # point the load command at the file itself, then re-sign, because arm64
    # runs nothing unsigned and the edit voids the linker's ad-hoc signature.
    listing = subprocess.run(
        ["otool", "-L", str(out)], capture_output=True, text=True, check=True
    ).stdout.splitlines()[1:]
    recorded = next((line.split()[0] for line in listing if "ython" in line), None)
    if recorded and recorded != str(library):
        subprocess.run(
            ["install_name_tool", "-change", recorded, str(library), str(out)],
            check=True,
            capture_output=True,
        )
        subprocess.run(["codesign", "--force", "--sign", "-", str(out)], check=True)


def _register(app: Path, *, unregister: bool = False) -> None:
    """Tell LaunchServices now, or Open With waits for the next login."""
    if not LSREGISTER.exists():
        return
    flag = "-u" if unregister else "-f"
    subprocess.run([str(LSREGISTER), flag, str(app)], check=False, capture_output=True)


def _assemble(app: Path) -> None:
    contents = app / "Contents"
    (contents / "MacOS").mkdir(parents=True)
    (contents / "Resources").mkdir()
    write_icns(contents / "Resources" / "Libera.icns")
    compile_launcher(
        contents / "MacOS" / "Libera", get_interpreter(), get_python_library()
    )
    (contents / "Info.plist").write_bytes(render_info_plist(_read_min_macos()))


def install() -> list[Path]:
    """Build the bundle beside its destination, then swap it in.

    An install that fails half-way leaves the previous Libera.app as it was.
    """
    app = get_app_path()
    app.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".Libera-", dir=app.parent)) / "Libera.app"
    try:
        _assemble(staging)
    except subprocess.CalledProcessError as e:
        shutil.rmtree(staging.parent, ignore_errors=True)
        # The tool has already said why on stderr; this names which one.
        msg = f"{Path(e.cmd[0]).name} failed (exit {e.returncode})"
        raise RuntimeError(msg) from e
    except BaseException:
        shutil.rmtree(staging.parent, ignore_errors=True)
        raise
    if app.exists():
        shutil.rmtree(app)
    staging.rename(app)
    shutil.rmtree(staging.parent, ignore_errors=True)
    _register(app)
    return [app]


def remove() -> list[Path]:
    app = get_app_path()
    if not app.exists():
        return []
    _register(app, unregister=True)
    shutil.rmtree(app)
    return [app]
