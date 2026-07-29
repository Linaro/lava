# Copyright 2026 NXP
#
# Author: Larry Shen <larry.shen@nxp.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import os

# Apply gevent monkey-patch before the WSGI app is preloaded.
# This must be done at module level because preload_app runs during
# Arbiter.setup(), which is called before any server hooks.
# Load this file via: --config python:lava_server.gunicorn_gevent
if (
    os.environ.get("GUNICORN_WORKER_CLASS") == "gevent"
    or os.environ.get("WORKER_CLASS") == "gevent"
):
    from gevent import monkey

    monkey.patch_all()
