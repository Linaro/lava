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

import os
import re
import shutil
from lava_dispatcher.pipeline.action import (
    Action,
    InfrastructureError,
    JobError,
    Timeout,
    LAVABug)
from lava_dispatcher.pipeline.logical import RetryAction
from lava_dispatcher.pipeline.utils.constants import (
    DEFAULT_SHELL_PROMPT,
    DISPATCHER_DOWNLOAD_DIR,
    DISTINCTIVE_PROMPT_CHARACTERS,
    LINE_SEPARATOR,
    BOOTLOADER_DEFAULT_CMD_TIMEOUT,
    BOOT_MESSAGE,
    CPU_RESET_MESSAGE,
    LOGIN_INCORRECT_MSG,
    LOGIN_TIMED_OUT_MSG
)
from lava_dispatcher.pipeline.utils.messages import LinuxKernelMessages
from lava_dispatcher.pipeline.utils.strings import substitute
from lava_dispatcher.pipeline.utils.network import dispatcher_ip
from lava_dispatcher.pipeline.utils.filesystem import write_bootscript
from lava_dispatcher.pipeline.utils.udev import usb_device_wait
from lava_dispatcher.pipeline.connections.ssh import SShSession

# pylint: disable=too-many-locals,too-many-instance-attributes,superfluous-parens
# pylint: disable=too-many-branches,too-many-statements


class BootAction(RetryAction):
    """
    Base class for all actions which control power-on
    and boot behaviour of a device under test.
    The subclass selected to do the work will be the
    subclass returning True in the accepts(device_type, image)
    function.
    Each new subclass needs a unit test to ensure it is
    reliably selected for the correct job and not
    selected for an invalid job or a job
    accepted by a different subclass.

    Boot and Test are closely related - a fail error in Boot
    will cause subsequent Test actions to be skipped.
    """

    name = 'boot'

    def has_prompts(self, parameters):  # pylint: disable=no-self-use
        return ('prompts' in parameters)

    def has_boot_finished(self, parameters):  # pylint: disable=no-self-use
        return ('boot_finished' in parameters)


