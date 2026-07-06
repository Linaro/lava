# Copyright (C) 2022 Linaro
#
# Author: Rémi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import importlib
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

import pytest
from django.core.exceptions import ImproperlyConfigured

from lava_server.settings.config_file import ConfigFile

FULL_MIDDLEWARE = "lava_server.security.LavaRequireLoginMiddleware"
PATHS_MIDDLEWARE = "lava_server.security.LavaRequireLoginPathsMiddleware"


def test_settings(mocker, monkeypatch):
    def __read_text(file, *args, **kwargs):
        if str(file).startswith("/etc/lava-server/settings"):
            raise FileNotFoundError
        return file.read_text(*args, **kwargs)

    mocker.patch("pathlib.Path.read_text", __read_text)
    mocker.patch(
        "lava_server.settings.config_file.ConfigFile.load",
        side_effect=FileNotFoundError,
    )

    monkeypatch.setenv("LAVA_SETTINGS_HELLO", "world")
    monkeypatch.setenv(
        "LAVA_JSON_SETTINGS", "eyJXT1JLRVJfQVVUT19SRUdJU1RFUl9ORVRNQVNLIjogWyI6OjEiXX0="
    )
    import lava_server.settings.prod as settings

    # Reload so the module body re-runs with this test's mocks and env,
    # regardless of whether prod was already imported by another test.
    importlib.reload(settings)

    assert settings.HELLO == "world"
    assert settings.WORKER_AUTO_REGISTER_NETMASK == ["::1"]


def test_settings_empty_yaml(mocker, monkeypatch):
    # An empty settings file (or a file with just comments) shouldn't crash.
    def __read_text(file, *args, **kwargs):
        if str(file) == "/etc/lava-server/settings.yaml":
            return "# just a comment\n"
        if str(file).startswith("/etc/lava-server/settings"):
            raise FileNotFoundError
        return file.read_text(*args, **kwargs)

    mocker.patch("pathlib.Path.read_text", __read_text)
    mocker.patch(
        "lava_server.settings.config_file.ConfigFile.load",
        side_effect=FileNotFoundError,
    )

    import lava_server.settings.prod as settings

    # Reload so the module body runs again with the mocked empty file.
    importlib.reload(settings)


class TestConfigFile(TestCase):
    def test_config_file(self) -> None:
        with TemporaryDirectory() as tmpdir_name:
            tempdir = Path(tmpdir_name)
            config_file_path = tempdir / "settings.conf"
            config_file_path.write_text(
                """FOO='BAR'
TEST123='456' # test setting
SPACE="foo bar"

# Empty line

NO_QUOTES=no_quotes
"""
            )
            config = ConfigFile.load(config_file_path)
            self.assertEqual(config["FOO"], "BAR")
            self.assertEqual(config["TEST123"], "456")
            self.assertEqual(config["SPACE"], "foo bar")
            self.assertEqual(config["NO_QUOTES"], "no_quotes")


def _run_update(**overrides):
    import lava_server.settings.dev
    from lava_server.settings.common import update

    values = {k: v for k, v in vars(lava_server.settings.dev).items() if k.isupper()}
    values["MIDDLEWARE"] = list(values["MIDDLEWARE"])
    values["INSTALLED_APPS"] = list(values["INSTALLED_APPS"])
    values.update(overrides)
    return update(values)


def test_require_login_paths_default_empty():
    result = _run_update()
    assert result["REQUIRE_LOGIN_PATHS"] == []
    assert PATHS_MIDDLEWARE not in result["MIDDLEWARE"]


def test_require_login_paths_adds_middleware():
    result = _run_update(REQUIRE_LOGIN_PATHS=["results/query"])
    assert PATHS_MIDDLEWARE in result["MIDDLEWARE"]


def test_require_login_runs_before_require_login_paths():
    result = _run_update(REQUIRE_LOGIN=True, REQUIRE_LOGIN_PATHS=["results/query"])
    middleware = result["MIDDLEWARE"]
    assert middleware.index(FULL_MIDDLEWARE) < middleware.index(PATHS_MIDDLEWARE)


@pytest.mark.parametrize(
    "value",
    ["results/query", [""], ["/"], [123], [None], ["results/query", ""]],
)
def test_require_login_paths_invalid_configuration(value):
    with pytest.raises(ImproperlyConfigured):
        _run_update(REQUIRE_LOGIN_PATHS=value)
