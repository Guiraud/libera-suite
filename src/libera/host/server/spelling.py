"""The personal dictionary: the words Add to dictionary keeps.

The spell checker itself runs in the page, in sdkjs's worker; it has no notion
of a user's words, so the host keeps them and the bridge marks them correct.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from libera.host.server.api import (
    NO_CONTENT,
    Refused,
    Request,
    Response,
    answer_json,
    endpoint,
)

if TYPE_CHECKING:
    import pathlib

    from libera.host.session import Session


def find_personal_words(session: Session) -> pathlib.Path:
    """Words the user added to the dictionary, one per line, in every
    language. Beside the session directory, like the Recent list: every window
    and every launch reads the same one."""
    return session.work.parent / "dictionary.txt"


def _read_personal_words(session: Session) -> list[str]:
    path = find_personal_words(session)
    return path.read_text(encoding="utf-8").splitlines() if path.is_file() else []


@endpoint("GET", "words")
def serve_words(r: Request) -> Response:
    return answer_json(_read_personal_words(r.session))


# Longer than any word a dictionary holds; what is longer is not a word.
LONGEST_WORD = 100

# Two windows adding the same word at once would both find it missing.
_ADDING_WORDS = threading.Lock()


@endpoint("POST", "words")
def add_personal_word(r: Request) -> Response:
    """Add to dictionary: one word, kept for every window and every launch."""
    word = r.read_json().get("word")
    if not isinstance(word, str) or not 0 < len(word) <= LONGEST_WORD:
        msg = f"a word is 1 to {LONGEST_WORD} characters"
        raise Refused(400, msg)
    if any(c.isspace() for c in word):
        msg = "a word has no spaces or line breaks in it"
        raise Refused(400, msg)
    with _ADDING_WORDS:
        if word not in _read_personal_words(r.session):
            with find_personal_words(r.session).open("a", encoding="utf-8") as f:
                f.write(word + "\n")
    return NO_CONTENT