class AutoLoginAction(Action):
    """
    Automatically login on the device.
    If 'auto_login' is not present in the parameters, this action does nothing.

    This Action expect POSIX-compatible support of PS1 from shell
    """
    def __init__(self):
        super(AutoLoginAction, self).__init__()
        self.name = 'auto-login-action'
        self.description = "automatically login after boot using job parameters and checking for messages."
        self.summary = "Auto-login after boot with support for kernel messages."
        self.check_prompt_characters_warning = (
            "The string '%s' does not look like a typical prompt and"
            " could match status messages instead. Please check the"
            " job log files and use a prompt string which matches the"
            " actual prompt string more closely."
        )
        self.force_prompt = False

    def validate(self):  # pylint: disable=too-many-branches
        super(AutoLoginAction, self).validate()
        # Skip auto login if the configuration is not found
        params = self.parameters.get('auto_login', None)
        if params:
            if not isinstance(params, dict):
                self.errors = "'auto_login' should be a dictionary"
                return

            if 'login_prompt' not in params:
                self.errors = "'login_prompt' is mandatory for auto_login"
            if not params['login_prompt']:
                self.errors = "Value for 'login_prompt' cannot be empty"
            if 'username' not in params:
                self.errors = "'username' is mandatory for auto_login"

            if 'password_prompt' in params:
                if 'password' not in params:
                    self.errors = "'password' is mandatory if 'password_prompt' is used in auto_login"

        prompts = self.parameters.get('prompts', None)
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

    def check_kernel_messages(self, connection, max_end_time):
        """
        Use the additional pexpect expressions to detect warnings
        and errors during the kernel boot. Ensure all test jobs using
        auto-login-action have a result set so that the duration is
        always available when the action completes successfully.
        """
        if isinstance(connection, SShSession):
            self.logger.debug("Skipping kernel messages")
            return
        self.logger.info("Parsing kernel messages")
        self.logger.debug(connection.prompt_str)
        parsed = LinuxKernelMessages.parse_failures(connection, self, max_end_time=max_end_time)
        if len(parsed) and 'success' in parsed[0]:
            self.results = {'success': parsed[0]}
        elif not parsed:
            self.results = {'success': "No kernel warnings or errors detected."}
        else:
            self.results = {'fail': parsed}
            self.logger.warning("Kernel warnings or errors detected.")

    def run(self, connection, max_end_time, args=None):
        # Prompts commonly include # - when logging such strings,
        # use lazy logging or the string will not be quoted correctly.
        def check_prompt_characters(chk_prompt):
            if not any([True for c in DISTINCTIVE_PROMPT_CHARACTERS if c in chk_prompt]):
                self.logger.warning(self.check_prompt_characters_warning, chk_prompt)

        if not connection:
            return connection
        prompts = self.parameters.get('prompts', None)
        for prompt in prompts:
            check_prompt_characters(prompt)

        connection.prompt_str = LinuxKernelMessages.get_init_prompts()
        connection.prompt_str.extend(prompts)

        # linesep should come from deployment_data as from now on it is OS dependent
        linesep = self.get_namespace_data(
            action='deploy-device-env',
            label='environment',
            key='line_separator'
        )
        connection.raw_connection.linesep = linesep if linesep else LINE_SEPARATOR
        self.logger.debug("Using line separator: #%r#", connection.raw_connection.linesep)

        # Skip auto login if the configuration is not found
        params = self.parameters.get('auto_login', None)
        if not params:
            self.logger.debug("No login prompt set.")
            self.force_prompt = True
            # If auto_login is not enabled, login will time out if login
            # details are requested.
            connection.prompt_str.append(LOGIN_TIMED_OUT_MSG)
            connection.prompt_str.append(LOGIN_INCORRECT_MSG)
            # wait for a prompt or kernel messages
            self.check_kernel_messages(connection, max_end_time)
            if 'success' in self.results:
                check = self.results['success'].values()
                if LOGIN_TIMED_OUT_MSG in check or LOGIN_INCORRECT_MSG in check:
                    raise JobError("auto_login not enabled but image requested login details.")
            # clear kernel message prompt patterns
            connection.prompt_str = list(self.parameters.get('prompts', []))
            # already matched one of the prompts
        else:
            self.logger.info("Waiting for the login prompt")
            connection.prompt_str.append(params['login_prompt'])
            connection.prompt_str.append(LOGIN_INCORRECT_MSG)

            # wait for a prompt or kernel messages
            self.check_kernel_messages(connection, max_end_time)
            if 'success' in self.results:
                if LOGIN_INCORRECT_MSG in self.results['success'].values():
                    self.logger.warning("Login incorrect message matched before the login prompt. "
                                        "Please check that the login prompt is correct. Retrying login...")
            self.logger.debug("Sending username %s", params['username'])
            connection.sendline(params['username'], delay=self.character_delay)
            # clear the kernel_messages patterns
            connection.prompt_str = list(self.parameters.get('prompts', []))

            if 'password_prompt' in params:
                self.logger.info("Waiting for password prompt")
                connection.prompt_str.append(params['password_prompt'])
                # This can happen if password_prompt is misspelled.
                connection.prompt_str.append(LOGIN_TIMED_OUT_MSG)

                # wait for the password prompt
                index = self.wait(connection, max_end_time)
                if index:
                    self.logger.debug("Matched prompt #%s: %s", index, connection.prompt_str[index])
                    if connection.prompt_str[index] == LOGIN_TIMED_OUT_MSG:
                        raise JobError("Password prompt not matched, please update the job definition with the correct one.")
                self.logger.debug("Sending password %s", params['password'])
                connection.sendline(params['password'], delay=self.character_delay)
                # clear the Password pattern
                connection.prompt_str = list(self.parameters.get('prompts', []))

            connection.prompt_str.append(LOGIN_INCORRECT_MSG)
            connection.prompt_str.append(LOGIN_TIMED_OUT_MSG)
            # wait for the login process to provide the prompt
            index = self.wait(connection, max_end_time)
            if index:
                self.logger.debug("Matched %s %s", index, connection.prompt_str[index])
                if connection.prompt_str[index] == LOGIN_INCORRECT_MSG:
                    self.errors = LOGIN_INCORRECT_MSG
                    raise JobError(LOGIN_INCORRECT_MSG)
                if connection.prompt_str[index] == LOGIN_TIMED_OUT_MSG:
                    self.errors = LOGIN_TIMED_OUT_MSG
                    raise JobError(LOGIN_TIMED_OUT_MSG)

        connection.prompt_str.extend([DEFAULT_SHELL_PROMPT])
        self.logger.debug("Setting shell prompt(s) to %s" % connection.prompt_str)  # pylint: disable=logging-not-lazy
        connection.sendline('export PS1="%s"' % DEFAULT_SHELL_PROMPT, delay=self.character_delay)

        return connection


