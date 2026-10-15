"""The host API's vocabulary: what an endpoint is, what it is handed, and what
it hands back.

An endpoint is a function marked `@endpoint(method, name)`, from a Request to
a Response. Both are plain values, so an endpoint knows nothing of HTTP's
machinery or of the framework under it: `adapter` is the only module that
does, building a Request from the framework's request and turning a Response
into the framework's. Swapping the framework changes that module and nothing
here.

The session travels inside the Request, as an argument. Nothing finds one on
the thread: see notes/lessons-learned/threads.md.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    import pathlib
    from collections.abc import Callable, Mapping

    from libera.host.session import Session

T = TypeVar("T")


class Refused(Exception):
    """This request will not be served: the status, and why.

    Every way a request is refused goes through this exception: by an endpoint,
    by admission, or for a body that was not what the endpoint reads. That keeps
    an endpoint's return value always its answer, with `adapter` turning the
    exception into one in one place.
    """

    def __init__(self, status: int, explain: str = "") -> None:
        super().__init__(f"{status} {explain}".strip())
        self.status = status
        self.explain = explain


@dataclass(frozen=True)
class Request:
    """One request, as an endpoint needs it."""

    session: Session
    body: bytes = b""
    query: Mapping[str, list[str]] = field(default_factory=dict)
    # `name` is what it was reached by, `path` what follows a prefix route's name:
    # "bridge-page.js", or "photo.png" for media/photo.png.
    name: str = ""
    path: str = ""

    def get_query(self, name: str, default: str = "") -> str:
        """The first value of a query parameter."""
        return self.query.get(name, [default])[0]

    def read_json(self) -> dict:
        """The body as a JSON object; otherwise refused, with a 400.

        Read with `json.loads` at each endpoint, a body that was not an object
        -- not JSON, a list, nothing at all -- raised wherever the endpoint
        first used it, closing the request with no answer.
        """
        try:
            found = json.loads(self.body or b"{}")
        except ValueError as e:
            msg = "the body is not JSON"
            raise Refused(400, msg) from e
        if not isinstance(found, dict):
            msg = "the body is not a JSON object"
            raise Refused(400, msg)
        return found

    def read_field(self, name: str, kind: type[T], default: T | None = None) -> T:
        """One field of the JSON body, of that type; otherwise refused, with a
        400. `default` stands in for a field that is not there at all."""
        found = self.read_json().get(name, default)
        if not isinstance(found, kind):
            msg = f"{name} is not a {kind.__name__}"
            raise Refused(400, msg)
        return found


@dataclass(frozen=True)
class Response:
    """What an endpoint answers. `explain` says why, for an error; `file` takes
    the place of `body` and is streamed without being read whole."""

    status: int = 200
    body: bytes = b""
    content_type: str = "application/json"
    explain: str = ""
    headers: Mapping[str, str] = field(default_factory=dict)
    file: pathlib.Path | None = None


NO_CONTENT = Response(204, content_type="")


def answer_json(value: object) -> Response:
    return Response(body=json.dumps(value).encode())


@dataclass(frozen=True)
class Endpoint:
    """A function the host API exposes, and the addresses that reach it.

    What `@endpoint` makes of a function, so that an entry point says so where
    it is defined; `routes` collects them into the table.
    """

    handle: Callable[[Request], Response]
    method: str
    names: tuple[str, ...]
    prefix: bool = False

    def __call__(self, r: Request) -> Response:
        return self.handle(r)


def endpoint(
    method: str, *names: str, prefix: bool = False
) -> Callable[[Callable[[Request], Response]], Endpoint]:
    """Mark a function as answering `method /__host__/<name>`, for each name.

    `prefix` for a name with more after it, as media/photo.png: the rest is
    `Request.path`. A mark, not a registration: nothing happens on import, and
    `routes` decides which modules' endpoints make up the API.
    """

    def mark(handle: Callable[[Request], Response]) -> Endpoint:
        return Endpoint(handle, method, names, prefix)

    return mark
