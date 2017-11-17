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
from lava_dispatcher.action import (
    Action,
    Pipeline,
    InfrastructureError,
    JobError,
    ConfigurationError,
    Timeout,
    LAVABug)
from lava_dispatcher.logical import Boot
from lava_dispatcher.logical import RetryAction
from lava_dispatcher.utils.constants import (
    DISPATCHER_DOWNLOAD_DIR,
    DISTINCTIVE_PROMPT_CHARACTERS,
    LINE_SEPARATOR,
    BOOTLOADER_DEFAULT_CMD_TIMEOUT,
    LOGIN_INCORRECT_MSG,
    LOGIN_TIMED_OUT_MSG
)
from lava_dispatcher.utils.messages import LinuxKernelMessages
from lava_dispatcher.utils.strings import substitute
from lava_dispatcher.utils.network import dispatcher_ip
from lava_dispatcher.utils.filesystem import write_bootscript
from lava_dispatcher.connections.ssh import SShSession
from lava_dispatcher.connections.serial import ConnectShell
from lava_dispatcher.actions.boot.environment import ExportDeviceEnvironment
from lava_dispatcher.shell import ExpectShellSession

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


class SecondaryShell(Boot):
    """
    SecondaryShell method can be used by a variety of other boot methods to
    read from the kernel console independently of the shell interaction
    required to interact with the bootloader and test shell.
    It is also the updated way to connect to the primary console.
    """

    compatibility = 6

    def __init__(self, parent, parameters):
        super(SecondaryShell, self).__init__(parent)
        self.action = SecondaryShellAction()
        self.action.section = self.action_type
        self.action.job = self.job
        parent.add_action(self.action, parameters)

    @classmethod
    def accepts(cls, device, parameters):
        if 'method' not in parameters:
            raise ConfigurationError("method not specified in boot parameters")
        if parameters['method'] != 'new_connection':
            return False, 'new_connection not in method'
        if 'actions' not in device:
            raise ConfigurationError("Invalid device configuration")
        if 'boot' not in device['actions']:
            return False, 'boot not in device actions'
        if 'methods' not in device['actions']['boot']:
            raise ConfigurationError("Device misconfiguration")
        if 'method' not in parameters:
            return False, 'no boot method'
        return True, 'accepted'


class SecondaryShellAction(BootAction):

    def __init__(self):
        super(SecondaryShellAction, self).__init__()
        self.name = "secondary-shell-action"
        self.description = "Connect to a secondary shell on specified hardware"
        self.summary = "connect to a specified second shell"

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        name = parameters['connection']
        self.internal_pipeline.add_action(ConnectShell(name=name))
        if self.has_prompts(parameters):
            self.internal_pipeline.add_action(AutoLoginAction())
            if self.test_has_shell(parameters):
                self.internal_pipeline.add_action(ExpectShellSession())
                if 'transfer_overlay' in parameters:
                    self.internal_pipeline.add_action(OverlayUnpack())
                self.internal_pipeline.add_action(ExportDeviceEnvironment())


