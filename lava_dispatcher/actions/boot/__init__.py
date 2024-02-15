# Copyright (C) 2014-2019 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING

from lava_common.constants import (
    BOOTLOADER_DEFAULT_CMD_TIMEOUT,
    DISPATCHER_DOWNLOAD_DIR,
    LINE_SEPARATOR,
)
from lava_common.exceptions import (
    ConfigurationError,
    InfrastructureError,
    JobError,
    LAVABug,
)
from lava_common.timeout import Timeout
from lava_dispatcher.action import Action
from lava_dispatcher.utils.filesystem import write_bootscript
from lava_dispatcher.utils.network import dispatcher_ip
from lava_dispatcher.utils.strings import substitute

if TYPE_CHECKING:
    from lava_dispatcher.job import Job


class BootloaderCommandOverlay(Action):
    """
    Replace KERNEL_ADDR and DTB placeholders with the actual values for this
    particular pipeline.
    addresses are read from the device configuration parameters
    bootloader_type is determined from the boot action method strategy
    bootz or bootm is determined by deploy action kernel type.
    server_ip is calculated at runtime
    filenames are determined from the download Action.
    """

    name = "bootloader-overlay"
    description = "substitute job data into bootloader command list"
    summary = "replace placeholders with job data"

    def __init__(self, job: Job, method=None, commands=None):
        super().__init__(job)
        self.commands = commands
        self.method = method
        self.use_bootscript = False
        self.lava_mac = None
        self.bootcommand = ""
        self.ram_disk = None

    def validate(self):
        super().validate()
        if self.method is None:
            self.method = self.parameters["method"]
        device_methods = self.job.device["actions"]["boot"]["methods"]
        if self.commands is not None:
            return
        if self.parameters["method"] == "bootloader":
            self.commands = self.parameters["commands"]
        elif isinstance(self.parameters["commands"], list):
            self.commands = self.parameters["commands"]
            self.logger.warning(
                "WARNING: Using boot commands supplied in the job definition, NOT the LAVA device configuration"
            )
        else:
            if "commands" not in self.parameters:
                self.errors = "missing commands"
            elif self.parameters["commands"] not in device_methods[self.method]:
                self.errors = (
                    "Command '%s' not found in supported methods"
                    % self.parameters["commands"]
                )
            elif (
                "commands"
                not in device_methods[self.method][self.parameters["commands"]]
            ):
                self.errors = "No commands found in parameters"
            else:
                self.commands = device_methods[self.method][
                    self.parameters["commands"]
                ]["commands"]

        for cmd in self.commands:
            if not isinstance(cmd, str):
                self.errors = "Deploy Commands instruction is not a string: %r" % cmd

        # download-action will set ['dtb'] as tftp_path, tmpdir & filename later, in the run step.
        if "use_bootscript" in self.parameters:
            self.use_bootscript = self.parameters["use_bootscript"]

        lava_mac = None
        if "lava_mac" in device_methods[self.method]["parameters"]:
            lava_mac = device_methods[self.method]["parameters"]["lava_mac"]
        if lava_mac:
            if re.match("([0-9A-F]{2}[:-]){5}([0-9A-F]{2})", lava_mac, re.IGNORECASE):
                self.lava_mac = lava_mac
            else:
                self.errors = "lava_mac is not a valid mac address"

    def run(self, connection, max_end_time):
        """
        Read data from the download action and replace in context
        Use common data for all values passed into the substitutions so that
        multiple actions can use the same code.
        """
        # Multiple deployments would overwrite the value if parsed in the validate step.
        # FIXME: implement isolation for repeated steps.
        connection = super().run(connection, max_end_time)
        ip_addr = dispatcher_ip(self.job.parameters["dispatcher"])

        self.ram_disk = self.get_namespace_data(
            action="compress-ramdisk", label="file", key="ramdisk"
        )
        # most jobs substitute RAMDISK, so also use this for the initrd
        if self.get_namespace_data(action="nbd-deploy", label="nbd", key="initrd"):
            self.ram_disk = self.get_namespace_data(
                action="download-action", label="file", key="initrd"
            )

        substitutions = {
            "{SERVER_IP}": ip_addr,
            "{PRESEED_CONFIG}": self.get_namespace_data(
                action="download-action", label="file", key="preseed"
            ),
            "{PRESEED_LOCAL}": self.get_namespace_data(
                action="compress-ramdisk", label="file", key="preseed_local"
            ),
            "{DTB}": self.get_namespace_data(
                action="download-action", label="file", key="dtb"
            ),
            "{RAMDISK}": self.ram_disk,
            "{INITRD}": self.ram_disk,
            "{KERNEL}": self.get_namespace_data(
                action="download-action", label="file", key="kernel"
            ),
            "{LAVA_MAC}": self.lava_mac,
            "{TEE}": self.get_namespace_data(
                action="download-action", label="file", key="tee"
            ),
        }
        self.bootcommand = self.get_namespace_data(
            action="uboot-prepare-kernel", label="bootcommand", key="bootcommand"
        )
        if not self.bootcommand and "type" in self.parameters:
            raise JobError("Kernel image type can't be determined")
        prepared_kernel = self.get_namespace_data(
            action="prepare-kernel", label="file", key="kernel"
        )
        if prepared_kernel:
            self.logger.info(
                "Using kernel file from prepare-kernel: %s", prepared_kernel
            )
            substitutions["{KERNEL}"] = prepared_kernel
        if self.bootcommand:
            kernel_addr = self.job.device["parameters"][self.bootcommand]["kernel"]
            dtb_addr = self.job.device["parameters"][self.bootcommand]["dtb"]
            ramdisk_addr = self.job.device["parameters"][self.bootcommand]["ramdisk"]
            tee_addr = self.job.device["parameters"][self.bootcommand].get("tee")

            if (
                not self.get_namespace_data(
                    action="tftp-deploy", label="tftp", key="ramdisk"
                )
                and not self.get_namespace_data(
                    action="download-action", label="file", key="ramdisk"
                )
                and not self.get_namespace_data(
                    action="download-action", label="file", key="initrd"
                )
            ):
                ramdisk_addr = "-"
            add_header = self.job.device["actions"]["deploy"]["parameters"].get(
                "add_header"
            )
            if self.method == "u-boot" and not add_header == "u-boot":
                self.logger.debug("No u-boot header, not passing ramdisk to bootX cmd")
                ramdisk_addr = "-"

            if self.get_namespace_data(
                action="download-action", label="file", key="initrd"
            ):
                # no u-boot header, thus no embedded size, so we have to add it to the
                # boot cmd with colon after the ramdisk
                if self.get_namespace_data(
                    action="download-action", label="file", key="tee"
                ):
                    substitutions["{BOOTX}"] = "%s %s %s:%s %s" % (
                        self.bootcommand,
                        tee_addr,
                        ramdisk_addr,
                        "${initrd_size}",
                        dtb_addr,
                    )
                else:
                    substitutions["{BOOTX}"] = "%s %s %s:%s %s" % (
                        self.bootcommand,
                        kernel_addr,
                        ramdisk_addr,
                        "${initrd_size}",
                        dtb_addr,
                    )
            else:
                if self.get_namespace_data(
                    action="download-action", label="file", key="tee"
                ):
                    substitutions["{BOOTX}"] = "%s %s %s %s" % (
                        self.bootcommand,
                        tee_addr,
                        ramdisk_addr,
                        dtb_addr,
                    )
                else:
                    substitutions["{BOOTX}"] = "%s %s %s %s" % (
                        self.bootcommand,
                        kernel_addr,
                        ramdisk_addr,
                        dtb_addr,
                    )

            substitutions["{KERNEL_ADDR}"] = kernel_addr
            substitutions["{DTB_ADDR}"] = dtb_addr
            substitutions["{RAMDISK_ADDR}"] = ramdisk_addr
            substitutions["{TEE_ADDR}"] = tee_addr
            self.results = {
                "kernel_addr": kernel_addr,
                "dtb_addr": dtb_addr,
                "ramdisk_addr": ramdisk_addr,
                "tee_addr": tee_addr,
            }

        nfs_address = self.get_namespace_data(
            action="persistent-nfs-overlay", label="nfs_address", key="nfsroot"
        )
        nfs_root = self.get_namespace_data(
            action="download-action", label="file", key="nfsrootfs"
        )
        if nfs_root:
            substitutions["{NFSROOTFS}"] = self.get_namespace_data(
                action="extract-rootfs", label="file", key="nfsroot"
            )
            substitutions["{NFS_SERVER_IP}"] = ip_addr
        elif nfs_address:
            substitutions["{NFSROOTFS}"] = nfs_address
            substitutions["{NFS_SERVER_IP}"] = self.get_namespace_data(
                action="persistent-nfs-overlay", label="nfs_address", key="serverip"
            )

        if "lava-xnbd" in self.parameters:
            substitutions["{NBDSERVERIP}"] = str(
                self.get_namespace_data(
                    action="nbd-deploy", label="nbd", key="nbd_server_ip"
                )
            )
            substitutions["{NBDSERVERPORT}"] = str(
                self.get_namespace_data(
                    action="nbd-deploy", label="nbd", key="nbd_server_port"
                )
            )

        substitutions["{ROOT}"] = self.get_namespace_data(
            action="bootloader-from-media", label="uuid", key="root"
        )  # UUID label, not a file
        substitutions["{ROOT_PART}"] = self.get_namespace_data(
            action="bootloader-from-media", label="uuid", key="boot_part"
        )

        # Save the substitutions
        self.set_namespace_data(
            action=self.name,
            label=self.method,
            key="substitutions",
            value=substitutions,
        )

        if self.use_bootscript:
            script = "/script.ipxe"
            bootscript = (
                self.get_namespace_data(
                    action="tftp-deploy", label="tftp", key="tftp_dir"
                )
                + script
            )
            bootscripturi = "tftp://%s/%s" % (
                ip_addr,
                os.path.dirname(substitutions["{KERNEL}"]) + script,
            )
            write_bootscript(substitute(self.commands, substitutions), bootscript)
            bootscript_commands = ["dhcp net0", "chain %s" % bootscripturi]
            self.set_namespace_data(
                action=self.name,
                label=self.method,
                key="commands",
                value=bootscript_commands,
            )
            self.logger.info("Parsed boot commands: %s", "; ".join(bootscript_commands))
            return connection
        subs = substitute(self.commands, substitutions, drop=True)
        self.set_namespace_data(
            action="bootloader-overlay", label=self.method, key="commands", value=subs
        )
        self.logger.debug("substitutions:")
        for k in sorted(substitutions.keys()):
            self.logger.debug("- %s: %s", k, substitutions[k])
        self.logger.info("Parsed boot commands:")
        for sub in subs:
            self.logger.info("- %s", sub)
        return connection


