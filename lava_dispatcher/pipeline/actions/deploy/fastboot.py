# Copyright (C) 2015 Linaro Limited
#
# Author: Senthil Kumaran S <senthil.kumaran@linaro.org>
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

from lava_dispatcher.pipeline.logical import Deployment
from lava_dispatcher.pipeline.action import (
    Pipeline,
    JobError,
)
from lava_dispatcher.pipeline.actions.deploy import DeployAction
from lava_dispatcher.pipeline.actions.deploy.overlay import OverlayAction
from lava_dispatcher.pipeline.actions.deploy.download import (
    DownloaderAction,
)
from lava_dispatcher.pipeline.utils.shell import infrastructure_error
from lava_dispatcher.pipeline.utils.filesystem import mkdtemp
from lava_dispatcher.pipeline.utils.constants import (
    DISPATCHER_DOWNLOAD_DIR,
    FASTBOOT_REBOOT_TIMEOUT,
)


def fastboot_accept(device, parameters):
    """
    Each fastboot deployment strategy uses these checks
    as a base, then makes the final decision on the
    style of fastboot deployment.
    """
    if 'to' not in parameters:
        return False
    if parameters['to'] != 'fastboot':
        return False
    if not device:
        return False
    if 'actions' not in device:
        raise RuntimeError("Invalid device configuration")
    if 'deploy' not in device['actions']:
        return False
    if 'serial_number' not in device:
        return False
    if 'methods' not in device['actions']['deploy']:
        raise RuntimeError("Device misconfiguration")
    return True


class Fastboot(Deployment):
    """
    Strategy class for a fastboot deployment.
    Downloads the relevant parts, copies to the locations using fastboot.
    """
    def __init__(self, parent, parameters):
        super(Fastboot, self).__init__(parent)
        self.action = FastbootAction()
        self.action.section = self.action_type
        self.action.job = self.job
        parent.add_action(self.action, parameters)

    @classmethod
    def accepts(cls, device, parameters):
        if not fastboot_accept(device, parameters):
            return False
        if 'fastboot' in device['actions']['deploy']['methods']:
            return True
        return False


class FastbootAction(DeployAction):  # pylint:disable=too-many-instance-attributes

    def __init__(self):
        super(FastbootAction, self).__init__()
        self.name = "fastboot-deploy"
        self.description = "download files and deploy using fastboot"
        self.summary = "fastboot deployment"
        self.fastboot_dir = DISPATCHER_DOWNLOAD_DIR
        try:
            self.fastboot_dir = mkdtemp(basedir=DISPATCHER_DOWNLOAD_DIR)
        except OSError:
            pass

    def validate(self):
        super(FastbootAction, self).validate()
        self.errors = infrastructure_error('adb')
        self.errors = infrastructure_error('fastboot')
        lava_test_results_dir = self.parameters['deployment_data']['lava_test_results_dir']
        self.data['lava_test_results_dir'] = lava_test_results_dir % self.job.job_id

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.internal_pipeline.add_action(OverlayAction())
        self.internal_pipeline.add_action(EnterFastbootAction())
        for image in parameters['images'].keys():
            if image != 'yaml_line':
                download = DownloaderAction(image, self.fastboot_dir)
                download.max_retries = 3  # overridden by failure_retry in the parameters, if set.
                self.internal_pipeline.add_action(download)
            if image == 'image':
                self.internal_pipeline.add_action(FastbootUpdateAction())
            if image == 'boot':
                self.internal_pipeline.add_action(ApplyBootAction())
            if image == 'userdata':
                self.internal_pipeline.add_action(ApplyUserdataAction())
            if image == 'system':
                self.internal_pipeline.add_action(ApplySystemAction())


