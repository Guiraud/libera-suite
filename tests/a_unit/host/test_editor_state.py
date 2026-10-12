"""What the editor can do is pushed to the host, not asked for.

A menu is validated on the GUI thread, and asking the editor from there would
deadlock against the thread that would have to answer.
"""

from __future__ import annotations

import json

import pytest

from libera.host import server, session as sessions
from libera.host.server import diagnostics, editor
from libera.host.server.api import Refused, Request
from libera.host.session import Session


@pytest.fixture
def bound_session(tmp_path) -> Session:
    found = Session(payload=tmp_path / "payload", work=tmp_path / "s")
    sessions.configure(found)
    return found


def request(body: bytes, session: Session) -> Request:
    """A request from that session's window."""
    return Request(session, body)


def test_the_editor_reports_what_it_can_do(bound_session):
    server.record_abilities(request(json.dumps({"undo": True}).encode(), bound_session))
    assert sessions.SESSIONS["s"].abilities == {"undo": True}


def test_later_reports_merge_rather_than_replace(bound_session):
    server.record_abilities(request(b'{"undo": true}', bound_session))
    server.record_abilities(request(b'{"redo": true}', bound_session))

    assert sessions.SESSIONS["s"].abilities == {"undo": True, "redo": True}


def test_closing_a_window_forgets_everything_about_it(bound_session):
    """The editor's state, its window, the reload offer: all on the session.

    They were three dictionaries in three modules, and closing a window
    cleared one of them.
    """
    server.record_abilities(request(b'{"undo": true}', bound_session))
    sessions.drop_session("s")

    assert "s" not in sessions.SESSIONS


@pytest.mark.parametrize(
    "body",
    [{"print": True}, {"undo": "yes"}, {"undo": 1}],
    ids=["an ability nobody asks about", "a string", "a number"],
)
def test_only_what_the_menu_asks_about_is_kept(bound_session, body):
    """Any key the page sent was kept, under any value."""
    with pytest.raises(Refused) as refused:
        server.record_abilities(request(json.dumps(body).encode(), bound_session))

    assert refused.value.status == 400
    assert bound_session.abilities == {}


@pytest.mark.parametrize(
    "log",
    [
        {"calls": "LocalStartOpen"},
        {"calls": [{"args": "x"}]},
        {"events": [{"frame": "top", "kind": "error"}]},
        {"events": [{"frame": "top", "kind": 1, "text": "x"}]},
    ],
    ids=["calls a string", "a call with no name", "an event with no text", "a kind"],
)
def test_a_page_log_of_the_wrong_shape_is_a_400(bound_session, log):
    """It was read where each part was first used, so a bad one raised
    halfway, after some of it had been counted."""
    with pytest.raises(Refused) as refused:
        editor.receive_page_log(request(json.dumps(log).encode(), bound_session))

    assert refused.value.status == 400
    assert diagnostics.SEEN == {}


def test_what_the_page_reports_is_bounded(bound_session):
    """Nothing clears it in a process with windows, which runs for days."""
    event = {"frame": "frame", "kind": "console.error", "text": "again"}
    log = {"events": [event] * (diagnostics.ERRORS.maxlen + 10)}

    editor.receive_page_log(request(json.dumps(log).encode(), bound_session))

    assert len(diagnostics.ERRORS) == diagnostics.ERRORS.maxlen
