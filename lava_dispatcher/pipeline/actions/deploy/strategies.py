# Copyright (C) 2014 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# This file is part of LAVA Dispatcher.
#
# LAVA Dispatcher is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# LAVA Dispatcher is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along
# with this program; if not, see <http://www.gnu.org/licenses>.

# List just the subclasses supported for this base strategy
# imported by the parser to populate the list of subclasses.

# pylint: disable=unused-import

from lava_dispatcher.pipeline.actions.deploy.image import DeployImages
from lava_dispatcher.pipeline.actions.deploy.tftp import Tftp
from lava_dispatcher.pipeline.actions.deploy.removable import MassStorage
from lava_dispatcher.pipeline.actions.deploy.ssh import Ssh
from lava_dispatcher.pipeline.actions.deploy.fastboot import Fastboot
from lava_dispatcher.pipeline.actions.deploy.lxc import Lxc
from lava_dispatcher.pipeline.actions.deploy.iso import DeployIso
from lava_dispatcher.pipeline.actions.deploy.nfs import Nfs
from lava_dispatcher.pipeline.actions.deploy.vemsd import VExpressMsd
from lava_dispatcher.pipeline.actions.deploy.nbd import Nbd
