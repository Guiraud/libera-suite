"""What the application runs as it quits on macOS, where start() never returns.

Cmd-Q is pywebview's `terminate:`, and AppKit ends the process inside the GUI
loop: the way out written after start() never ran, and every document's lock
file stayed behind. `on_quit` hangs that way out on the notification AppKit
posts just before it ends the process; this posts it.
"""

from __future__ import annotations

import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "darwin", reason="AppKit")

if sys.platform == "darwin":
    from libera.host.window import macos


def test_the_work_runs_when_the_application_says_it_will_terminate():
    import AppKit
    import Foundation

    ran: list[str] = []
    macos.on_quit(lambda: ran.append("let go"))

    # Delivered at once, on this thread: the observer names no queue. From an
    # object of the test's own, so that AppKit's observers of NSApp stay out.
    Foundation.NSNotificationCenter.defaultCenter().postNotificationName_object_(
        AppKit.NSApplicationWillTerminateNotification, Foundation.NSObject.new()
    )

    assert ran == ["let go"]
