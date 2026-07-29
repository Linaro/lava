# Copyright 2026 NXP
#
# Author: Larry Shen <larry.shen@nxp.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import importlib
import sys
import types

import pytest


@pytest.mark.parametrize(
    "env_vars,expect_patch",
    [
        ({"GUNICORN_WORKER_CLASS": "gevent"}, True),
        ({"WORKER_CLASS": "gevent"}, True),
        ({"GUNICORN_WORKER_CLASS": "gthread"}, False),
        ({}, False),
    ],
)
def test_gunicorn_gevent_patch(monkeypatch, env_vars, expect_patch):
    # Clear both env vars to avoid interference between test cases
    monkeypatch.delenv("GUNICORN_WORKER_CLASS", raising=False)
    monkeypatch.delenv("WORKER_CLASS", raising=False)
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)

    patched = []

    class FakeMonkey:
        @staticmethod
        def patch_all():
            patched.append(True)

    # Mock gevent so the test does not require gevent installed
    fake_gevent = types.ModuleType("gevent")
    fake_gevent.monkey = FakeMonkey
    monkeypatch.setitem(sys.modules, "gevent", fake_gevent)

    # Remove cached module so the import below re-executes the module body
    # with the current environment variables and mocks
    monkeypatch.delitem(sys.modules, "lava_server.gunicorn_gevent", raising=False)

    importlib.import_module("lava_server.gunicorn_gevent")

    assert bool(patched) == expect_patch
