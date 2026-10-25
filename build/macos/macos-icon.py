"""Draw the application icon into a .icns.

One drawing, rasterised at every size macOS asks for. The drawing is
src/libera/icon.svg -- the same file the Flatpak exports as its icon and the
same one the host sets as the Dock icon at runtime, so the three cannot drift.

The drawing code is `libera.macos_app.write_icns`, which
`libera --launcher-install` uses for the Libera.app it builds from a wheel.
One copy, so the two bundles wear the same icon.

NSImage has rasterised SVG since macOS 13. Nothing else here can, so a build
machine older than that will fail at the first draw rather than produce a
blank icon -- which is the right way round.
"""

from __future__ import annotations

import pathlib
import sys

from libera.macos_app import write_icns


def main() -> int:
    out = pathlib.Path(sys.argv[1])
    try:
        write_icns(out)
    except RuntimeError as e:
        print(f"FATAL: {e}", file=sys.stderr)
        return 1
    print(f"    {out} ({out.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
