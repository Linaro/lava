# Copyright (C) 2024 Linaro Limited
#
# Author: Igor Ponomarev <igor.ponomarev@collabora.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

from typing import TYPE_CHECKING

from lava_common.exceptions import ConfigurationError, JobError

from .base_strategy import BaseStrategy

if TYPE_CHECKING:
    from lava_dispatcher.action import Action
    from lava_dispatcher.job import Job


class BootStrategy(BaseStrategy):
    section = "boot"
    name = "base-boot"

    @classmethod
    def check_subclass(cls, device, parameters) -> None:
        if not device:
            raise JobError('job "device" was None')
        if "method" not in parameters:
            raise ConfigurationError("method not specified in boot parameters")
        if "actions" not in device:
            raise ConfigurationError(
                'Invalid device configuration, no "actions" in device configuration'
            )
        if "boot" not in device["actions"]:
            raise ConfigurationError(
                '"boot" is not in the device configuration actions'
            )
        if "methods" not in device["actions"]["boot"]:
            raise ConfigurationError(
                'Device misconfiguration, no "methods" in device configuration boot action'
            )


class BootAvh(BootStrategy):
    @classmethod
    def action(cls, job: Job) -> Action:
        from lava_dispatcher.actions.boot.avh import BootAvhAction

        return BootAvhAction(job)

    @classmethod
    def accepts(cls, device, parameters) -> tuple[bool, str]:
        if "avh" not in device["actions"]["boot"]["methods"]:
            return False, "'avh' not in the device configuration boot methods"
        if parameters["method"] != "avh":
            return False, "'method' is not 'avh'"
        return True, "accepted"


class Barebox(BootStrategy):
    """
    The Barebox method prepares the command to run on the dispatcher but this
    command needs to start a new connection and then interrupt barebox.
    An expect shell session can then be handed over to the BareboxAction.
    self.run_command is a blocking call, so Boot needs to use
    a direct spawn call via ShellCommand (which wraps pexpect.spawn) then
    hand this pexpect wrapper to subsequent actions as a shell connection.
    """

    @classmethod
    def action(cls, job: Job) -> Action:
        from lava_dispatcher.actions.boot.barebox import BareboxAction

        return BareboxAction(job)

    @classmethod
    def accepts(cls, device, parameters) -> tuple[bool, str]:
        if parameters["method"] != "barebox":
            return False, '"method" was not "barebox"'
        if "commands" not in parameters:
            raise ConfigurationError("commands not specified in boot parameters")
        if "barebox" in device["actions"]["boot"]["methods"]:
            return True, "accepted"
        return False, '"barebox" was not in the device configuration boot methods'


class BootBootloader(BootStrategy):
    @classmethod
    def action(cls, job: Job) -> Action:
        from lava_dispatcher.actions.boot.bootloader import BootBootloaderRetry

        return BootBootloaderRetry(job)

    @classmethod
    def accepts(cls, device, parameters) -> tuple[bool, str]:
        if parameters["method"] != "bootloader":
            return False, "'method' was not 'bootloader'"
        if "bootloader" not in parameters:
            return False, "'bootloader' is undefined"
        bootloader = parameters["bootloader"]
        if bootloader not in device["actions"]["boot"]["methods"]:
            return (
                False,
                "boot method '%s' not in the device configuration" % bootloader,
            )
        return True, "accepted"


class CMSIS(BootStrategy):
    @classmethod
    def action(cls, job: Job) -> Action:
        from lava_dispatcher.actions.boot.cmsis_dap import BootCMSISRetry

        return BootCMSISRetry(job)

    @classmethod
    def accepts(cls, device, parameters) -> tuple[bool, str]:
        if "cmsis-dap" not in device["actions"]["boot"]["methods"]:
            return False, '"cmsis-dap" is not in the device configuration boot methods'
        if parameters["method"] != "cmsis-dap":
            return False, '"method" was not "cmsis-dap"'
        if "board_id" not in device:
            return False, 'device has no "board_id" configured'
        if "parameters" not in device["actions"]["boot"]["methods"]["cmsis-dap"]:
            return (
                False,
                '"parameters" was not in the device boot method configuration for "cmsis-dap"',
            )
        if (
            "usb_mass_device"
            not in device["actions"]["boot"]["methods"]["cmsis-dap"]["parameters"]
        ):
            return (
                False,
                '"usb_mass_device" was not in the device configuration "cmsis-dap" boot method parameters',
            )
        return True, "accepted"


