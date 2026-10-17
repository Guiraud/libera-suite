"""Where a click on a cross-edition link actually lands, in a real browser.

`make switcher`, after a build. It serves `site/` and drives Chromium, because
the logic under test is the interplay between `src/assets/lang.js` and the
theme's own handler, and neither shows up in the HTML. Every case here is a
bug that shipped: the selector landing on the edition root with its trailing
slash stripped, the selector freezing on the first page after an instant
navigation, and the theme rewriting a content link into "this page, over
there".

Needs playwright: `uv run --with playwright python switcher.py`.
"""

from __future__ import annotations

import functools
import http.server
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

SITE = Path(__file__).parent / "site"

# A click on the language selector, and where it has to land.
SWITCH = [
    ("/en/develop/", "fr", "/fr/develop/"),
    ("/en/develop/architecture/", "fr", "/fr/develop/"),
    ("/en/main/install/", "fr", "/fr/main/install/"),
    ("/en/", "fr", "/fr/"),
    ("/fr/develop/", "en", "/en/develop/"),
    ("/de/main/install/", "es", "/es/main/install/"),
]

# A click on a link into another edition: the theme must not redirect it.
CROSS = [
    ("/fr/licence/", "/en/develop/patches/"),
    ("/fr/main/install/", "/en/develop/roadmap/"),
    ("/fr/develop/", "/en/develop/"),
    ("/de/licence/", "/en/develop/patches/"),
]

# A page that renders unstyled has lost its stylesheets, which is the shape
# the slashless edition root took.
STYLED = 3

CLICK_CONTENT_LINK = """
h => [...document.querySelectorAll('.md-content a[href]')]
  .find(a => new URL(a.href).pathname === h).click()
"""
CLICK_SELECTOR = (
    "l => document.querySelector(`a.md-select__link[hreflang=${l}]`).click()"
)
SELECTOR_HREF = """
l => document.querySelector(`a.md-select__link[hreflang=${l}]`).getAttribute('href')
"""
CLICK_WITHIN_EDITION = """
p => [...document.querySelectorAll('a')]
  .find(a => a.href.includes(p) && !a.hreflang).click()
"""


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args: object) -> None:
        """One request per asset is not news here."""


def serve() -> str:
    handler = functools.partial(Quiet, directory=str(SITE))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{server.server_port}"


def main() -> None:
    assert SITE.is_dir(), f"{SITE} is not there: build first"
    root = serve()
    with sync_playwright() as play:
        browser = play.chromium.launch()

        for path, lang, expected in SWITCH:
            page = browser.new_page()
            page.goto(root + path, wait_until="load")
            page.wait_for_timeout(500)
            page.evaluate(CLICK_SELECTOR, lang)
            page.wait_for_load_state("load")
            page.wait_for_timeout(800)
            assert page.url == root + expected, f"{path} [{lang}] landed on {page.url}"
            sheets = page.evaluate("document.styleSheets.length")
            assert sheets >= STYLED, f"{page.url} has {sheets} stylesheets"
            assert f"libera-docs-lang={lang}" in page.evaluate("document.cookie")
            print(f"ok  {path} [{lang}] -> {expected}")
            page.close()

        for path, link in CROSS:
            page = browser.new_page()
            page.goto(root + path, wait_until="load")
            page.wait_for_timeout(500)
            page.evaluate(CLICK_CONTENT_LINK, link)
            page.wait_for_timeout(1500)
            assert page.url == root + link, f"{path} -> {link} landed on {page.url}"
            print(f"ok  {path} -> {link}")
            page.close()

        # The selector must survive instant navigation: it used to read back
        # the page path it had written itself, and freeze there.
        page = browser.new_page()
        page.goto(root + "/en/", wait_until="load")
        page.wait_for_timeout(500)
        page.evaluate("window.__mark = 1")
        for step in ["/en/main/install/", "/en/main/status/", "/en/develop/"]:
            page.evaluate(CLICK_WITHIN_EDITION, step)
            page.wait_for_timeout(1200)
        instant = page.evaluate("window.__mark === 1")
        assert instant, "same-edition links no longer navigate instantly"
        href = page.evaluate(SELECTOR_HREF, "fr")
        assert href == "/fr/develop/", f"after three instant navigations: {href}"
        print("ok  three instant navigations, then the selector -> /fr/develop/")
        page.close()

        # The decks on the translated pages point at /en/pdf/, so their link
        # crosses editions too.
        page = browser.new_page()
        page.goto(root + "/fr/", wait_until="load")
        page.wait_for_timeout(2500)
        with page.expect_download(timeout=8000) as download:
            page.evaluate("document.querySelector('.deck a[download]').click()")
        assert download.value.suggested_filename.endswith(".pdf")
        print("ok  /fr/ deck link -> the PDF itself")
        page.close()

        browser.close()
    print("the switcher is sound")


if __name__ == "__main__":
    main()