class BootloaderSecondaryMedia(Action):
    """
    Generic class for secondary media substitutions
    """

    name = "bootloader-from-media"
    description = (
        "let bootloader know where to find the kernel in the image on secondary media"
    )
    summary = "set bootloader strings for deployed media"

    def validate(self):
        super().validate()
        if "media" not in self.job.device.get("parameters", []):
            return
        media_keys = self.job.device["parameters"]["media"].keys()
        commands = self.parameters["commands"]
        if isinstance(commands, list) or commands not in media_keys:
            return
        if "kernel" not in self.parameters:
            self.errors = "Missing kernel location"
        # ramdisk does not have to be specified, nor dtb
        if "root_uuid" not in self.parameters:
            # FIXME: root_node also needs to be supported
            self.errors = "Missing UUID of the roofs inside the deployed image"
        if "boot_part" not in self.parameters:
            self.errors = "Missing boot_part for the partition number of the boot files inside the deployed image"
        self.set_namespace_data(
            action="download-action",
            label="file",
            key="kernel",
            value=self.parameters.get("kernel", ""),
        )
        self.set_namespace_data(
            action="compress-ramdisk",
            label="file",
            key="ramdisk",
            value=self.parameters.get("ramdisk", ""),
        )
        self.set_namespace_data(
            action="download-action",
            label="file",
            key="ramdisk",
            value=self.parameters.get("ramdisk", ""),
        )
        self.set_namespace_data(
            action="download-action",
            label="file",
            key="dtb",
            value=self.parameters.get("dtb", ""),
        )
        self.set_namespace_data(
            action="bootloader-from-media",
            label="uuid",
            key="root",
            value=self.parameters.get("root_uuid", ""),
        )
        self.set_namespace_data(
            action="bootloader-from-media",
            label="uuid",
            key="boot_part",
            value=str(self.parameters.get("boot_part")),
        )