class WaitUSBDeviceAction(Action):

    def __init__(self, device_actions):
        super(WaitUSBDeviceAction, self).__init__()
        self.name = "wait-usb-device"
        self.description = "wait for udev to see USB device"
        self.summary = self.description
        self.device_actions = device_actions

    def validate(self):
        super(WaitUSBDeviceAction, self).validate()
        if not isinstance(self.device_actions, list):
            self.errors = "device_actions is not a list"
        if 'device_info' in self.job.device \
           and not isinstance(self.job.device['device_info'], list):
            self.errors = "device_info unset"
        try:
            if 'device_info' in self.job.device:
                for usb_device in self.job.device['device_info']:
                    board_id = usb_device.get('board_id', '')
                    usb_vendor_id = usb_device.get('usb_vendor_id', '')
                    usb_product_id = usb_device.get('usb_product_id', '')
                    if board_id == '0000000000':
                        self.errors = "board_id unset"
                    if usb_vendor_id == '0000':
                        self.errors = 'usb_vendor_id unset'
                    if usb_product_id == '0000':
                        self.errors = 'usb_product_id unset'
        except KeyError as exc:
            raise InfrastructureError(exc)
        except (TypeError):
            self.errors = "Invalid parameters for %s" % self.name

    def run(self, connection, max_end_time, args=None):
        self.logger.info("Waiting for USB device(s) ...")
        usb_device_wait(self.job, device_actions=self.device_actions)
        return connection


