"""Saying once that a newer version is out, and nothing when offline.

The origin is a directory, reached as file:, laid out as the CDN is: the
pointer at bundles/latest. No network, and the same urlopen call.
"""

from __future__ import annotations

import json
import urllib.error

import pytest

from libera.host import hooks, updates
from libera.payload import locate

NOW = 1_800_000_000.0


class Told(hooks.HeadlessShell):
    def __init__(self) -> None:
        self.said: list[tuple[str, str]] = []

    def tell(self, heading: str, detail: str) -> None:
        self.said.append((heading, detail))


@pytest.fixture
def told(monkeypatch):
    shell = Told()
    monkeypatch.setattr(hooks, "shell", shell)
    monkeypatch.delenv("FLATPAK_ID", raising=False)
    return shell.said


def an_origin(tmp_path, latest: str) -> str:
    (tmp_path / "origin" / "bundles").mkdir(parents=True)
    (tmp_path / "origin" / "bundles" / "latest").write_text(latest + "\n")
    return (tmp_path / "origin").as_uri()


def test_a_newer_version_is_told_once(tmp_path, told):
    origin = an_origin(tmp_path, "0.5.0")
    state = tmp_path / "state" / "updates.json"

    updates.check("0.4.0", origin, state, NOW)
    updates.check("0.4.0", origin, state, NOW + 2 * updates.DAY)

    assert [heading for heading, _ in told] == ["Libera Suite 0.5.0 is available"]


def test_once_a_day_at_most(tmp_path, told):
    """The second start the same day does not ask: if it did, the version
    published in between would be told, and here it is not."""
    origin = an_origin(tmp_path, "0.4.0")
    state = tmp_path / "updates.json"
    updates.check("0.4.0", origin, state, NOW)
    (tmp_path / "origin" / "bundles" / "latest").write_text("0.5.0\n")

    updates.check("0.4.0", origin, state, NOW + 60)

    assert told == []
    assert json.loads(state.read_text())["checked"] == NOW


def test_the_same_or_an_older_version_says_nothing(tmp_path, told):
    origin = an_origin(tmp_path, "0.4.0")

    updates.check("0.4.0", origin, tmp_path / "a.json", NOW)
    updates.check("0.10.0", origin, tmp_path / "b.json", NOW)

    assert told == []


def test_offline_nothing_is_said_and_nothing_is_recorded(tmp_path, told):
    state = tmp_path / "updates.json"

    with pytest.raises(urllib.error.URLError):
        updates.check("0.4.0", (tmp_path / "nowhere").as_uri(), state, NOW)

    assert told == []
    assert not state.exists(), "an offline start would skip the next day's check"


def test_an_answer_that_is_not_a_version_says_nothing(tmp_path, told):
    origin = an_origin(tmp_path, "<html>not found</html>")

    with pytest.raises(ValueError, match="not a version"):
        updates.check("0.4.0", origin, tmp_path / "updates.json", NOW)

    assert told == []


def test_the_message_says_how_to_update_a_flatpak(tmp_path, monkeypatch, told):
    monkeypatch.setenv("FLATPAK_ID", "eu.liberasuite.Libera")

    updates.check("0.4.0", an_origin(tmp_path, "0.5.0"), tmp_path / "u.json", NOW)

    [(_, detail)] = told
    assert "install.sh | sh" in detail
    assert "This is version 0.4.0." in detail


@pytest.fixture
def config(tmp_path, monkeypatch):
    """Where config.toml is read from, not yet written."""
    path = tmp_path / "config.toml"
    monkeypatch.setattr(locate, "get_config_file", lambda: path)
    return path


@pytest.mark.parametrize(
    "contents",
    [None, 'user_name = "Jeanne Dupont"\n', "check_updates = true\n"],
    ids=["no config file", "a config without the key", "switched on"],
)
def test_it_is_on_unless_switched_off(config, contents):
    if contents is not None:
        config.write_text(contents, encoding="utf-8")

    assert updates.wanted()


def test_config_turns_it_off(config):
    config.write_text("check_updates = false\n", encoding="utf-8")

    assert not updates.wanted()


def test_a_switch_that_is_not_true_or_false_is_named(config):
    config.write_text('check_updates = "no"\n', encoding="utf-8")

    with pytest.raises(locate.PayloadError, match=r"check_updates .* true or false"):
        updates.wanted()


@pytest.fixture
def started(monkeypatch):
    """The names of the threads check_in_background starts, none of them run:
    a real one would go to the network."""
    names: list[str] = []

    class NotRun:
        def __init__(self, *, name: str, **_kw) -> None:
            names.append(name)

        def start(self) -> None:
            pass

    monkeypatch.setattr(updates.threading, "Thread", NotRun)
    return names


def test_without_a_config_the_check_starts(config, started):
    """What the two below are measured against: with nothing configured, the
    thread does start, so an empty list there means something."""
    updates.check_in_background()

    assert started == ["update-check"]


def test_a_switch_that_cannot_be_read_means_no_check(config, started, caplog):
    config.write_text('check_updates = "no"\n', encoding="utf-8")

    updates.check_in_background()

    assert started == []
    assert "true or false" in caplog.text


def test_a_switch_turned_off_means_no_check(config, started):
    config.write_text("check_updates = false\n", encoding="utf-8")

    updates.check_in_background()

    assert started == []


def test_a_pre_release_hears_about_its_release(tmp_path, told):
    """A tester's 0.4.0rc1 is older than 0.4.0, and newer than 0.3.3."""
    updates.check("0.4.0rc1", an_origin(tmp_path, "0.4.0"), tmp_path / "s.json", NOW)
    assert [heading for heading, _ in told] == ["Libera Suite 0.4.0 is available"]
    told.clear()
    updates.check(
        "0.4.0rc1", an_origin(tmp_path / "old", "0.3.3"), tmp_path / "t.json", NOW
    )
    assert told == []


def test_pre_releases_sort_below_their_release_and_by_number():
    ordered = ["0.3.3", "0.4.0a1", "0.4.0b1", "0.4.0rc2", "0.4.0rc10", "0.4.0", "0.4.1"]
    assert sorted(ordered, key=updates.parse_version) == ordered
