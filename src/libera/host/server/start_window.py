"""The start window: its page, the editors it offers, and where the payload
came from.
"""

from __future__ import annotations

import json
import pathlib

from libera.host import apps
from libera.host.server.api import Request, Response, answer_json, endpoint


@endpoint("GET", "start")
def serve_start(_r: Request) -> Response:
    """The start window's page, ours: the payload has none.

    Upstream keeps its start screen in the C++ shell, so there is nothing to
    reuse: this is a plain page served by the host, talking to the same
    /__host__/ endpoints the editor does. It loads none of the bridge, sdkjs
    or the theme.
    """
    page = pathlib.Path(__file__).with_name("start-window.html").read_bytes()
    return Response(body=page, content_type="text/html; charset=utf-8")


@endpoint("GET", "apps")
def serve_apps(_r: Request) -> Response:
    """The editors, for a page that offers to make a new document."""
    body = [
        {
            "name": app.name,
            "kind": app.noun,
            "doctype": app.doctype,
            "ext": app.ext,
            "creates": app.blank is not None,
        }
        for app in apps.ALL
    ]
    return answer_json(body)


@endpoint("GET", "payload")
def serve_payload(r: Request) -> Response:
    """Where the payload came from, for the start window to show.

    The same facts `libera --payload-status` prints. Read from the installed
    payload's own payload.json, so a development tree reports that it
    knows nothing.
    """
    # Imported here, since this is the only thing that wants the installer and
    # `libera --serve` runs the host without it.
    from libera import payload as payload_mod

    # Unreadable is not the same as absent: a payload.json that will not parse
    # was shown as "local build", which is what a tree with none is told.
    marker = r.session.layout.record
    info = json.loads(marker.read_text(encoding="utf-8")) if marker.is_file() else {}
    body = {
        "root": str(r.session.payload),
        # How this process found it -- LIBERA_PAYLOAD, a config file, or the
        # installed copy -- which is not in payload.json because it is not a
        # property of the payload.
        "origin": payload_mod.resolve().origin,
        "version": info.get("payload_version") or "local build",
        "platform": info.get("platform"),
        "built": info.get("built"),
    }
    return answer_json(body)
