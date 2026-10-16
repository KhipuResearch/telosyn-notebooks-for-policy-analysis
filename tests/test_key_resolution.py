"""API keys come from the environment, or from a file the reader names; from nowhere else.

This repository stores and uses no secret, and the library reads none from a place the
reader did not point it at. These tests pin that: no default file, the reader's own
``KRL_SECRETS_PATH`` honoured only when set, and a missing key explained by the variable's
name and where to register for it.

© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import builtins
import inspect
import re
from pathlib import Path

import pytest

from krl_tutorials_data import sources
from krl_tutorials_data.sources import (
    ALLOWED_KEYS,
    KEY_REGISTRATION,
    DisallowedCredentialError,
    MissingCredentialError,
    load_key,
)

REPO = Path(__file__).resolve().parents[1]
PLANTED = "planted-value-never-to-be-read"


@pytest.fixture(name="home")
def _home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A fake home directory holding a key file where the old default looked."""
    home = tmp_path / "home"
    (home / ".krl").mkdir(parents=True)
    (home / ".krl" / "secrets.env").write_text(f"CENSUS_API_KEY={PLANTED}\n", encoding="utf-8")
    monkeypatch.setenv("HOME", str(home))
    for name in ALLOWED_KEYS | {"KRL_SECRETS_PATH"}:
        monkeypatch.delenv(name, raising=False)
    return home


def _opened(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Record every path opened through ``open`` or ``Path.open`` from now on."""
    seen: list[str] = []
    real_open, real_path_open = builtins.open, Path.open

    def spy_open(file, *args, **kwargs):  # type: ignore[no-untyped-def]
        """Spy open."""
        seen.append(str(file))
        return real_open(file, *args, **kwargs)

    def spy_path_open(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        """Spy path open."""
        seen.append(str(self))
        return real_path_open(self, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", spy_open)
    monkeypatch.setattr(Path, "open", spy_path_open)
    return seen


@pytest.mark.usefixtures("home")
def test_a_key_file_under_the_home_directory_is_not_read(monkeypatch: pytest.MonkeyPatch) -> None:
    """A key file under the home directory is not read."""
    seen = _opened(monkeypatch)
    with pytest.raises(MissingCredentialError) as exc:
        load_key("CENSUS_API_KEY")
    assert not [p for p in seen if p.endswith("secrets.env")], seen
    assert PLANTED not in str(exc.value)


@pytest.mark.usefixtures("home")
def test_a_missing_key_names_the_variable_and_where_to_register() -> None:
    """A missing key names the variable and where to register."""
    for name, url in KEY_REGISTRATION.items():
        with pytest.raises(MissingCredentialError) as exc:
            load_key(name)
        message = str(exc.value)
        assert name in message and url in message and "KRL_SECRETS_PATH is not set" in message


@pytest.mark.usefixtures("home")
def test_the_environment_wins_and_the_old_default_is_irrelevant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The environment wins and the old default is irrelevant."""
    monkeypatch.setenv("CENSUS_API_KEY", "from-the-environment")
    assert load_key("CENSUS_API_KEY") == "from-the-environment"


@pytest.mark.usefixtures("home")
def test_a_file_is_read_only_when_the_reader_names_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A file is read only when the reader names it."""
    mine = tmp_path / "mine.env"
    mine.write_text("# mine\nFRED_API_KEY='abc123'\nOTHER=ignored\n", encoding="utf-8")  # pragma: allowlist secret
    monkeypatch.setenv("KRL_SECRETS_PATH", str(mine))
    assert sources.secrets_path() == mine
    assert load_key("FRED_API_KEY") == "abc123"
    with pytest.raises(MissingCredentialError, match="does not define it"):
        load_key("CENSUS_API_KEY")  # the planted home file is still not consulted
    seen = _opened(monkeypatch)
    load_key("FRED_API_KEY")
    assert all(not p.endswith("secrets.env") for p in seen)


@pytest.mark.usefixtures("home")
def test_an_explicit_path_argument_still_works(tmp_path: Path) -> None:
    """An explicit path argument still works."""
    explicit = tmp_path / "explicit.env"
    explicit.write_text("BLS_API_KEY=xyz\n", encoding="utf-8")
    assert load_key("BLS_API_KEY", path=explicit) == "xyz"


@pytest.mark.usefixtures("home")
def test_without_a_named_file_there_is_no_file_path_at_all() -> None:
    """Without a named file there is no file path at all."""
    assert sources.secrets_path() is None


@pytest.mark.usefixtures("home")
def test_a_disallowed_name_opens_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    """A disallowed name opens nothing."""
    seen = _opened(monkeypatch)
    with pytest.raises(DisallowedCredentialError):
        load_key("DATABASE_URL")
    assert not seen


def test_no_default_location_survives_in_the_source() -> None:
    """No default location survives in the source."""
    source = inspect.getsource(sources)
    assert not hasattr(sources, "_DEFAULT_SECRETS_PATH")
    assert ".krl" not in source and "Path.home" not in source and "expanduser" not in source


def test_registration_addresses_cover_every_allowed_key_and_match_the_template() -> None:
    """Registration addresses cover every allowed key and match the template."""
    assert set(KEY_REGISTRATION) == set(ALLOWED_KEYS)
    template = (REPO / ".env.example").read_text(encoding="utf-8")
    for name, url in KEY_REGISTRATION.items():
        assert re.search(rf"{re.escape(url)}", template), f"{name}: {url} is not in .env.example"
