# Copyright (C) 2014-2019 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import contextlib
import os
import re

from lava_common.constants import (
    BOOTLOADER_DEFAULT_CMD_TIMEOUT,
    DISPATCHER_DOWNLOAD_DIR,
    DISTINCTIVE_PROMPT_CHARACTERS,
    LINE_SEPARATOR,
    LOGIN_INCORRECT_MSG,
    LOGIN_TIMED_OUT_MSG,
)
from lava_common.exceptions import (
    ConfigurationError,
    InfrastructureError,
    JobError,
    LAVABug,
)
from lava_common.timeout import Timeout
from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.actions.boot.environment import ExportDeviceEnvironment
from lava_dispatcher.connections.ssh import SShSession
from lava_dispatcher.logical import Boot, RetryAction
from lava_dispatcher.shell import ExpectShellSession
from lava_dispatcher.utils.compression import untar_file
from lava_dispatcher.utils.filesystem import write_bootscript
from lava_dispatcher.utils.messages import LinuxKernelMessages
from lava_dispatcher.utils.network import dispatcher_ip
from lava_dispatcher.utils.strings import substitute


class BootHasMixin:
    """Add the two methods to boot classes using it"""

    def has_prompts(self, parameters):
        return "prompts" in parameters

    def has_boot_finished(self, parameters):
        return "boot_finished" in parameters


