"""One instance at a time, claimed before either launch has said where it is.

Explorer starts a process per file of a multi-selection, and the first says
where it is only once its window exists, so all of them found nobody to hand
off to and each ran on its own: two instances shared one session directory,
and each swept away the other's live sessions.
"""

from __future__ import annotations

import pytest

from libera.host import instance


@pytest.fixture
def claimed():
    """The claim, held by "another launch" for the length of the test."""
    held = instance.claim()
    assert held is not None
    yield held
    held.close()


def test_the_claim_is_one_process_at_a_time(claimed):
    assert instance.claim() is None


def test_the_claim_is_free_again_once_its_holder_lets_go():
    held = instance.claim()
    assert held is not None
    held.close()

    again = instance.claim()

    assert again is not None
    again.close()


def test_a_launch_that_finds_the_claim_free_becomes_the_instance():
    held = instance.become([])

    assert held is not None
    held.close()


def test_a_launch_that_lost_the_claim_hands_off_once_the_instance_answers(
    claimed, tmp_path, monkeypatch
):
    asked: list[list] = []

    def answers_on_the_third(documents):
        asked.append(documents)
        return len(asked) == 3

    monkeypatch.setattr(instance, "hand_off", answers_on_the_third)
    monkeypatch.setattr(instance, "CLAIM_POLL", 0.01)

    assert instance.become([tmp_path / "a.docx"]) is None
    assert len(asked) == 3


def test_a_claimant_that_never_answers_is_said_so(claimed, monkeypatch):
    monkeypatch.setattr(instance, "hand_off", lambda _documents: False)
    monkeypatch.setattr(instance, "CLAIM_WAIT", 0.05)
    monkeypatch.setattr(instance, "CLAIM_POLL", 0.01)

    with pytest.raises(instance.BusyError, match="has not answered"):
        instance.become([])
