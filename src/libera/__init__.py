"""Libera Suite.

Empty on purpose. The console script is `libera.cli:main`, not a re-export
here: importing `libera` must stay cheap, because the build tooling imports
`libera.manifest` on machines with no virtualenv, where the CLI's imports
(pywebview, the GUI) are not there. This file also runs inside the build
container, whose Python is 3.10. See notes/plans/build-tooling.md.
"""
