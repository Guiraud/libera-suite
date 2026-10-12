"""Who may ask, and what every answer says about itself.

The server is on 127.0.0.1, which every page in every browser on this machine
can reach, so this is security policy, not plumbing.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from libera.host.server.api import Refused
from libera.host.session import NotReadyError, Session, lookup

if TYPE_CHECKING:
    from collections.abc import Mapping

logger = logging.getLogger(__name__)

# Only our own pages may frame ours. Any site could put the start window in an
# iframe, and a click there sends new, open-recent and open-document with our
# origin, which admit() lets through. 'self' and not 'none': the editor
# frames itself.
FRAME_ANCESTORS = "frame-ancestors 'self'"

# On every answer, whichever route or error produced it.
SECURITY_HEADERS = (
    ("Content-Security-Policy", FRAME_ANCESTORS),
    # The declared type is the type: a browser that sniffed text/plain into
    # HTML would undo what the adapter's plain-text refusals guarantee.
    ("X-Content-Type-Options", "nosniff"),
)


def admit(
    *,
    host: str | None,
    origin: str | None,
    fetch_site: str | None,
    port: str,
    query: Mapping[str, list[str]],
) -> Session:
    """The session the request is about, if it may be served at all; refused
    otherwise.

    The server is on 127.0.0.1, which every page in every browser on this
    machine can reach, so what a page elsewhere could send is the question.

    **Host must be this server's address.** A page on a name its author
    controls can re-resolve that name to 127.0.0.1 -- DNS rebinding -- and is
    then same-origin with itself, so it reads every answer: the open document,
    the recent list, any file media-import was told to copy in.

    **Origin, when there is one, must be ours.** A browser sends it with every
    POST another page makes, and a text/plain POST needs no preflight.
    Measured before this check: a request from another origin, with no session
    named, truncated the open document's change log to nothing. Our own pages
    send our origin; the hand-off and the tests send none.

    **Sec-Fetch-Site, when there is one, must say so too.** A GET carries no
    Origin, so another site could load `<script src>` from one of our
    addresses and read what it declares: the bridge's prelude says who has the
    open document locked. The browser marks every request it sends with where
    it came from: "same-origin" from our own pages, "none" from no page at all,
    a navigation the user or the application started. "same-site" is not ours:
    another port on 127.0.0.1 is the same site, and another origin.

    **The session must exist.** Static requests name none and get the first,
    which is harmless because the payload is shared. A request about a
    document names its session, and one that has gone is refused: see
    session.lookup.
    """
    own = f"127.0.0.1:{port}"
    if (
        host != own
        or origin not in {None, f"http://{own}"}
        or fetch_site not in {None, "same-origin", "none"}
    ):
        logger.info(
            "refused: Host %s, Origin %s, Sec-Fetch-Site %s", host, origin, fetch_site
        )
        raise Refused(403)
    try:
        return lookup(query.get("session", [""])[0])
    except NotReadyError as e:
        raise Refused(404, str(e)) from e
