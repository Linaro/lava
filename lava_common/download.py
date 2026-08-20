# Copyright (C) 2026 Qualcomm Technologies, Inc. and/or its subsidiaries.
#
# Author: Christopher Obbard <chris.obbard@oss.qualcomm.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

# Dispatcher temporary directory, used when nothing else is configured.
# This is distinct from the TFTP daemon directory.
# Files here are for download using the Apache /tmp alias, see
# share/apache2/lava-dispatcher.conf.
DEFAULT_DOWNLOAD_DIR = Path("/var/lib/lava/dispatcher/tmp")


def resolve_download_dir(path: str | Path | None = None) -> Path:
    """
    Directory holding the temporary files of the jobs, which is served over
    http by the dispatcher.

    Returns path when the dispatcher is configured to use another directory,
    either with the dispatcher_download_dir key of the dispatcher
    configuration or on the command line, and the default location otherwise.

    The result is absolute: the directory is shared between processes which do
    not have the same working directory, like the worker, lava-run,
    lava-dispatcher-host and the http server.
    """
    if not path:
        return DEFAULT_DOWNLOAD_DIR
    return Path(path).absolute()


def dispatcher_download_dir(dispatcher_config: dict[str, Any] | None) -> str:
    """
    Same directory as resolve_download_dir(), for the callers holding the
    dispatcher configuration rather than the value itself.

    dispatcher_config is None when no dispatcher configuration was given and
    might be any type as it comes straight from the configuration file.
    """
    if not isinstance(dispatcher_config, dict):
        return str(resolve_download_dir())
    return str(resolve_download_dir(dispatcher_config.get("dispatcher_download_dir")))
