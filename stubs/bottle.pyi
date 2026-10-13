# The parts of Bottle the host uses, which is the adapter in
# libera/host/server/adapter.py and nothing else. Bottle ships no types and
# typeshed has none; see stubs/README.md.
from collections.abc import Callable, Iterable, Mapping
from typing import IO, Any, TypeVar

_F = TypeVar("_F", bound=Callable[..., Any])

class BaseRequest:
    environ: dict[str, Any]
    headers: Mapping[str, str]
    query_string: str
    body: IO[bytes]
    method: str
    path: str

# Bottle's request for the thread serving it. Read in the adapter only, which
# copies what an endpoint needs into a Request value and passes it on.
request: BaseRequest

class HTTPResponse(Exception):
    status_code: int
    def __init__(
        self,
        body: Any = ...,
        status: int | str | None = ...,
        headers: Mapping[str, str] | None = ...,
        **more_headers: Any,
    ) -> None: ...
    def set_header(self, name: str, value: str) -> None: ...

class Bottle:
    catchall: bool
    def __init__(self, catchall: bool = ..., autojson: bool = ...) -> None: ...
    def route(
        self,
        path: str | None = ...,
        method: str | list[str] = ...,
        callback: Callable[..., Any] | None = ...,
        name: str | None = ...,
        **config: Any,
    ) -> Callable[[_F], _F]: ...
    def __call__(
        self, environ: dict[str, Any], start_response: Callable[..., Any]
    ) -> Iterable[bytes]: ...