class BootloaderCommandOverlay(Action):
    """
    Replace KERNEL_ADDR and DTB placeholders with the actual values for this
    particular pipeline.
    addresses are read from the device configuration parameters
    bootloader_type is determined from the boot action method strategy
    bootz or bootm is determined by boot action method type. (i.e. it is up to
    the test writer to select the correct download file for the correct boot command.)
    server_ip is calculated at runtime
    filenames are determined from the download Action.
    """
    def __init__(self):
        super(BootloaderCommandOverlay, self).__init__()
        self.name = "bootloader-overlay"
        self.summary = "replace placeholders with job data"
        self.description = "substitute job data into bootloader command list"
        self.commands = None
        self.method = ""
        self.use_bootscript = False
        self.lava_mac = None
        self.bootcommand = ''

    def validate(self):
        super(BootloaderCommandOverlay, self).validate()
        self.method = self.parameters['method']
        device_methods = self.job.device['actions']['boot']['methods']
        if isinstance(self.parameters['commands'], list):
            self.commands = self.parameters['commands']
            self.logger.warning("WARNING: Using boot commands supplied in the job definition, NOT the LAVA device configuration")
        else:
            if self.method not in self.job.device['actions']['boot']['methods']:
                self.errors = "%s boot method not found" % self.method
            if 'method' not in self.parameters:
                self.errors = "missing method"
            elif 'commands' not in self.parameters:
                self.errors = "missing commands"
            elif self.parameters['commands'] not in device_methods[self.parameters['method']]:
                self.errors = "Command not found in supported methods"
            elif 'commands' not in device_methods[self.parameters['method']][self.parameters['commands']]:
                self.errors = "No commands found in parameters"
            self.commands = device_methods[self.parameters['method']][self.parameters['commands']]['commands']
        # download_action will set ['dtb'] as tftp_path, tmpdir & filename later, in the run step.
        if 'use_bootscript' in self.parameters:
            self.use_bootscript = self.parameters['use_bootscript']
        if 'lava_mac' in self.parameters:
            if re.match("([0-9A-F]{2}[:-]){5}([0-9A-F]{2})", self.parameters['lava_mac'], re.IGNORECASE):
                self.lava_mac = self.parameters['lava_mac']
            else:
                self.errors = "lava_mac is not a valid mac address"

    def run(self, connection, max_end_time, args=None):
        """
        Read data from the download action and replace in context
        Use common data for all values passed into the substitutions so that
        multiple actions can use the same code.
        """
        # Multiple deployments would overwrite the value if parsed in the validate step.
        # FIXME: implement isolation for repeated steps.
        connection = super(BootloaderCommandOverlay, self).run(connection, max_end_time, args)
        ip_addr = dispatcher_ip(self.job.parameters['dispatcher'])

        substitutions = {
            '{SERVER_IP}': ip_addr,
            '{PRESEED_CONFIG}': self.get_namespace_data(action='download_action', label='file', key='preseed'),
            '{PRESEED_LOCAL}': self.get_namespace_data(action='compress-ramdisk', label='file', key='preseed_local'),
            '{DTB}': self.get_namespace_data(action='download_action', label='file', key='dtb'),
            '{RAMDISK}': self.get_namespace_data(action='compress-ramdisk', label='file', key='ramdisk'),
            '{KERNEL}': self.get_namespace_data(action='download_action', label='file', key='kernel'),
            '{LAVA_MAC}': self.lava_mac
        }
        self.bootcommand = self.get_namespace_data(action='uboot-prepare-kernel', label='bootcommand', key='bootcommand')
        if not self.bootcommand:
            if 'type' in self.parameters:
                self.logger.warning("Using type from the boot action as the boot-command. "
                                    "Declaring a kernel type in the deploy is preferred.")
                self.bootcommand = self.parameters['type']
        prepared_kernel = self.get_namespace_data(action='prepare-kernel', label='file', key='kernel')
        if prepared_kernel:
            self.logger.info("Using kernel file from prepare-kernel: %s", prepared_kernel)
            substitutions['{KERNEL}'] = prepared_kernel
        if self.bootcommand:
            kernel_addr = self.job.device['parameters'][self.bootcommand]['kernel']
            dtb_addr = self.job.device['parameters'][self.bootcommand]['dtb']
            ramdisk_addr = self.job.device['parameters'][self.bootcommand]['ramdisk']

            if not self.get_namespace_data(action='tftp-deploy', label='tftp', key='ramdisk') \
                    and not self.get_namespace_data(action='download_action', label='file', key='ramdisk'):
                ramdisk_addr = '-'

            substitutions['{BOOTX}'] = "%s %s %s %s" % (
                self.bootcommand, kernel_addr, ramdisk_addr, dtb_addr)
            substitutions['{KERNEL_ADDR}'] = kernel_addr
            substitutions['{DTB_ADDR}'] = dtb_addr
            substitutions['{RAMDISK_ADDR}'] = ramdisk_addr
            self.results = {
                'kernel_addr': kernel_addr,
                'dtb_addr': dtb_addr,
                'ramdisk_addr': ramdisk_addr
            }

        nfs_address = self.get_namespace_data(action='persistent-nfs-overlay', label='nfs_address', key='nfsroot')
        nfs_root = self.get_namespace_data(action='download_action', label='file', key='nfsrootfs')
        if nfs_root:
            substitutions['{NFSROOTFS}'] = self.get_namespace_data(action='extract-rootfs', label='file', key='nfsroot')
            substitutions['{NFS_SERVER_IP}'] = ip_addr
        elif nfs_address:
            substitutions['{NFSROOTFS}'] = nfs_address
            substitutions['{NFS_SERVER_IP}'] = self.get_namespace_data(
                action='persistent-nfs-overlay', label='nfs_address', key='serverip')

        substitutions['{ROOT}'] = self.get_namespace_data(action='uboot-from-media', label='uuid', key='root')  # UUID label, not a file
        substitutions['{ROOT_PART}'] = self.get_namespace_data(action='uboot-from-media', label='uuid', key='boot_part')
        if self.use_bootscript:
            script = "/script.ipxe"
            bootscript = self.get_namespace_data(action='tftp-deploy', label='tftp', key='tftp_dir') + script
            bootscripturi = "tftp://%s/%s" % (ip_addr, os.path.dirname(substitutions['{KERNEL}']) + script)
            write_bootscript(substitute(self.commands, substitutions), bootscript)
            bootscript_commands = ['dhcp net0', "chain %s" % bootscripturi]
            self.set_namespace_data(action=self.name, label=self.method, key='commands', value=bootscript_commands)
            self.logger.info("Parsed boot commands: %s", '; '.join(bootscript_commands))
            return connection
        subs = substitute(self.commands, substitutions)
        self.set_namespace_data(action='bootloader-overlay', label=self.method, key='commands', value=subs)
        self.logger.info("Parsed boot commands: %s", '; '.join(subs))
        return connection


