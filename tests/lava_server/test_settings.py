# Copyright (C) 2022 Linaro
#
# Author: Rémi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import importlib


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
