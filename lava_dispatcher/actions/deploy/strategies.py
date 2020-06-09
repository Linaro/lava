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

from lava_dispatcher.actions.deploy.docker import Docker
from lava_dispatcher.actions.deploy.download import Download
from lava_dispatcher.actions.deploy.downloads import Downloads
from lava_dispatcher.actions.deploy.image import DeployImages
from lava_dispatcher.actions.deploy.iso import DeployIso
from lava_dispatcher.actions.deploy.fastboot import Fastboot
from lava_dispatcher.actions.deploy.flasher import Flasher
from lava_dispatcher.actions.deploy.fvp import FVP
from lava_dispatcher.actions.deploy.lxc import Lxc
from lava_dispatcher.actions.deploy.overlay import Overlay
from lava_dispatcher.actions.deploy.nbd import Nbd
from lava_dispatcher.actions.deploy.nfs import Nfs
from lava_dispatcher.actions.deploy.removable import MassStorage
from lava_dispatcher.actions.deploy.mps import Mps
from lava_dispatcher.actions.deploy.musca import Musca
from lava_dispatcher.actions.deploy.ssh import Ssh
from lava_dispatcher.actions.deploy.tftp import Tftp
from lava_dispatcher.actions.deploy.uboot_ums import UBootUMS
from lava_dispatcher.actions.deploy.vemsd import VExpressMsd
from lava_dispatcher.actions.deploy.recovery import RecoveryMode
from lava_dispatcher.actions.deploy.uuu import UUU
