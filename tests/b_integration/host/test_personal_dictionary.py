"""Add to dictionary, as the host keeps it.

The editor hands the word to AscDesktopEditor.SpellCheck, and the bridge used
to pass it to the spell checker's worker, which handles only checking and
suggesting and dropped it. The word was flagged again next session.
"""

from __future__ import annotations

import json

import pytest


def add(live, word) -> int:
    status, _ = live.post("words", json.dumps({"word": word}).encode())
    return status


def test_an_added_word_is_kept_and_handed_back(live):
    assert add(live, "Frobnitzel") == 204

    assert live.json("words") == ["Frobnitzel"]


def test_a_word_added_twice_is_kept_once(live):
    add(live, "Frobnitzel")
    add(live, "Frobnitzel")

    assert live.json("words") == ["Frobnitzel"]


def test_the_words_outlive_the_session(live):
    """Beside the sessions, like the Recent list: every window, every launch."""
    add(live, "Frobnitzel")

    from libera.host.server import spelling

    kept = spelling.find_personal_words(live.host)
    assert kept.parent == live.host.work.parent
    assert "Frobnitzel" in kept.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "word",
    ["", "two words", "line\nbreak", "x" * 101, 42, None],
    ids=["empty", "space", "newline", "too long", "number", "null"],
)
def test_what_is_not_one_word_is_refused(live, word):
    assert add(live, word) == 400
    assert live.json("words") == []
