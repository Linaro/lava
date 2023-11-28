# Copyright (C) 2014 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

# List just the subclasses supported for this base strategy
# imported by the parser to populate the list of subclasses.

# pylint: disable=unused-import

from lava_dispatcher.actions.boot.barebox import Barebox
from lava_dispatcher.actions.boot.bootloader import BootBootloader
from lava_dispatcher.actions.boot.cmsis_dap import CMSIS
from lava_dispatcher.actions.boot.depthcharge import Depthcharge
from lava_dispatcher.actions.boot.dfu import DFU
from lava_dispatcher.actions.boot.docker import BootDocker
from lava_dispatcher.actions.boot.fastboot import BootFastboot
from lava_dispatcher.actions.boot.fvp import BootFVP
from lava_dispatcher.actions.boot.gdb import GDB
from lava_dispatcher.actions.boot.grub import Grub, GrubSequence
from lava_dispatcher.actions.boot.ipxe import IPXE
from lava_dispatcher.actions.boot.iso import BootIsoInstaller
from lava_dispatcher.actions.boot.jlink import JLink
from lava_dispatcher.actions.boot.kexec import BootKExec
from lava_dispatcher.actions.boot.lxc import BootLxc
from lava_dispatcher.actions.boot.minimal import Minimal
from lava_dispatcher.actions.boot.musca import Musca
from lava_dispatcher.actions.boot.nodebooter import BootNodebooter
from lava_dispatcher.actions.boot.openocd import OpenOCD
from lava_dispatcher.actions.boot.pyocd import PyOCD
from lava_dispatcher.actions.boot.qemu import BootQEMU
from lava_dispatcher.actions.boot.recovery import RecoveryBoot
from lava_dispatcher.actions.boot.secondary import SecondaryShell
from lava_dispatcher.actions.boot.ssh import Schroot, SshLogin
from lava_dispatcher.actions.boot.u_boot import UBoot
from lava_dispatcher.actions.boot.uefi import UefiShell
from lava_dispatcher.actions.boot.uefi_menu import UefiMenu
from lava_dispatcher.actions.boot.uuu import UUUBoot

try:
    from lava_dispatcher.actions.boot.avh import BootAvh
except ImportError:
    ...
