# Copyright (C) 2013 Neil Williams
#
# Author: Neil Williams <codehelp@debian.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from os.path import abspath
from sys import path

path.insert(0, abspath(".."))

from lava_common.version import version as lava_version

project = "LAVA"
copyright = "2010-2024, Linaro Limited"
version = lava_version()
release = version

exclude_patterns = ["_build"]
master_doc = "lava-server"  # Do not require index.rst
man_pages = [
    (
        "lava-coordinator",
        "lava-coordinator",
        "manage multinode communications",
        ["Linaro Validation Team"],
        1,
    ),
    (
        "lava-server",
        "lava-server",
        "lava-server command line support",
        ["Linaro Validation Team"],
        1,
    ),
    ("lava-run", "lava-run", "run jobs on LAVA devices", ["Linaro Validation Team"], 1),
    (
        "lava-worker",
        "lava-worker",
        "manage connections to lava server",
        ["Linaro Validation Team"],
        8,
    ),
    (
        "lava-lxc-mocker",
        "lava-lxc-mocker",
        "mock LXC commands used by LAVA",
        ["Senthil Kumaran S <senthil.kumaran@linaro.org>"],
        7,
    ),
    (
        "lxc-attach",
        "lxc-attach",
        "mock lxc-attach command used by LAVA",
        ["Senthil Kumaran S <senthil.kumaran@linaro.org>"],
        1,
    ),
    (
        "lxc-create",
        "lxc-create",
        "mock lxc-create command used by LAVA",
        ["Senthil Kumaran S <senthil.kumaran@linaro.org>"],
        1,
    ),
    (
        "lxc-destroy",
        "lxc-destroy",
        "mock lxc-destroy command used by LAVA",
        ["Senthil Kumaran S <senthil.kumaran@linaro.org>"],
        1,
    ),
    (
        "lxc-device",
        "lxc-device",
        "mock lxc-device command used by LAVA",
        ["Senthil Kumaran S <senthil.kumaran@linaro.org>"],
        1,
    ),
    (
        "lxc-info",
        "lxc-info",
        "mock lxc-info command used by LAVA",
        ["Senthil Kumaran S <senthil.kumaran@linaro.org>"],
        1,
    ),
    (
        "lxc-start",
        "lxc-start",
        "mock lxc-start command used by LAVA",
        ["Senthil Kumaran S <senthil.kumaran@linaro.org>"],
        1,
    ),
    (
        "lxc-stop",
        "lxc-stop",
        "mock lxc-stop command used by LAVA",
        ["Senthil Kumaran S <senthil.kumaran@linaro.org>"],
        1,
    ),
]
