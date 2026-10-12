"""Add to dictionary, end to end: the editor's call, the real spell checker,
and a page loaded afterwards.

The worker answers what the editor asks it to check. A word the user added is
the bridge's to mark correct, since the worker has no notion of a user's words.
"""

from __future__ import annotations

ENGLISH = 1033  # what the editor sends for en-US


def check(editor, words: list[str]) -> list[bool]:
    """Ask the bridge to check words, as a paragraph does, and read the reply."""
    request = {
        "type": "spell",
        "ParagraphId": "probe",
        "RecalcId": 0,
        "ElementId": 0,
        "usrWords": words,
        "usrLang": [ENGLISH] * len(words),
    }
    return editor.frame.evaluate(
        """(request) => new Promise((resolve) => {
            const before = window.asc_nativeOnSpellCheck;
            window.asc_nativeOnSpellCheck = (reply) => {
                if (reply && reply.ParagraphId === "probe") {
                    window.asc_nativeOnSpellCheck = before;
                    resolve(reply.usrCorrect);
                } else if (before) before(reply);
            };
            window.AscDesktopEditor.SpellCheck(JSON.stringify(request));
        })""",
        request,
    )


def test_a_word_added_to_the_dictionary_is_correct_next_time(editor_with):
    editor = editor_with([])
    assert check(editor, ["Frobnitzel", "Frobnitzal"]) == [False, False]

    editor.frame.evaluate(
        "() => window.Asc.editor.asc_spellCheckAddToDictionary('Frobnitzel')"
    )
    editor.page.reload()
    editor.wait_until_ready()

    assert check(editor, ["Frobnitzel", "Frobnitzal"]) == [True, False]


def test_an_added_word_is_correct_with_punctuation_around_it(editor_with):
    """The editor checks a word as it stands in the text, so the last word of a
    sentence arrives as "Frobnitzel.": exact matching left it flagged, and an
    added word looked forgotten as soon as it ended a sentence."""
    editor = editor_with([])
    editor.frame.evaluate(
        "() => window.Asc.editor.asc_spellCheckAddToDictionary('Frobnitzel')"
    )

    words = [
        "Frobnitzel.",
        "(Frobnitzel)",
        "«Frobnitzel»",
        "Frobnitzel,",
        "Frobnitzal.",
    ]
    assert check(editor, words) == [True, True, True, True, False]


def test_an_added_word_follows_hunspells_rule_for_case(editor_with):
    """Added in lower case, it is right capitalised and in capitals, as a
    dictionary word is; added capitalised, a name, it is not right in lower
    case."""
    editor = editor_with([])
    for word in ("frobnitzel", "Grenwick"):
        editor.frame.evaluate(
            "(w) => window.Asc.editor.asc_spellCheckAddToDictionary(w)", word
        )

    words = ["frobnitzel", "Frobnitzel", "FROBNITZEL", "Grenwick", "grenwick"]
    assert check(editor, words) == [True, True, True, True, False]


def test_a_word_added_with_its_punctuation_is_kept_without_it(editor_with):
    """What was under the cursor can carry the full stop too."""
    editor = editor_with([])
    editor.frame.evaluate(
        "() => window.Asc.editor.asc_spellCheckAddToDictionary('Frobnitzel.')"
    )

    assert check(editor, ["Frobnitzel"]) == [True]