class OverlayUnpack(Action):
    """
    Transfer the overlay.tar.gz to the device using test writer tools
    Can be used with inline bootloader commands or where the rootfs is
    not deployed directly by LAVA.
    Whether the device has booted by tftp or ipxe or something else does
    not matter for this action - the file will be downloaded from the
    worker tmp dir using the default apache config.
    """
    def __init__(self):
        super(OverlayUnpack, self).__init__()
        self.name = 'overlay-unpack'
        self.description = 'transfer and unpack overlay to persistent rootfs after login'
        self.summary = 'transfer and unpack overlay'
        self.url = None

    def cleanup(self, connection):
        super(OverlayUnpack, self).cleanup(connection)
        if self.url:
            os.unlink(self.url)

    def validate(self):
        super(OverlayUnpack, self).validate()
        if 'transfer_overlay' not in self.parameters:
            self.errors = "Unable to identify transfer commands for overlay."
            return
        if 'download_command' not in self.parameters['transfer_overlay']:
            self.errors = "Unable to identify download command for overlay."
        if 'unpack_command' not in self.parameters['transfer_overlay']:
            self.errors = "Unable to identify unpack command for overlay."

    def run(self, connection, max_end_time, args=None):
        connection = super(OverlayUnpack, self).run(connection, max_end_time, args)
        if not connection:
            raise LAVABug("Cannot transfer overlay, no connection available.")
        ip_addr = dispatcher_ip(self.job.parameters['dispatcher'])
        overlay_file = self.get_namespace_data(action='compress-overlay', label='output', key='file')
        if not overlay_file:
            raise JobError("No overlay file identified for the transfer.")
        overlay = os.path.basename(overlay_file).strip()
        self.url = os.path.join(DISPATCHER_DOWNLOAD_DIR, overlay)
        shutil.move(overlay_file, self.url)
        self.logger.debug("Moved %s to %s", overlay_file, self.url)
        dwnld = self.parameters['transfer_overlay']['download_command']
        dwnld += " http://%s/tmp/%s" % (ip_addr, overlay)
        unpack = self.parameters['transfer_overlay']['unpack_command']
        unpack += ' ' + overlay
        connection.sendline("rm %s; %s && %s" % (overlay, dwnld, unpack))
        return connection


class BootloaderCommandsAction(Action):
    """
    Send the boot commands to the bootloader
    """
    def __init__(self):
        super(BootloaderCommandsAction, self).__init__()
        self.name = "bootloader-commands"
        self.description = "send commands to bootloader"
        self.summary = "interactive bootloader"
        self.params = None
        self.timeout = Timeout(self.name, BOOTLOADER_DEFAULT_CMD_TIMEOUT)
        self.method = ""

    def validate(self):
        super(BootloaderCommandsAction, self).validate()
        self.method = self.parameters['method']
        self.params = self.job.device['actions']['boot']['methods'][self.method]['parameters']

    def run(self, connection, max_end_time, args=None):
        if not connection:
            self.errors = "%s started without a connection already in use" % self.name
        connection = super(BootloaderCommandsAction, self).run(connection, max_end_time, args)
        connection.prompt_str = self.params['bootloader_prompt']
        self.logger.debug("Changing prompt to start interaction: %s", connection.prompt_str)
        self.wait(connection)
        i = 1
        commands = self.get_namespace_data(action='bootloader-overlay', label=self.method, key='commands')

        for line in commands:
            connection.sendline(line, delay=self.character_delay)
            if i != (len(commands)):
                self.wait(connection)
                i += 1

        res = 'failed' if self.errors else 'success'
        self.set_namespace_data(action='boot', label='shared', key='boot-result', value=res)
        self.set_namespace_data(action='shared', label='shared', key='connection', value=connection)
        # allow for auto_login
        if self.parameters.get('prompts', None):
            connection.prompt_str = [
                self.params.get('boot_message', BOOT_MESSAGE),
                CPU_RESET_MESSAGE
            ]
            self.logger.debug("Changing prompt to boot_message %s",
                              connection.prompt_str)
            index = self.wait(connection)
            if connection.prompt_str[index] == CPU_RESET_MESSAGE:
                self.logger.error("Bootloader reset detected: Bootloader "
                                  "failed to load the required file into "
                                  "memory correctly so the bootloader reset "
                                  "the CPU.")
                self.errors = "Bootloader reset detected"
                raise InfrastructureError("Bootloader reset detected")
        return connection