class Depthcharge(BootStrategy):
    """
    Depthcharge is a payload used by Coreboot in recent ChromeOS machines.
    This boot strategy works with the "dev" build variant of Depthcharge, which
    enables an interactive command line interface and the tftpboot command to
    download files over TFTP. This includes at least a kernel image and a
    command line file.  On arm/arm64, the kernel image is in the FIT format,
    which can include a device tree blob and a ramdisk.  On x86, the kernel
    image is a plain bzImage and an optional ramdisk can be downloaded as a
    separate file.
    """

    @classmethod
    def action(cls, job: Job) -> Action:
        from lava_dispatcher.actions.boot.depthcharge import DepthchargeAction

        return DepthchargeAction(job)

    @classmethod
    def accepts(cls, device, parameters) -> tuple[bool, str]:
        if parameters["method"] != "depthcharge":
            return False, '"method" was not "depthcharge"'
        if "commands" not in parameters:
            raise ConfigurationError("commands not specified in boot parameters")
        if "depthcharge" not in device["actions"]["boot"]["methods"]:
            return (
                False,
                '"depthcharge" was not in the device configuration boot methods',
            )
        return True, "accepted"


class DFU(BootStrategy):
    @classmethod
    def action(cls, job: Job) -> Action:
        from lava_dispatcher.actions.boot.dfu import BootDFURetry

        return BootDFURetry(job)

    @classmethod
    def accepts(cls, device, parameters) -> tuple[bool, str]:
        if "dfu" not in device["actions"]["boot"]["methods"]:
            return False, '"dfu" was not in the device configuration boot methods'
        if parameters["method"] != "dfu":
            return False, '"method" was not "dfu"'
        if "board_id" not in device:
            return False, '"board_id" is not in the device configuration'
        return True, "accepted"


class BootDocker(BootStrategy):
    @classmethod
    def action(cls, job: Job) -> Action:
        from lava_dispatcher.actions.boot.docker import BootDockerAction

        return BootDockerAction(job)

    @classmethod
    def accepts(cls, device, parameters) -> tuple[bool, str]:
        if "docker" not in device["actions"]["boot"]["methods"]:
            return False, '"docker" was not in the device configuration boot methods'
        if parameters["method"] != "docker":
            return False, '"method" was not "docker"'
        if "command" not in parameters:
            return False, '"command" was not in boot parameters'
        return True, "accepted"


class BootFastboot(BootStrategy):
    """
    Expects fastboot bootloader, and boots.
    """

    @classmethod
    def action(cls, job: Job) -> Action:
        from lava_dispatcher.actions.boot.fastboot import BootFastbootAction

        return BootFastbootAction(job)

    @classmethod
    def accepts(cls, device, parameters) -> tuple[bool, str]:
        if parameters["method"] != "fastboot":
            return False, 'boot "method" was not "fastboot"'

        return True, "accepted"


class BootFVP(BootStrategy):
    @classmethod
    def action(cls, job: Job) -> Action:
        from lava_dispatcher.actions.boot.fvp import BootFVPAction

        return BootFVPAction(job)

    @classmethod
    def accepts(cls, device, parameters) -> tuple[bool, str]:
        if "fvp" not in device["actions"]["boot"]["methods"]:
            return False, '"fvp" was not in the device configuration boot methods'
        if parameters["method"] != "fvp":
            return False, '"method" was not "fvp"'
        if "image" not in parameters:
            return False, '"image" was not in boot parameters'
        return True, "accepted"


