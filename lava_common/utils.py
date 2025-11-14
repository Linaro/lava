# Copyright (C) 2018 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import contextlib
import re
import subprocess  # nosec dpkg

from lava_common.exceptions import InfrastructureError


def binary_version(binary: str, flags: str = "", pattern: str = "") -> str:
    """
    Returns a string with the version of the binary by running it with
    the provided flags. If the output from running the binary is verbose
    and contains more than just the version number, a pattern can be
    provided for the function to parse the output to pick out the
    substring that contains the version number.
    """
    # if binary is not absolute, fail.
    msg = f"Unable to retrieve version of {binary}"
    try:
        ver_str = (
            subprocess.check_output((binary, flags), stderr=subprocess.STDOUT)
            .strip()
            .decode("utf-8", errors="replace")
        )
        if not ver_str:
            raise InfrastructureError(msg)
    except (subprocess.CalledProcessError, FileNotFoundError):
        raise InfrastructureError(msg)

    if pattern != "":
        p = re.compile(pattern)
        result = p.search(ver_str)
        if result is not None:
            ver_str = result.group(1)
        else:
            raise InfrastructureError(msg)

    return f"{binary}, version {ver_str}"


def debian_package_arch(pkg: str) -> str:
    """
    Relies on Debian Policy rules for the existence of the
    changelog. Distributions not derived from Debian will
    return an empty string.
    """
    with contextlib.suppress(FileNotFoundError, subprocess.CalledProcessError):
        return (
            subprocess.check_output(  # nosec dpkg-query
                ("dpkg-query", "-W", "-f=${Architecture}\n", pkg),
                stderr=subprocess.STDOUT,
            )
            .strip()
            .decode("utf-8", errors="replace")
        )
    return ""


def debian_package_version(pkg: str) -> str:
    """
    Use dpkg-query to retrieve the version of the given package.
    Distributions not derived from Debian will return an empty string.
    """
    with contextlib.suppress(FileNotFoundError, subprocess.CalledProcessError):
        return (
            subprocess.check_output(  # nosec dpkg-query
                ("dpkg-query", "-W", "-f=${Version}\n", pkg),
                stderr=subprocess.STDOUT,
            )
            .strip()
            .decode("utf-8", errors="replace")
        )
    return ""


def debian_filename_version(binary: str) -> str:
    """
    Relies on Debian Policy rules for the existence of the
    changelog. Distributions not derived from Debian will
    return an empty string.
    """
    # if binary is not absolute, fail.
    msg = f"Unable to retrieve version of {binary}"
    pkg_str = None
    with contextlib.suppress(FileNotFoundError, subprocess.CalledProcessError):
        pkg_str = (
            subprocess.check_output(  # nosec dpkg-query
                ("dpkg-query", "-S", binary), stderr=subprocess.STDOUT
            )
            .strip()
            .decode("utf-8", errors="replace")
        )
    if not pkg_str:
        raise InfrastructureError(msg)
    pkg = pkg_str.split(":", maxsplit=1)[0]
    pkg_ver = debian_package_version(pkg)
    return f"{pkg} for <{binary}>, installed at version: {pkg_ver}"
