"""build/tests has no __init__.py (its tiers' names would collide with the
application's tests/a_unit and the rest), so pytest imports each test file by
its basename alone, and two files of one name stop the whole collection with
"import file mismatch". This says so at once, naming them."""

from __future__ import annotations

from collections import Counter

from libera_build.repo import REPO

HERE = REPO / "build" / "tests"


def test_every_test_file_name_is_unique_across_the_tiers():
    names = Counter(p.name for p in HERE.glob("*/test_*.py"))
    assert "test_lb_layout.py" in names, "the glob found nothing to compare"
    assert [n for n, count in names.items() if count > 1] == []
