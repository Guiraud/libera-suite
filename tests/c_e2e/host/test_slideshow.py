"""Starting a slideshow, which is the first thing in Slides that is not typing.

`Show from the beginning` was a TypeError and an asc_onError -25: sdkjs calls
AscDesktopEditor.SetFullscreen guarded on nothing but the bridge existing, and
the bridge did not have it. Nothing in the suite drove a toolbar button, so
nothing caught it.

The button is real and so is the click. #slot-btn-dt-start-over has been
stable across the editors we ship; if upstream renames it this test fails
loudly, which is the right way to find out.
"""

from __future__ import annotations

import shutil

import pytest

from libera import payload as payload_mod

LOUD = ("error", "reject", "asc_onError")


@pytest.fixture
def slides(editor_with, tmp_path):
    """Slides, open on the payload's blank deck, in a real browser.

    Ready when the document is laid out and the load mask is down, as every
    editor here is: it waited for `Asc.editor` and then slept three seconds,
    which is the condition tests/c_e2e/host/conftest.py says is wrong.
    """
    deck = tmp_path / "deck.pptx"
    shutil.copyfile(payload_mod.resolve().root / "empty" / "new.pptx", deck)
    return editor_with([], deck)


def loud_errors(report: dict) -> list[str]:
    return [
        f"{e['kind']}: {e['text'].splitlines()[0][:160]}"
        for e in report["errors"]
        if e["kind"] in LOUD
    ]


def start_the_show(slides) -> None:
    """Click, and wait for sdkjs to ask the host for the screen."""
    with slides.answered("fullscreen"):
        slides.frame.locator("#slot-btn-dt-start-over").click()


def end_the_show(slides) -> None:
    """Leave the slideshow, which is where the presenter window is torn down.

    Escape, not a click on the canvas: measured, both reach
    DemonstrationReporterEnd, and the preview element that takes the click is
    not the one with the id that looks right (#presentation-preview is an
    empty shell; #pe-preview is the visible one). Leaving gives the screen
    back, which is the request waited for.
    """
    with slides.answered("fullscreen"):
        slides.page.keyboard.press("Escape")


def quiet_since(slides) -> list[str]:
    """The loud errors, once what was just done has had its moment to throw.

    An error that is not raised has no event to wait for, so this waits a
    fixed time after the action's own request was answered, then has the page
    post everything it saw.
    """
    slides.wait_for_nothing()
    return loud_errors(slides.reported())


def test_ending_a_slideshow_does_not_raise(slides):
    """The reported bug: clicking past the last slide.

    sdkjs tears the presenter window down on the way out -- endReporter --
    guarded on nothing but the bridge existing. It threw, the editor raised
    asc_onError, and the user got two dialogs for one fault.
    """
    start_the_show(slides)
    end_the_show(slides)

    assert quiet_since(slides) == []


def test_show_from_the_beginning_does_not_raise(slides):
    """The bug, exactly: a TypeError the moment the slideshow starts."""
    assert loud_errors(slides.report()) == [], "broken before the click"

    start_the_show(slides)

    assert quiet_since(slides) == []


def test_show_from_the_beginning_asks_the_host_for_fullscreen(slides):
    """sdkjs asks the host to take the window over, and means it.

    With no window -- this server has none -- the host says nothing happened
    and the show runs where it is. What matters is that the call arrives.
    """
    start_the_show(slides)

    assert slides.asked_for("fullscreen") == 1


def test_the_bridge_carries_the_method_sdkjs_calls_unguarded(slides):
    """sdkjs guards on `undefined !== window.AscDesktopEditor` and no further.

    The bridge's Proxy returns undefined for anything it does not implement,
    which is right for a feature check and a TypeError for a call like this
    one.
    """
    kind = slides.frame.evaluate("() => typeof window.AscDesktopEditor.SetFullscreen")
    assert kind == "function"