class GDB(BootStrategy):
    @classmethod
    def action(cls, job: Job) -> Action:
        from lava_dispatcher.actions.boot.gdb import BootGDB

        return BootGDB(job)

    @classmethod
    def accepts(cls, device, parameters) -> tuple[bool, str]:
        methods = device["actions"]["boot"]["methods"]
        if "gdb" not in methods:
            return False, '"gdb" is not in the device configuration boot methods'
        if parameters["method"] != "gdb":
            return False, '"method" was not "gdb"'
        if "commands" not in parameters:
            return False, '"commands" not in parameters'
        if parameters["commands"] not in methods["gdb"]:
            return (
                False,
                'commands "%s" undefined for the device' % parameters["commands"],
            )

        return True, "accepted"


class GrubSequence(BootStrategy):
    @classmethod
    def action(cls, job: Job) -> Action:
        from lava_dispatcher.actions.boot.grub import GrubSequenceAction

        return GrubSequenceAction(job)

    @classmethod
    def accepts(cls, device, parameters) -> tuple[bool, str]:
        if parameters["method"] not in ["grub", "grub-efi"]:
            return False, '"method" was not "grub" or "grub-efi"'

        params = device["actions"]["boot"]["methods"]
        if "grub" not in params:
            return False, '"grub" was not in the device configuration boot methods'
        if "grub-efi" in params:
            return False, '"grub-efi" was not in the device configuration boot methods'
        if "sequence" in params["grub"]:
            return True, "accepted"
        return False, '"sequence" not in device configuration boot methods'


class Grub(BootStrategy):
    @classmethod
    def action(cls, job: Job) -> Action:
        from lava_dispatcher.actions.boot.grub import GrubMainAction

        return GrubMainAction(job)

    @classmethod
    def accepts(cls, device, parameters) -> tuple[bool, str]:
        if parameters["method"] not in ["grub", "grub-efi"]:
            return False, '"method" was not "grub" or "grub-efi"'

        params = device["actions"]["boot"]["methods"]
        if "grub" in params and "sequence" in params["grub"]:
            return False, '"sequence" was in "grub" parameters'
        if "grub" in params or "grub-efi" in params:
            return True, "accepted"
        else:
            return (
                False,
                '"grub" or "grub-efi" was not in the device configuration boot methods',
            )


class IPXE(BootStrategy):
    """
    The IPXE method prepares the command to run on the dispatcher but this
    command needs to start a new connection and then interrupt iPXE.
    An expect shell session can then be handed over to the BootloaderAction.
    self.run_command is a blocking call, so Boot needs to use
    a direct spawn call via ShellCommand (which wraps pexpect.spawn) then
    hand this pexpect wrapper to subsequent actions as a shell connection.
    """

    @classmethod
    def action(cls, job: Job) -> Action:
        from lava_dispatcher.actions.boot.ipxe import BootloaderAction

        return BootloaderAction(job)

    @classmethod
    def accepts(cls, device, parameters) -> tuple[bool, str]:
        if parameters["method"] != "ipxe":
            return False, '"method" was not "ipxe"'
        if "ipxe" in device["actions"]["boot"]["methods"]:
            return True, "accepted"
        else:
            return False, '"ipxe" was not in the device configuration boot methods'


class BootIsoInstaller(BootStrategy):
    @classmethod
    def action(cls, job: Job) -> Action:
        from lava_dispatcher.actions.boot.iso import BootIsoInstallerAction

        return BootIsoInstallerAction(job)

    @classmethod
    def accepts(cls, device, parameters) -> tuple[bool, str]:
        if parameters["method"] != "qemu-iso":
            return False, '"method" was not "qemu-iso"'
        if "media" not in parameters:
            return False, '"media" was not in parameters'
        if parameters["media"] != "img":
            return False, '"media" was not "img"'

        return True, "accepted"


class JLink(BootStrategy):
    @classmethod
    def action(cls, job: Job) -> Action:
        from lava_dispatcher.actions.boot.jlink import BootJLinkRetry

        return BootJLinkRetry(job)

    @classmethod
    def accepts(cls, device, parameters) -> tuple[bool, str]:
        if "jlink" not in device["actions"]["boot"]["methods"]:
            return False, '"jlink" was not in the device configuration boot methods'
        if parameters["method"] != "jlink":
            return False, '"method" was not "jlink"'
        if "board_id" not in device:
            return False, '"board_id" is not in the device configuration'
        return True, "accepted"


