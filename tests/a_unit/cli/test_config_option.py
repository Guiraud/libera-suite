"""`libera --config FILE` and LIBERA_CONFIG: a configuration of one's own, for
development, beside the user's usual config.toml, which they leave alone."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

from libera.cli import dispatch
from libera.payload import locate

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def own(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.delenv("LIBERA_CONFIG", raising=False)
    config = tmp_path / "dev.toml"
    config.write_text('user_name = "Ada Lovelace"\n', encoding="utf-8")
    return config


def test_libera_config_names_the_file_read(own: Path, monkeypatch) -> None:
    monkeypatch.setenv("LIBERA_CONFIG", str(own))
    assert locate.get_config_file() == own
    assert locate.read_config_string("user_name") == "Ada Lovelace"


def test_a_named_file_that_is_not_there_is_an_error(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("LIBERA_CONFIG", str(tmp_path / "typo.toml"))
    with pytest.raises(locate.PayloadError, match=r"typo\.toml"):
        locate.read_config_string("user_name")


def test_the_option_sets_it_for_the_whole_run(own: Path, monkeypatch) -> None:
    seen: list[str | None] = []

    def command(_args) -> int:
        seen.append(os.environ.get("LIBERA_CONFIG"))
        return 0

    monkeypatch.setattr(dispatch, "_choose_command", lambda _parser, _args: command)
    # Put back whatever the option sets: the environment outlives the test.
    monkeypatch.setenv("LIBERA_CONFIG", "")

    assert dispatch.main(["-c", str(own)]) == 0
    assert seen == [str(own.resolve())]


def test_the_option_refuses_a_file_that_is_not_there(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        dispatch.main(["--config", str(tmp_path / "typo.toml")])