# FIXME: move to it's own file
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
            elif not params['login_prompt']:
                self.errors = "Value for 'login_prompt' cannot be empty"

            if 'username' not in params:
                self.errors = "'username' is mandatory for auto_login"

            if 'password_prompt' in params:
                if 'password' not in params:
                    self.errors = "'password' is mandatory if 'password_prompt' is used in auto_login"

            if 'login_commands' in params:
                login_commands = params['login_commands']
                if not isinstance(login_commands, list):
                    self.errors = "'login_commands' must be a list"
                if not login_commands:
                    self.errors = "'login_commands' must not be empty"

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
            self.results = {'success': parsed[0]['success']}
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

        connection = super(AutoLoginAction, self).run(connection, max_end_time, args)
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
                check = self.results['success']
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
                if LOGIN_INCORRECT_MSG in self.results['success']:
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

            login_commands = params.get('login_commands', None)
            if login_commands is not None:
                self.logger.debug("Running login commands")
                for command in login_commands:
                    connection.sendline(command)

        connection.prompt_str.extend([self.job.device.get_constant(
            'default-shell-prompt')])
        self.logger.debug("Setting shell prompt(s) to %s" % connection.prompt_str)  # pylint: disable=logging-not-lazy
        connection.sendline('export PS1="%s"' % self.job.device.get_constant(
            'default-shell-prompt'), delay=self.character_delay)

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
        self.ram_disk = None

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
        # download-action will set ['dtb'] as tftp_path, tmpdir & filename later, in the run step.
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

        self.ram_disk = self.get_namespace_data(action='compress-ramdisk', label='file', key='ramdisk')
        # most jobs substitute RAMDISK, so also use this for the initrd
        if self.get_namespace_data(action='nbd-deploy', label='nbd', key='initrd'):
            self.ram_disk = self.get_namespace_data(action='download-action', label='file', key='initrd')

        substitutions = {
            '{SERVER_IP}': ip_addr,
            '{PRESEED_CONFIG}': self.get_namespace_data(action='download-action', label='file', key='preseed'),
            '{PRESEED_LOCAL}': self.get_namespace_data(action='compress-ramdisk', label='file', key='preseed_local'),
            '{DTB}': self.get_namespace_data(action='download-action', label='file', key='dtb'),
            '{RAMDISK}': self.ram_disk,
            '{INITRD}': self.ram_disk,
            '{KERNEL}': self.get_namespace_data(action='download-action', label='file', key='kernel'),
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
            self.logger.debug("%s", self.job.device['parameters'])
            kernel_addr = self.job.device['parameters'][self.bootcommand]['kernel']
            dtb_addr = self.job.device['parameters'][self.bootcommand]['dtb']
            ramdisk_addr = self.job.device['parameters'][self.bootcommand]['ramdisk']

            if not self.get_namespace_data(action='tftp-deploy', label='tftp', key='ramdisk') \
                    and not self.get_namespace_data(action='download-action', label='file', key='ramdisk') \
                    and not self.get_namespace_data(action='download-action', label='file', key='initrd'):
                ramdisk_addr = '-'
            add_header = self.job.device['actions']['deploy']['parameters'].get('add_header', None)
            if self.method == 'u-boot' and not add_header == "u-boot":
                self.logger.debug("No u-boot header, not passing ramdisk to bootX cmd")
                ramdisk_addr = '-'

            if self.get_namespace_data(action='download-action', label='file', key='initrd'):
                # no u-boot header, thus no embedded size, so we have to add it to the
                # boot cmd with colon after the ramdisk
                substitutions['{BOOTX}'] = "%s %s %s:%s %s" % (
                    self.bootcommand, kernel_addr, ramdisk_addr, '${initrd_size}', dtb_addr)
            else:
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
        nfs_root = self.get_namespace_data(action='download-action', label='file', key='nfsrootfs')
        if nfs_root:
            substitutions['{NFSROOTFS}'] = self.get_namespace_data(action='extract-rootfs', label='file', key='nfsroot')
            substitutions['{NFS_SERVER_IP}'] = ip_addr
        elif nfs_address:
            substitutions['{NFSROOTFS}'] = nfs_address
            substitutions['{NFS_SERVER_IP}'] = self.get_namespace_data(
                action='persistent-nfs-overlay', label='nfs_address', key='serverip')

        nbd_root = self.get_namespace_data(action='download-action', label='file', key='nbdroot')
        if nbd_root:
            substitutions['{NBDSERVERIP}'] = str(self.get_namespace_data(action='nbd-deploy', label='nbd', key='nbd_server_ip'))
            substitutions['{NBDSERVERPORT}'] = str(self.get_namespace_data(action='nbd-deploy', label='nbd', key='nbd_server_port'))

        substitutions['{ROOT}'] = self.get_namespace_data(action='bootloader-from-media', label='uuid', key='root')  # UUID label, not a file
        substitutions['{ROOT_PART}'] = self.get_namespace_data(action='bootloader-from-media', label='uuid', key='boot_part')
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


class BootloaderSecondaryMedia(Action):
    """
    Generic class for secondary media substitutions
    """
    def __init__(self):
        super(BootloaderSecondaryMedia, self).__init__()
        self.name = "bootloader-from-media"
        self.summary = "set bootloader strings for deployed media"
        self.description = "let bootloader know where to find the kernel in the image on secondary media"

    def validate(self):
        super(BootloaderSecondaryMedia, self).validate()
        if 'media' not in self.job.device.get('parameters', []):
            return
        media_keys = self.job.device['parameters']['media'].keys()
        if self.parameters['commands'] not in media_keys:
            return
        if 'kernel' not in self.parameters:
            self.errors = "Missing kernel location"
        # ramdisk does not have to be specified, nor dtb
        if 'root_uuid' not in self.parameters:
            # FIXME: root_node also needs to be supported
            self.errors = "Missing UUID of the roofs inside the deployed image"
        if 'boot_part' not in self.parameters:
            self.errors = "Missing boot_part for the partition number of the boot files inside the deployed image"
        self.set_namespace_data(action='download-action', label='file', key='kernel', value=self.parameters.get('kernel', ''))
        self.set_namespace_data(action='compress-ramdisk', label='file', key='ramdisk', value=self.parameters.get('ramdisk', ''))
        self.set_namespace_data(action='download-action', label='file', key='ramdisk', value=self.parameters.get('ramdisk', ''))
        self.set_namespace_data(action='download-action', label='file', key='dtb', value=self.parameters.get('dtb', ''))
        self.set_namespace_data(action='bootloader-from-media', label='uuid', key='root', value=self.parameters.get('root_uuid', ''))
        self.set_namespace_data(action='bootloader-from-media', label='uuid', key='boot_part', value=str(self.parameters.get('boot_part')))


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

    def line_separator(self):
        return LINE_SEPARATOR

    def run(self, connection, max_end_time, args=None):
        if not connection:
            self.errors = "%s started without a connection already in use" % self.name
        connection = super(BootloaderCommandsAction, self).run(connection, max_end_time, args)
        connection.raw_connection.linesep = self.line_separator()
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

        self.set_namespace_data(action='shared', label='shared', key='connection', value=connection)
        # allow for auto_login
        if self.parameters.get('prompts', None):
            connection.prompt_str = [
                self.params.get('boot_message',
                                self.job.device.get_constant('boot-message')),
                self.job.device.get_constant('cpu-reset-message')
            ]
            self.logger.debug("Changing prompt to boot_message %s",
                              connection.prompt_str)
            index = self.wait(connection)
            if connection.prompt_str[index] == self.job.device.get_constant('cpu-reset-message'):
                self.logger.error("Bootloader reset detected: Bootloader "
                                  "failed to load the required file into "
                                  "memory correctly so the bootloader reset "
                                  "the CPU.")
                raise InfrastructureError("Bootloader reset detected")
        return connection
