"""A port for a test server, which nothing else is listening on, and the key
the host's server wants on every request (see `server.admission`)."""

from __future__ import annotations

import socket

from libera.host import instance
from libera.host.server import admission


def find_free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def keyed(url: str, key: str = instance.TOKEN) -> str:
    """The URL with the key in it, the way a window's first URL has it. A
    server in a subprocess has a key of its own, read off the URL it printed."""
    return f"{url}{'&' if '?' in url else '?'}key={key}"


def key_cookie(key: str = instance.TOKEN) -> dict[str, str]:
    """The header the page sends the key in, once its first answer set it."""
    return {"Cookie": f"{admission.KEY_COOKIE}={key}"}