class OverlayUnpack(Action):
    """
    Transfer the overlay.tar.gz to the device using test writer tools
    Can be used with inline bootloader commands or where the rootfs is
    not deployed directly by LAVA.
    Whether the device has booted by tftp or ipxe or something else does
    not matter for this action - the file will be downloaded from the
    worker tmp dir using the default apache config.
    """

    name = "overlay-unpack"
    description = "transfer and unpack overlay to persistent rootfs after login"
    summary = "transfer and unpack overlay"

    def validate(self):
        super().validate()
        if "transfer_overlay" not in self.parameters:
            self.errors = "Unable to identify transfer commands for overlay."
            return
        if "download_command" not in self.parameters["transfer_overlay"]:
            self.errors = "Unable to identify download command for overlay."
        if "unpack_command" not in self.parameters["transfer_overlay"]:
            self.errors = "Unable to identify unpack command for overlay."

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)
        if not connection:
            raise LAVABug("Cannot transfer overlay, no connection available.")

        transfer_method = self.parameters["transfer_overlay"].get(
            "transfer_method", "http"
        )

        if transfer_method == "http":
            overlay_full_path = self.get_namespace_data(
                action="compress-overlay", label="output", key="file"
            )
            if not overlay_full_path:
                raise JobError("No overlay file identified for the transfer.")
            if not overlay_full_path.startswith(DISPATCHER_DOWNLOAD_DIR):
                raise ConfigurationError(
                    "overlay should already be in DISPATCHER_DOWNLOAD_DIR"
                )
            overlay_path = overlay_full_path[len(DISPATCHER_DOWNLOAD_DIR) + 1 :]
            overlay = os.path.basename(overlay_path)

            connection.sendline("rm %s" % overlay, delay=self.character_delay)
            connection.wait()

            cmd = self.parameters["transfer_overlay"]["download_command"]
            ip_addr = dispatcher_ip(self.job.parameters["dispatcher"], "http")
            connection.sendline(
                "%s http://%s/tmp/%s" % (cmd, ip_addr, overlay_path),
                delay=self.character_delay,
            )
            connection.wait()

            unpack = self.parameters["transfer_overlay"]["unpack_command"]
            connection.sendline(unpack + " " + overlay, delay=self.character_delay)
            connection.wait()
        elif transfer_method == "nfs":
            location = self.get_namespace_data(
                action="test", label="shared", key="location"
            )

            cmd = self.parameters["transfer_overlay"]["download_command"]
            ip_addr = dispatcher_ip(self.job.parameters["dispatcher"], "nfs")
            mount_dir = f"/{os.path.basename(location)}"
            connection.sendline(
                "mkdir -p %s; %s %s:%s %s"
                % (mount_dir, cmd, ip_addr, location, mount_dir),
                delay=self.character_delay,
            )
            connection.wait()

            unpack = self.parameters["transfer_overlay"]["unpack_command"]
            connection.sendline(
                "%s %s/* /; umount %s; rm -fr %s"
                % (unpack, mount_dir, mount_dir, mount_dir),
                delay=self.character_delay,
            )
            connection.wait()

        return connection