class EnterFastbootAction(DeployAction):
    """
    Enters fastboot bootloader.
    """

    def __init__(self):
        super(EnterFastbootAction, self).__init__()
        self.name = "enter_fastboot_action"
        self.description = "enter fastboot bootloader"
        self.summary = "enter fastboot"
        self.retries = 10
        self.sleep = 10

    def validate(self):
        super(EnterFastbootAction, self).validate()
        if 'serial_number' not in self.job.device:
            self.errors = "device serial number missing"
            if self.job.device['serial_number'] == '0000000000':
                self.errors = "device serial number unset"

    def run(self, connection, args=None):
        connection = super(EnterFastbootAction, self).run(connection, args)
        serial_number = self.job.device['serial_number']
        adb_cmd = ['adb', '-s', serial_number, 'get-serialno']
        command_output = self.run_command(adb_cmd)
        if command_output and serial_number in command_output:
            adb_cmd = ['adb', '-s', serial_number, 'reboot', 'bootloader']
            command_output = self.run_command(adb_cmd)
            if command_output and command_output is not '':
                raise JobError("Unable to enter fastboot using adb: %s" %
                               command_output)  # FIXME: JobError needs a unit test
        else:
            fastboot_cmd = ['fastboot', '-s', serial_number, 'devices']
            command_output = self.run_command(fastboot_cmd)
            if command_output and serial_number in command_output:
                self.logger.debug("Device is in fastboot: %s" % command_output)
                fastboot_cmd = ['fastboot', '-s', serial_number,
                                'reboot-bootloader']
                command_output = self.run_command(fastboot_cmd)
                if command_output and 'OKAY' not in command_output:
                    raise JobError("Unable to enter fastboot: %s" %
                                   command_output)  # FIXME: JobError needs a unit test
        return connection


class FastbootUpdateAction(DeployAction):
    """
    Fastboot update image.
    """

    def __init__(self):
        super(FastbootUpdateAction, self).__init__()
        self.name = "fastboot_update_action"
        self.description = "fastboot update image"
        self.summary = "fastboot update"
        self.retries = 3
        self.sleep = 10

    def validate(self):
        super(FastbootUpdateAction, self).validate()
        if 'download_action' not in self.data:
            raise RuntimeError("download-action missing: %s" % self.name)
        if 'file' not in self.data['download_action']['image']:
            self.errors = "no file specified for fastboot"
        if 'serial_number' not in self.job.device:
            self.errors = "device serial number missing"
            if self.job.device['serial_number'] == '0000000000':
                self.errors = "device serial number unset"

    def run(self, connection, args=None):
        connection = super(FastbootUpdateAction, self).run(connection, args)
        serial_number = self.job.device['serial_number']
        fastboot_cmd = ['fastboot', '-s', serial_number, '-w', 'update',
                        self.data['download_action']['image']['file']]
        command_output = self.run_command(fastboot_cmd)
        if command_output and 'error' in command_output:
            raise JobError("Unable to update image using fastboot: %s" %
                           command_output)  # FIXME: JobError needs a unit test
        return connection


class FastbootRebootAction(DeployAction):
    """
    Fastboot Reboot.
    """

    def __init__(self):
        super(FastbootRebootAction, self).__init__()
        self.name = "fastboot_reboot_action"
        self.description = "fastboot reboot"
        self.summary = "fastboot reboot"
        self.retries = 3
        self.sleep = FASTBOOT_REBOOT_TIMEOUT

    def validate(self):
        super(FastbootRebootAction, self).validate()
        if 'serial_number' not in self.job.device:
            self.errors = "device serial number missing"
            if self.job.device['serial_number'] == '0000000000':
                self.errors = "device serial number unset"

    def run(self, connection, args=None):
        connection = super(FastbootRebootAction, self).run(connection, args)
        serial_number = self.job.device['serial_number']
        fastboot_cmd = ['fastboot', '-s', serial_number, 'reboot']
        command_output = self.run_command(fastboot_cmd)
        if command_output and 'error' in command_output:
            raise JobError("Unable to reboot using fastboot: %s" %
                           command_output)  # FIXME: JobError needs a unit test
        return connection


