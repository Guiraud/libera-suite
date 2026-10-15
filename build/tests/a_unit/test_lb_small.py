"""The small pure parts: artifact names, the host protocol's helpers, versions."""

from __future__ import annotations

import pytest
from libera_build import artifacts, versions
from libera_build.hosts import facts_from, remote_path
from libera_build.release import on
from libera_build.report import RefusedError


def test_artifacts_are_named_for_the_right_version():
    assert artifacts.core_name("linux-arm64") == "core-linux-arm64.tar.gz"
    assert artifacts.bundle_name("0.3.3", "amd64") == "libera-0.3.3-amd64.flatpak"


def test_an_artifact_under_its_floor_is_not_one():
    floor = artifacts.MIN_CORE_BYTES
    assert artifacts.size_problem("p", "c.tar.gz", floor - 1, floor)
    assert artifacts.size_problem("p", "c.tar.gz", floor, floor) is None


def test_facts_are_the_key_value_lines_only():
    out = "noise\nARCH=x86_64\nPATH=a=b\nmore noise"
    assert facts_from(out) == {"ARCH": "x86_64", "PATH": "a=b"}


def test_a_remote_path_keeps_its_tilde_expandable():
    assert remote_path("~/muchado") == '"$HOME/muchado"'
    assert remote_path("/a b") == "'/a b'"


def test_the_payload_version_is_read_from_its_line(tmp_path):
    (tmp_path / "src" / "libera" / "payload").mkdir(parents=True)
    (tmp_path / "src" / "libera" / "payload" / "payload.version").write_text(
        '# a comment = no\nversion = "0.4"\n'
    )
    assert versions.payload_version(tmp_path) == "0.4"
    (tmp_path / "src" / "libera" / "payload" / "payload.version").write_text(
        "# nothing\n"
    )
    with pytest.raises(RefusedError):
        versions.payload_version(tmp_path)


def test_the_application_version_is_pyprojects(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "1.2.3"\n')
    assert versions.app_version(tmp_path) == "1.2.3"


def test_on_reads_the_status_from_the_verdict():
    assert on.status_of("linux-arm64", "0") == 0
    assert on.status_of("linux-arm64", "3") == 3


@pytest.mark.parametrize(
    ("verdict", "says"),
    [
        ("no checkout at ~/x", "linux-arm64: no checkout at ~/x"),
        ("", "linux-arm64: the command stopped without saying how"),
    ],
)
def test_a_verdict_that_is_not_a_status_is_said(verdict, says):
    with pytest.raises(RefusedError) as e:
        on.status_of("linux-arm64", verdict)
    assert str(e.value) == says


def test_a_pointer_names_digits_and_dots_and_nothing_else_is_a_release():
    assert not versions.is_prerelease("0.4.0")
    assert not versions.is_prerelease("1.10")
    for pre in ("0.4.0rc1", "0.4.0a2", "0.4.0.post1", "0.4.0+local", "0.4.0.dev3"):
        assert versions.is_prerelease(pre), pre
