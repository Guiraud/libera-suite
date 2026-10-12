"""The work of each phase, grouped by where it runs.

update      sends this commit to every builder
builders    build and bundles: `lb` on the builders, in parallel
here        native and wheel: on this machine
publishing  collect, push, check, publish, verify: the origin and PyPI
"""