class BootKExec(BootStrategy):
    """
    Expects a shell session, checks for kexec executable and
    prepares the arguments to run kexec,
    """

    @classmethod
    def action(cls, job: Job) -> Action:
        from lava_dispatcher.actions.boot.kexec import BootKexecAction

        return BootKexecAction(job)

    @classmethod
    def accepts(cls, device, parameters) -> tuple[bool, str]:
        if parameters["method"] != "kexec":
            return False, '"method" was not "kexec"'

        return True, "accepted"


class BootLxc(BootStrategy):
    """
    Attaches to the lxc container.
    """

    @classmethod
    def action(cls, job: Job) -> Action:
        from lava_dispatcher.actions.boot.lxc import BootLxcAction

        return BootLxcAction(job)

    @classmethod
    def accepts(cls, device, parameters) -> tuple[bool, str]:
        if parameters["method"] != "lxc":
            return False, '"method" was not "lxc"'

        return True, "accepted"


class Minimal(BootStrategy):
    @classmethod
    def action(cls, job: Job) -> Action:
        from lava_dispatcher.actions.boot.minimal import MinimalBoot

        return MinimalBoot(job)

    @classmethod
    def accepts(cls, device, parameters) -> tuple[bool, str]:
        if "minimal" not in device["actions"]["boot"]["methods"]:
            return False, '"minimal" was not in device configuration boot methods'
        if parameters["method"] != "minimal":
            return False, '"method" was not "minimal"'
        return True, "accepted"


class Musca(BootStrategy):
    @classmethod
    def action(cls, job: Job) -> Action:
        from lava_dispatcher.actions.boot.musca import MuscaBoot

        return MuscaBoot(job)

    @classmethod
    def accepts(cls, device, parameters) -> tuple[bool, str]:
        if "musca" not in device["actions"]["boot"]["methods"]:
            return False, '"musca" was not in device configuration boot methods'
        if parameters["method"] != "musca":
            return False, '"method" was not "musca"'
        if "board_id" not in device:
            return False, '"board_id" is not in the device configuration'
        return True, "accepted"


class BootNodebooter(BootStrategy):
    @classmethod
    def action(cls, job: Job) -> Action:
        from lava_dispatcher.actions.boot.nodebooter import BootNodebooterAction

        return BootNodebooterAction(job)

    @classmethod
    def accepts(cls, device, parameters) -> tuple[bool, str]:
        if "nodebooter" not in device["actions"]["boot"]["methods"]:
            return (
                False,
                '"nodebooter" was not in the device configuration boot methods',
            )
        if parameters["method"] != "nodebooter":
            return False, '"method" was not "nodebooter"'
        return True, "accepted"


class OpenOCD(BootStrategy):
    @classmethod
    def action(cls, job: Job) -> Action:
        from lava_dispatcher.actions.boot.openocd import BootOpenOCDRetry

        return BootOpenOCDRetry(job)

    @classmethod
    def accepts(cls, device, parameters) -> tuple[bool, str]:
        if "openocd" not in device["actions"]["boot"]["methods"]:
            return False, '"openocd" was not in the device configuration boot methods'
        if parameters["method"] != "openocd":
            return False, '"method" was not "openocd"'
        if "board_id" not in device:
            return False, '"board_id" is not in the device configuration'
        return True, "accepted"


class PyOCD(BootStrategy):
    @classmethod
    def action(cls, job: Job) -> Action:
        from lava_dispatcher.actions.boot.pyocd import BootPyOCD

        return BootPyOCD(job)

    @classmethod
    def accepts(cls, device, parameters) -> tuple[bool, str]:
        if "pyocd" not in device["actions"]["boot"]["methods"]:
            return False, '"pyocd" was not in the device configuration boot methods'
        if parameters["method"] != "pyocd":
            return False, '"method" was not "pyocd"'
        if "board_id" not in device:
            return False, '"board_id" is not in the device configuration'
        return True, "accepted"


