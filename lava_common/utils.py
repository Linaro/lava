# Copyright (C) 2018 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import contextlib
import re
import subprocess  # nosec dpkg

from lava_common.exceptions import InfrastructureError


def binary_version(binary, flags="", pattern=""):
    """
    Returns a string with the version of the binary by running it with
    the provided flags. If the output from running the binary is verbose
    and contains more than just the version number, a pattern can be
    provided for the function to parse the output to pick out the
    substring that contains the version number.
    """
    # if binary is not absolute, fail.
    msg = "Unable to retrieve version of %s" % binary
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

    return "%s, version %s" % (binary, ver_str)


def debian_package_arch(pkg):
    """
    Relies on Debian Policy rules for the existence of the
    changelog. Distributions not derived from Debian will
    return an empty string.
    """
    with contextlib.suppress(FileNotFoundError, subprocess.CalledProcessError):
        return (
            subprocess.check_output(  # nosec dpkg-query
                ("dpkg-query", "-W", "-f=${Architecture}\n", "%s" % pkg),
                stderr=subprocess.STDOUT,
            )
            .strip()
            .decode("utf-8", errors="replace")
        )
    return ""


def debian_package_version(pkg):
    """
    Use dpkg-query to retrieve the version of the given package.
    Distributions not derived from Debian will return an empty string.
    """
    with contextlib.suppress(FileNotFoundError, subprocess.CalledProcessError):
        return (
            subprocess.check_output(  # nosec dpkg-query
                ("dpkg-query", "-W", "-f=${Version}\n", "%s" % pkg),
                stderr=subprocess.STDOUT,
            )
            .strip()
            .decode("utf-8", errors="replace")
        )
    return ""


def debian_filename_version(binary):
    """
    Relies on Debian Policy rules for the existence of the
    changelog. Distributions not derived from Debian will
    return an empty string.
    """
    # if binary is not absolute, fail.
    msg = "Unable to retrieve version of %s" % binary
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
    pkg = pkg_str.split(":")[0]
    pkg_ver = debian_package_version(pkg)
    return "%s for <%s>, installed at version: %s" % (pkg, binary, pkg_ver)