class BootloaderInterruptAction(Action):
    """
    Support for interrupting the bootloader.
    """

    name = "bootloader-interrupt"
    description = "interrupt bootloader"
    summary = "interrupt bootloader to get an interactive shell"
    timeout_exception = InfrastructureError

    def __init__(self, job: Job, method=None):
        super().__init__(job)
        self.params = {}
        self.method = method
        self.needs_interrupt = False

    def validate(self):
        super().validate()
        # 'to' only exists in deploy, this action can be used in boot too.
        deployment = self.parameters.get("to", "")
        boot_method = self.parameters.get("method", "")
        if self.method is None:
            if deployment in ["fastboot", "download"] or boot_method in [
                "fastboot",
                "download",
            ]:
                if self.job.device.get("fastboot_via_uboot", False):
                    self.method = "u-boot"
            else:
                self.method = self.parameters["method"]
        self.params = self.job.device["actions"]["boot"]["methods"][self.method][
            "parameters"
        ]
        if self.job.device.connect_command == "":
            self.errors = "Unable to connect to device %s"
        device_methods = self.job.device["actions"]["boot"]["methods"]
        if (
            self.parameters.get("method", "") == "grub-efi"
            and "grub-efi" in device_methods
        ):
            self.method = "grub-efi"
        if "bootloader_prompt" not in self.params:
            self.errors = "Missing bootloader prompt for device"
        self.bootloader_prompt = self.params["bootloader_prompt"]
        self.interrupt_prompt = self.params.get(
            "interrupt_prompt",
            self.job.device.get_constant("interrupt-prompt", prefix=self.method),
        )
        self.needs_interrupt = self.params.get("needs_interrupt", True)
        self.interrupt_newline = self.job.device.get_constant(
            "interrupt-newline",
            prefix=self.method,
            missing_ok=True,
            missing_default=True,
        )
        # interrupt_char can actually be a sequence of ASCII characters - sendline does not care.
        self.interrupt_char = None
        if self.method != "ipxe":
            # ipxe only need interrupt_ctrl_list, not a single char.
            self.interrupt_char = self.params.get(
                "interrupt_char",
                self.job.device.get_constant("interrupt-character", prefix=self.method),
            )
        # vendor u-boot builds may require one or more control characters
        self.interrupt_control_chars = self.params.get(
            "interrupt_ctrl_list",
            self.job.device.get_constant(
                "interrupt_ctrl_list", prefix=self.method, missing_ok=True
            ),
        )

    def run(self, connection, max_end_time):
        if not connection:
            raise LAVABug("%s started without a connection already in use" % self.name)
        connection = super().run(connection, max_end_time)
        if self.needs_interrupt:
            connection.prompt_str = [self.interrupt_prompt]
            self.wait(connection)
            if self.interrupt_control_chars:
                for char in self.interrupt_control_chars:
                    connection.sendcontrol(char)
            else:
                if self.interrupt_newline:
                    connection.sendline(self.interrupt_char)
                else:
                    connection.send(self.interrupt_char)
        else:
            self.logger.info(
                "Not interrupting bootloader, waiting for bootloader prompt"
            )
            connection.prompt_str = [self.bootloader_prompt]
            self.wait(connection)
            self.set_namespace_data(
                action="interrupt",
                label="interrupt",
                key="at_bootloader_prompt",
                value=True,
            )
        return connection