class BootQEMU(BootStrategy):
    """
    The Boot method prepares the command to run on the dispatcher but this
    command needs to start a new connection and then allow AutoLogin, if
    enabled, and then expect a shell session which can be handed over to the
    test method. self.run_command is a blocking call, so Boot needs to use
    a direct spawn call via ShellCommand (which wraps pexpect.spawn) then
    hand this pexpect wrapper to subsequent actions as a shell connection.
    """

    @classmethod
    def action(cls, job: Job) -> Action:
        from lava_dispatcher.actions.boot.qemu import BootQEMUImageAction

        return BootQEMUImageAction(job)

    @classmethod
    def accepts(cls, device, parameters) -> tuple[bool, str]:
        methods = device["actions"]["boot"]["methods"]
        if "qemu" not in methods and "qemu-nfs" not in methods:
            return (
                False,
                '"qemu" or "qemu-nfs" was not in the device configuration boot methods',
            )
        if parameters["method"] not in ["qemu", "qemu-nfs", "monitor"]:
            return False, '"method" was not "qemu" or "qemu-nfs"'
        return True, "accepted"


class RecoveryBoot(BootStrategy):
    @classmethod
    def action(cls, job: Job) -> Action:
        from lava_dispatcher.actions.boot.recovery import RecoveryBootAction

        return RecoveryBootAction(job)

    @classmethod
    def accepts(cls, device, parameters) -> tuple[bool, str]:
        if parameters["method"] != "recovery":
            return False, 'boot "method" was not "recovery"'

        return True, "accepted"


class SecondaryShell(BootStrategy):
    """
    SecondaryShell method can be used by a variety of other boot methods to
    read from the kernel console independently of the shell interaction
    required to interact with the bootloader and test shell.
    It is also the updated way to connect to the primary console.
    """

    @classmethod
    def action(cls, job: Job) -> Action:
        from lava_dispatcher.actions.boot.secondary import SecondaryShellAction

        return SecondaryShellAction(job)

    @classmethod
    def accepts(cls, device, parameters) -> tuple[bool, str]:
        if parameters["method"] != "new_connection":
            return False, "new_connection not in method"
        if "method" not in parameters:
            return False, "no boot method"
        return True, "accepted"


class SshLogin(BootStrategy):
    """
    Ssh boot strategy is a login process, without actually booting a kernel
    but still needs AutoLoginAction.
    """

    @classmethod
    def action(cls, job: Job) -> Action:
        from lava_dispatcher.actions.boot.ssh import SshAction

        return SshAction(job)

    @classmethod
    def accepts(cls, device, parameters) -> tuple[bool, str]:
        if "ssh" not in device["actions"]["boot"]["methods"]:
            return False, '"ssh" not in device configuration boot methods'
        if "ssh" not in parameters["method"]:
            return False, '"ssh" not in "method"'
        return True, "accepted"


class Schroot(BootStrategy):
    @classmethod
    def action(cls, job: Job) -> Action:
        from lava_dispatcher.actions.boot.ssh import SchrootAction

        return SchrootAction(job)

    @classmethod
    def accepts(cls, device, parameters) -> tuple[bool, str]:
        if "schroot" not in device["actions"]["boot"]["methods"]:
            return False, '"schroot" was not in the device configuration boot methods'
        if "schroot" not in parameters["method"]:
            return False, '"method" was not "schroot"'
        return True, "accepted"


class UBoot(BootStrategy):
    """
    The UBoot method prepares the command to run on the dispatcher but this
    command needs to start a new connection and then interrupt u-boot.
    An expect shell session can then be handed over to the UBootAction.
    self.run_command is a blocking call, so Boot needs to use
    a direct spawn call via ShellCommand (which wraps pexpect.spawn) then
    hand this pexpect wrapper to subsequent actions as a shell connection.
    """

    @classmethod
    def action(cls, job: Job) -> Action:
        from lava_dispatcher.actions.boot.u_boot import UBootAction

        return UBootAction(job)

    @classmethod
    def accepts(cls, device, parameters) -> tuple[bool, str]:
        if parameters["method"] != "u-boot":
            return False, '"method" was not "u-boot"'
        if "commands" not in parameters:
            raise ConfigurationError("commands not specified in boot parameters")
        if "u-boot" in device["actions"]["boot"]["methods"]:
            return True, "accepted"
        return False, '"u-boot" was not in the device configuration boot methods'


