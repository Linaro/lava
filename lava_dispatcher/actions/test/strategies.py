# Copyright (C) 2014 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

# List just the subclasses supported for this base strategy
# imported by the parser to populate the list of subclasses.

# pylint: disable=unused-import

from lava_dispatcher.actions.test.docker import DockerTestShell
from lava_dispatcher.actions.test.interactive import TestInteractive
from lava_dispatcher.actions.test.monitor import TestMonitor
from lava_dispatcher.actions.test.multinode import MultinodeTestShell
from lava_dispatcher.actions.test.shell import TestShell
