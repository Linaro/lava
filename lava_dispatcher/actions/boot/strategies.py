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

from lava_dispatcher.actions.boot import SecondaryShell
from lava_dispatcher.actions.boot.bootloader import BootBootloader
from lava_dispatcher.actions.boot.cmsis_dap import CMSIS
from lava_dispatcher.actions.boot.depthcharge import Depthcharge
from lava_dispatcher.actions.boot.dfu import DFU
from lava_dispatcher.actions.boot.docker import BootDocker
from lava_dispatcher.actions.boot.fastboot import BootFastboot
from lava_dispatcher.actions.boot.gdb import GDB
from lava_dispatcher.actions.boot.grub import Grub, GrubSequence
from lava_dispatcher.actions.boot.iso import BootIsoInstaller
from lava_dispatcher.actions.boot.ipxe import IPXE
from lava_dispatcher.actions.boot.kexec import BootKExec
from lava_dispatcher.actions.boot.lxc import BootLxc
from lava_dispatcher.actions.boot.minimal import Minimal
from lava_dispatcher.actions.boot.openocd import OpenOCD
from lava_dispatcher.actions.boot.pyocd import PyOCD
from lava_dispatcher.actions.boot.qemu import BootQEMU
from lava_dispatcher.actions.boot.ssh import SshLogin, Schroot
from lava_dispatcher.actions.boot.u_boot import UBoot
from lava_dispatcher.actions.boot.barebox import Barebox
from lava_dispatcher.actions.boot.uefi import UefiShell
from lava_dispatcher.actions.boot.uefi_menu import UefiMenu
from lava_dispatcher.actions.boot.recovery import RecoveryBoot