class UefiShell(BootStrategy):
    @classmethod
    def action(cls, job: Job) -> Action:
        from lava_dispatcher.actions.boot.uefi import UefiShellAction

        return UefiShellAction(job)

    @classmethod
    def accepts(cls, device, parameters) -> tuple[bool, str]:
        if parameters["method"] != "uefi":
            return False, '"method" was not "uefi"'
        if "uefi" in device["actions"]["boot"]["methods"]:
            params = device["actions"]["boot"]["methods"]["uefi"]["parameters"]
            if not params:
                return (
                    False,
                    'there were no parameters in the "uefi" device configuration boot method',
                )
            if "shell_interrupt_string" not in params:
                return (
                    False,
                    '"shell_interrupt_string" was not in the uefi device configuration boot method parameters',
                )
            if "shell_interrupt_prompt" in params and "bootloader_prompt" in params:
                return True, "accepted"
        return (
            False,
            "missing or invalid parameters in the uefi device configuration boot methods",
        )


class UefiMenu(BootStrategy):
    """
    The UEFI Menu strategy selects the specified options
    and inserts relevant strings into the UEFI menu instead
    of issuing commands over a shell-like serial connection.
    """

    @classmethod
    def action(cls, job: Job) -> Action:
        from lava_dispatcher.actions.boot.uefi_menu import UefiMenuAction

        return UefiMenuAction(job)

    @classmethod
    def accepts(cls, device, parameters) -> tuple[bool, str]:
        if parameters["method"] != "uefi-menu":
            return False, '"method" was not "uefi-menu"'
        if "uefi-menu" in device["actions"]["boot"]["methods"]:
            params = device["actions"]["boot"]["methods"]["uefi-menu"]["parameters"]
            if "interrupt_prompt" in params and "interrupt_string" in params:
                return True, "accepted"
            else:
                return (
                    False,
                    '"interrupt_prompt" or "interrupt_string" was not in the device configuration uefi-menu boot method parameters',
                )
        return False, '"uefi-menu" was not in the device configuration boot methods'


class UUUBoot(BootStrategy):
    """
    The UUUBoot method allow to always boot on USB serial download mode
    used by uuu to flash on boot media a fresh bootimage.

    If the board is not available for USB serial download, action 'boot-corrupt-boot-media'
    will run commands in u-boot to corrupt boot media. After this action, board must be available in USB serial download
    mode.
    if the board is available without the previous action, 'boot-corrupt-boot-media' won't add anything to pipeline.

    """

    @classmethod
    def action(cls, job: Job) -> Action:
        from lava_dispatcher.actions.boot.uuu import UUUBootRetryAction

        return UUUBootRetryAction(job)

    @classmethod
    def accepts(cls, device, parameters) -> tuple[bool, str]:
        if parameters["method"] != "uuu":
            return False, '"method" was not "uuu"'
        if "commands" not in parameters:
            raise ConfigurationError("commands not specified in boot parameters")
        params = device["actions"]["boot"]["methods"]["uuu"]["options"]
        if not params["usb_otg_path"] and not params["usb_otg_path_command"]:
            raise ConfigurationError(
                "'uuu_usb_otg_path' or 'uuu_usb_otg_path_command' not defined in device definition"
            )
        if params["corrupt_boot_media_command"] is None:
            raise ConfigurationError(
                "uuu_corrupt_boot_media_command not defined in device definition"
            )
        if "u-boot" in device["actions"]["boot"]["methods"]:
            return True, "accepted"
        return False, '"uuu" was not in the device configuration boot methods'