class LoginAction(Action):
    name = "login-action"
    description = "Real login action."
    summary = "Login after boot."

    check_prompt_characters_warning = (
        "The string '%s' does not look like a typical prompt and"
        " could match status messages instead. Please check the"
        " job log files and use a prompt string which matches the"
        " actual prompt string more closely."
    )

    def __init__(self):
        super().__init__()
        self.force_prompt = True  # Kernel logs may overlap with login prompt on boot

    def check_kernel_messages(
        self, connection, max_end_time, fail_msg, auto_login=False
    ):
        """
        Use the additional pexpect expressions to detect warnings
        and errors during the kernel boot. Ensure all test jobs using
        auto-login-action have a result set so that the duration is
        always available when the action completes successfully.
        """
        if isinstance(connection, SShSession):
            self.logger.debug("Skipping kernel messages")
            return
        if self.parameters.get("ignore_kernel_messages", False):
            self.logger.debug("Skipping kernel messages. Flag set to false")
            if self.force_prompt:
                connection.force_prompt_wait(max_end_time)
            else:
                connection.wait(max_end_time)
            return
        self.logger.info("Parsing kernel messages")
        self.logger.debug(connection.prompt_str)
        parsed = LinuxKernelMessages.parse_failures(
            connection,
            self,
            max_end_time=max_end_time,
            fail_msg=fail_msg,
            auto_login=auto_login,
        )
        if len(parsed) and "success" in parsed[0]:
            self.results = {"success": parsed[0]["success"]}
            if len(parsed) > 1:
                # errors detected.
                self.logger.warning("Kernel warnings or errors detected.")
                self.results = {"extra": parsed}
        elif not parsed:
            self.results = {"success": "No kernel warnings or errors detected."}
        else:
            self.results = {"fail": parsed}
            self.logger.warning("Kernel warnings or errors detected.")

    def _check_prompt_characters(self, chk_prompt: str | type) -> None:
        if not isinstance(chk_prompt, str):
            return

        if not any(c in chk_prompt for c in DISTINCTIVE_PROMPT_CHARACTERS):
            self.logger.warning(self.check_prompt_characters_warning, chk_prompt)

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)
        if not connection:
            return connection
        prompts = self.parameters.get("prompts")
        for prompt in prompts:
            self._check_prompt_characters(prompt)

        connection.prompt_str = []
        if not self.parameters.get("ignore_kernel_messages", False):
            connection.prompt_str = LinuxKernelMessages.get_init_prompts()
        connection.prompt_str.extend(prompts)

        # Needs to be added after the standard kernel message matches
        # FIXME: check behaviour if boot_message is defined too.
        failure = self.parameters.get("failure_message")
        if failure:
            self.logger.info("Checking for user specified failure message: %s", failure)
            connection.prompt_str.append(failure)

        # linesep should come from deployment_data as from now on it is OS dependent
        linesep = self.get_namespace_data(
            action="deploy-device-env", label="environment", key="line_separator"
        )
        connection.raw_connection.linesep = linesep if linesep else LINE_SEPARATOR
        self.logger.debug(
            "Using line separator: #%r#", connection.raw_connection.linesep
        )

        # Skip auto login if the configuration is not found
        params = self.parameters.get("auto_login")
        if not params:
            self.logger.debug("No login prompt set.")
            # If auto_login is not enabled, login will time out if login
            # details are requested.
            connection.prompt_str.append(LOGIN_TIMED_OUT_MSG)
            connection.prompt_str.append(LOGIN_INCORRECT_MSG)
            # wait for a prompt or kernel messages
            self.check_kernel_messages(connection, max_end_time, failure)
            if "success" in self.results:
                check = self.results["success"]
                if LOGIN_TIMED_OUT_MSG in check or LOGIN_INCORRECT_MSG in check:
                    raise JobError(
                        "auto_login not enabled but image requested login details."
                    )
            # clear kernel message prompt patterns
            connection.prompt_str = list(self.parameters.get("prompts", []))
            # already matched one of the prompts
        else:
            self.logger.info("Waiting for the login prompt")
            connection.prompt_str.append(params["login_prompt"])
            connection.prompt_str.append(LOGIN_INCORRECT_MSG)

            # wait for a prompt or kernel messages
            self.check_kernel_messages(
                connection, max_end_time, failure, auto_login=True
            )
            if "success" in self.results:
                if LOGIN_INCORRECT_MSG in self.results["success"]:
                    self.logger.warning(
                        "Login incorrect message matched before the login prompt. "
                        "Please check that the login prompt is correct. Retrying login..."
                    )
            self.logger.debug("Sending username %s", params["username"])
            connection.sendline(params["username"], delay=self.character_delay)
            # clear the kernel_messages patterns
            connection.prompt_str = list(self.parameters.get("prompts", []))

            if "password_prompt" in params:
                self.logger.info("Waiting for password prompt")
                connection.prompt_str.append(params["password_prompt"])
                # This can happen if password_prompt is misspelled.
                connection.prompt_str.append(LOGIN_TIMED_OUT_MSG)

                # wait for the password prompt
                index = self.wait(connection, max_end_time)
                if index:
                    self.logger.debug(
                        "Matched prompt #%s: %s", index, connection.prompt_str[index]
                    )
                    if connection.prompt_str[index] == LOGIN_TIMED_OUT_MSG:
                        raise JobError(
                            "Password prompt not matched, please update the job definition with the correct one."
                        )
                self.logger.debug("Sending password %s", params["password"])
                connection.sendline(params["password"], delay=self.character_delay)
                # clear the Password pattern
                connection.prompt_str = list(self.parameters.get("prompts", []))

            connection.prompt_str.append(LOGIN_INCORRECT_MSG)
            connection.prompt_str.append(LOGIN_TIMED_OUT_MSG)
            # wait for the login process to provide the prompt
            index = self.wait(connection, max_end_time)
            if index:
                self.logger.debug("Matched %s %s", index, connection.prompt_str[index])
                if connection.prompt_str[index] == LOGIN_INCORRECT_MSG:
                    raise JobError(LOGIN_INCORRECT_MSG)
                if connection.prompt_str[index] == LOGIN_TIMED_OUT_MSG:
                    raise JobError(LOGIN_TIMED_OUT_MSG)

            # clear the login patterns
            connection.prompt_str = list(self.parameters.get("prompts", []))

            login_commands = params.get("login_commands")
            if login_commands is not None:
                self.logger.debug("Running login commands")
                for command in login_commands:
                    connection.sendline(command, delay=self.character_delay)
                    connection.wait()

        return connection


