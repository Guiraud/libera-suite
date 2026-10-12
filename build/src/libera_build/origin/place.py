"""Where the payload lives, asked of the application rather than repeated.

The origin and the version are what the installed `libera` will ask for, so
tooling that spelt them itself could publish a perfect set of artifacts to a
directory nothing looks in.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from libera.payload import installer, locate
from libera_build import versions
from libera_build.report import RefusedError

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True)
class Origin:
    cdn_url: str  # https://host
    zone: str  # the first path segment: how the CDN resolves one
    version: str  # the payload version: the directory a release goes in

    @property
    def base(self) -> str:
        """The payload's directory, as a stranger's machine reads it."""
        return f"{self.cdn_url}/{self.zone}/{self.version}"

    def public(self, key: str) -> str:
        return f"{self.cdn_url}/{self.zone}/{key}"

    def api(self, key: str) -> str:
        """Where an object is written: the CDN's upload API."""
        return f"{self.cdn_url}/_/api/v1/zones/{self.zone}/objects/{key}"


def split_origin(url: str) -> tuple[str, str]:
    """https://host/zone into the host's URL and the zone."""
    parts = urlsplit(url)
    zone = parts.path.strip("/")
    if not zone:
        msg = f"no zone in {url}: it should be https://host/<zone>"
        raise RefusedError(msg)
    return f"{parts.scheme}://{parts.netloc}", zone


def agreed_version(application: str, build: str) -> str:
    """The payload version, once the application and the build agree on it.

    Two definitions of one version is a way to publish to a directory the
    application never reads, and the failure would not appear until somebody
    ran --payload-install.
    """
    if application != build:
        msg = (
            f"build/payload/payload.version says {build}, locate.py {application}.\n"
            f"  The artifacts would go to {application}/ and the build would name "
            f"them {build}. Fix one before publishing anything."
        )
        raise RefusedError(msg)
    return application


def here(root: Path) -> Origin:
    """The origin this checkout publishes to. CDN_URL and ZONE override the
    two halves of DEFAULT_ORIGIN, for a test origin."""
    cdn_url, zone = split_origin(installer.DEFAULT_ORIGIN)
    version = agreed_version(locate.PAYLOAD_VERSION, versions.payload_version(root))
    return Origin(
        os.environ.get("CDN_URL") or cdn_url, os.environ.get("ZONE") or zone, version
    )