class BootloaderCommandsAction(Action):
    """
    Send the boot commands to the bootloader
    """

    name = "bootloader-commands"
    description = "send commands to bootloader"
    summary = "interactive bootloader"
    timeout_exception = InfrastructureError

    def __init__(self, job: Job, expect_final=True, method=None):
        super().__init__(job)
        self.params = None
        self.timeout = Timeout(
            self.name,
            self,
            duration=BOOTLOADER_DEFAULT_CMD_TIMEOUT,
            exception=self.timeout_exception,
        )
        self.method = method
        self.expect_final = expect_final

    def validate(self):
        super().validate()
        if self.method is None:
            self.method = self.parameters["method"]
        self.params = self.job.device["actions"]["boot"]["methods"][self.method][
            "parameters"
        ]

    def line_separator(self):
        return LINE_SEPARATOR

    def run(self, connection, max_end_time):
        if not connection:
            self.errors = "%s started without a connection already in use" % self.name
        connection = super().run(connection, max_end_time)
        connection.raw_connection.linesep = self.line_separator()
        connection.prompt_str = [self.params["bootloader_prompt"]]
        at_bootloader_prompt = self.get_namespace_data(
            action="interrupt", label="interrupt", key="at_bootloader_prompt"
        )
        if not at_bootloader_prompt:
            self.wait(connection, max_end_time)
        commands = self.get_namespace_data(
            action="bootloader-overlay", label=self.method, key="commands"
        )
        error_messages = self.job.device.get_constant(
            "error-messages", prefix=self.method, missing_ok=True
        )
        final_message = self.job.device.get_constant(
            "final-message", prefix=self.method, missing_ok=True
        )
        if error_messages:
            if isinstance(connection.prompt_str, str):
                connection.prompt_str = [connection.prompt_str]
            connection.prompt_str = connection.prompt_str + error_messages

        for index, line in enumerate(commands):
            connection.sendline(line, delay=self.character_delay)
            if index + 1 == len(commands):
                if not final_message or not self.expect_final:
                    break
                connection.prompt_str = (
                    [final_message] + error_messages
                    if error_messages
                    else [final_message]
                )
            res = self.wait(connection, max_end_time)
            if res != 0:
                msg = "matched a bootloader error message: '%s' (%d)" % (
                    connection.prompt_str[res],
                    res,
                )
                raise InfrastructureError(msg)

        self.set_namespace_data(
            action="shared", label="shared", key="connection", value=connection
        )
        return connection
