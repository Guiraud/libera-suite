"""Help says where the documentation is when it cannot open a browser.

`show_help` asked the desktop to open the docs and threw away the answer. On a
machine where opening fails -- a Flatpak whose portal finds no handler, a
desktop with nothing registered for https -- the menu item did nothing at all,
which is the hardest kind of bug for a user to report.

It went through `webbrowser.open` at first, which made the fallback
unreachable: that reports success for a browser it merely spawned. See
test_desktop_open_url.py.

Both directions matter. Saying nothing when the browser opened would be noise
on every machine that works.
"""

from __future__ import annotations

import pytest

from libera.host import desktop, language
from libera.host.menu import actions
from libera.host.window import dialogs


@pytest.fixture
def messages(monkeypatch):
    """Whatever `_open_help` would have put on screen."""
    said: list[tuple[str, str]] = []
    monkeypatch.setattr(dialogs, "say", lambda h, d: said.append((h, d)))
    return said


def browser(monkeypatch, *, works: bool):
    """A desktop that does or does not open what it is given."""
    opened: list[str] = []

    def fake_open(url: str) -> bool:
        opened.append(url)
        return works

    monkeypatch.setattr(desktop, "open_url", fake_open)
    return opened


def test_no_browser_gets_the_url_on_screen(monkeypatch, messages):
    opened = browser(monkeypatch, works=False)

    actions._open_help()

    assert opened == [actions.find_help_url()], "it did not try to open anything"
    assert messages, "nothing told the user, so Help did nothing visible"
    heading, detail = messages[0]
    assert actions.find_help_url() in detail, (
        f"the message has to carry the URL, or it is no better than silence: {detail!r}"
    )
    assert heading, "an alert with no heading"


def test_a_working_browser_says_nothing(monkeypatch, messages):
    browser(monkeypatch, works=True)

    actions._open_help()

    assert not messages, (
        "it reported a failure after the browser opened, which would fire on "
        "every machine where Help works"
    )


@pytest.mark.parametrize(
    ("tag", "edition"), [("fr-CA", "fr"), ("en-FR", "en"), ("pt-BR", "en")]
)
def test_help_opens_the_edition_in_the_interface_language(monkeypatch, tag, edition):
    monkeypatch.setattr(language, "get_language", lambda: tag)
    assert actions.find_help_url() == f"{actions.HELP_URL}{edition}/"