# FIXME: move to it's own file
class AutoLoginAction(RetryAction):
    """
    Automatically login on the device.
    If 'auto_login' is not present in the parameters, this action does nothing.

    This Action expect POSIX-compatible support of PS1 from shell
    """

    name = "auto-login-action"
    description = (
        "automatically login after boot using job parameters and checking for messages."
    )
    summary = "Auto-login after boot with support for kernel messages."

    def __init__(self, booting=True):
        super().__init__()
        self.params = None
        self.booting = booting  # if a boot is expected, False for second UART or ssh.

    def validate(self):
        super().validate()
        # Skip auto login if the configuration is not found
        self.method = self.parameters["method"]
        params = self.parameters.get("auto_login")
        if params:
            if not isinstance(params, dict):
                self.errors = "'auto_login' should be a dictionary"
                return

            if "login_prompt" not in params:
                self.errors = "'login_prompt' is mandatory for auto_login"
            elif not params["login_prompt"]:
                self.errors = "Value for 'login_prompt' cannot be empty"

            if "username" not in params:
                self.errors = "'username' is mandatory for auto_login"

            if "password_prompt" in params:
                if "password" not in params:
                    self.errors = "'password' is mandatory if 'password_prompt' is used in auto_login"

            if "login_commands" in params:
                login_commands = params["login_commands"]
                if not isinstance(login_commands, list):
                    self.errors = "'login_commands' must be a list"
                if not login_commands:
                    self.errors = "'login_commands' must not be empty"

        prompts = self.parameters.get("prompts")
        if prompts is None:
            self.errors = "'prompts' is mandatory for AutoLoginAction"

        if not isinstance(prompts, (list, str)):
            self.errors = "'prompts' should be a list or a str"

        if not prompts:
            self.errors = "Value for 'prompts' cannot be empty"

        if isinstance(prompts, list):
            for prompt in prompts:
                if not prompt:
                    self.errors = "Items of 'prompts' can't be empty"

        methods = self.job.device["actions"]["boot"]["methods"]
        with contextlib.suppress(KeyError, TypeError):
            if "parameters" in methods[self.method]:
                # fastboot devices usually lack method parameters
                self.params = methods[self.method]["parameters"]

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.pipeline.add_action(LoginAction())

    def run(self, connection, max_end_time):
        # Prompts commonly include # - when logging such strings,
        # use lazy logging or the string will not be quoted correctly.
        if self.booting:
            kernel_start_message = self.parameters.get("parameters", {}).get(
                "kernel-start-message",
                self.job.device.get_constant("kernel-start-message"),
            )
            if kernel_start_message:
                connection.prompt_str = [kernel_start_message]

            if self.params and self.params.get("boot_message"):
                self.logger.warning(
                    "boot_message is being deprecated in favour of kernel-start-message in constants"
                )
                connection.prompt_str = [self.params.get("boot_message")]

            error_messages = self.job.device.get_constant(
                "error-messages", prefix=self.method, missing_ok=True
            )
            if error_messages:
                if isinstance(connection.prompt_str, str):
                    connection.prompt_str = [connection.prompt_str]
                connection.prompt_str = connection.prompt_str + error_messages
            if kernel_start_message:
                res = self.wait(connection)
                if res != 0:
                    msg = "matched a bootloader error message: '%s' (%d)" % (
                        connection.prompt_str[res],
                        res,
                    )
                    raise InfrastructureError(msg)

        connection = super().run(connection, max_end_time)
        return connection


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

    def __init__(self, method=None, commands=None):
        super().__init__()
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

    def __init__(self, method=None):
        super().__init__()
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


class BootloaderCommandsActionAltBank(Action):
    """
    Send the "uboot_altbank_cmd" command to the bootloader
    """

    name = "bootloader-commands-altbank"
    description = "send commands to bootloader altbank"
    summary = "interactive bootloader altbank"
    timeout_exception = InfrastructureError

    def __init__(self, expect_final=True, method=None):
        super().__init__()
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
        command = self.params.get("uboot_altbank_cmd")
        connection.sendline(command, delay=self.character_delay)
        if final_message and self.expect_final:
            connection.prompt_str = [final_message]
            self.wait(connection, max_end_time)

        self.set_namespace_data(
            action="shared", label="shared", key="connection", value=connection
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

    def __init__(self, expect_final=True, method=None):
        super().__init__()
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


class AdbOverlayUnpack(Action):
    name = "adb-overlay-unpack"
    summary = "unpack the overlay on the remote device"
    description = "unpack the overlay over adb"

    def validate(self):
        super().validate()
        if "adb_serial_number" not in self.job.device:
            self.errors = "device adb serial number missing"
            if self.job.device["adb_serial_number"] == "0000000000":
                self.errors = "device adb serial number unset"

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)
        if not connection:
            raise LAVABug("Cannot transfer overlay, no connection available.")
        overlay_file = self.get_namespace_data(
            action="compress-overlay", label="output", key="file"
        )
        if not overlay_file:
            raise JobError("No overlay file identified for the transfer.")
        serial_number = self.job.device["adb_serial_number"]
        host_dir = self.mkdtemp()
        target_dir = "/data/local"
        untar_file(overlay_file, host_dir)
        host_dir = os.path.join(host_dir, "data/local/tmp")
        adb_cmd = ["adb", "-s", serial_number, "push", host_dir, target_dir]
        command_output = self.run_command(adb_cmd)
        if command_output and "pushed" not in command_output.lower():
            raise JobError("Unable to push overlay files with adb: %s" % command_output)
        adb_cmd = [
            "adb",
            "-s",
            serial_number,
            "shell",
            "/system/bin/chmod",
            "-R",
            "0777",
            os.path.join(target_dir, "tmp"),
        ]
        command_output = self.run_command(adb_cmd)
        if command_output and "pushed" not in command_output.lower():
            raise JobError(
                "Unable to chmod overlay files with adb: %s" % command_output
            )
        return connection