class ApplyBootAction(DeployAction):
    """
    Fastboot deploy boot image.
    """

    def __init__(self):
        super(ApplyBootAction, self).__init__()
        self.name = "fastboot_apply_boot_action"
        self.description = "fastboot apply boot image"
        self.summary = "fastboot apply boot"
        self.retries = 3
        self.sleep = 10

    def validate(self):
        super(ApplyBootAction, self).validate()
        if 'download_action' not in self.data:
            raise RuntimeError("download-action missing: %s" % self.name)
        if 'file' not in self.data['download_action']['boot']:
            self.errors = "no file specified for fastboot boot image"
        if 'serial_number' not in self.job.device:
            self.errors = "device serial number missing"
            if self.job.device['serial_number'] == '0000000000':
                self.errors = "device serial number unset"

    def run(self, connection, args=None):
        connection = super(ApplyBootAction, self).run(connection, args)
        serial_number = self.job.device['serial_number']
        fastboot_cmd = ['fastboot', '-s', serial_number, 'flash', 'boot',
                        self.data['download_action']['boot']['file']]
        command_output = self.run_command(fastboot_cmd)
        if command_output and 'error' in command_output:
            raise JobError("Unable to apply boot image using fastboot: %s" %
                           command_output)  # FIXME: JobError needs a unit test
        return connection


class ApplyUserdataAction(DeployAction):
    """
    Fastboot deploy userdata image.
    """

    def __init__(self):
        super(ApplyUserdataAction, self).__init__()
        self.name = "fastboot_apply_userdata_action"
        self.description = "fastboot apply userdata image"
        self.summary = "fastboot apply userdata"
        self.retries = 3
        self.sleep = 10

    def validate(self):
        super(ApplyUserdataAction, self).validate()
        if 'download_action' not in self.data:
            raise RuntimeError("download-action missing: %s" % self.name)
        if 'file' not in self.data['download_action']['userdata']:
            self.errors = "no file specified for fastboot userdata image"
        if 'serial_number' not in self.job.device:
            self.errors = "device serial number missing"
            if self.job.device['serial_number'] == '0000000000':
                self.errors = "device serial number unset"

    def run(self, connection, args=None):
        connection = super(ApplyUserdataAction, self).run(connection, args)
        serial_number = self.job.device['serial_number']
        fastboot_cmd = ['fastboot', '-s', serial_number,
                        'flash', 'userdata',
                        self.data['download_action']['userdata']['file']]
        command_output = self.run_command(fastboot_cmd)
        if command_output and 'error' in command_output:
            raise JobError("Unable to apply userdata image using fastboot: %s" %
                           command_output)  # FIXME: JobError needs a unit test
        return connection


class ApplySystemAction(DeployAction):
    """
    Fastboot deploy system image.
    """

    def __init__(self):
        super(ApplySystemAction, self).__init__()
        self.name = "fastboot_apply_system_action"
        self.description = "fastboot apply system image"
        self.summary = "fastboot apply system"
        self.retries = 3
        self.sleep = 10

    def validate(self):
        super(ApplySystemAction, self).validate()
        if 'download_action' not in self.data:
            raise RuntimeError("download-action missing: %s" % self.name)
        if 'file' not in self.data['download_action']['system']:
            self.errors = "no file specified for fastboot system image"
        if 'serial_number' not in self.job.device:
            self.errors = "device serial number missing"
            if self.job.device['serial_number'] == '0000000000':
                self.errors = "device serial number unset"

    def run(self, connection, args=None):
        connection = super(ApplySystemAction, self).run(connection, args)
        serial_number = self.job.device['serial_number']
        fastboot_cmd = ['fastboot', '-s', serial_number,
                        'flash', 'system',
                        self.data['download_action']['system']['file']]
        command_output = self.run_command(fastboot_cmd)
        if command_output and 'error' in command_output:
            raise JobError("Unable to apply system image using fastboot: %s" %
                           command_output)  # FIXME: JobError needs a unit test
        return connection
