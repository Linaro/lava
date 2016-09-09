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
from lava_dispatcher.pipeline.connections.serial import ConnectDevice
from lava_dispatcher.pipeline.power import PowerOn
from lava_dispatcher.pipeline.action import (
    Pipeline,
    JobError,
)
from lava_dispatcher.pipeline.actions.deploy import DeployAction
from lava_dispatcher.pipeline.actions.deploy.lxc import LxcAddDeviceAction
from lava_dispatcher.pipeline.actions.deploy.overlay import OverlayAction
from lava_dispatcher.pipeline.actions.deploy.download import (
    DownloaderAction,
)
from lava_dispatcher.pipeline.utils.filesystem import mkdtemp, copy_to_lxc
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
    if 'adb_serial_number' not in device:
        return False
    if 'fastboot_serial_number' not in device:
        return False
    if 'methods' not in device['actions']['deploy']:
        raise RuntimeError("Device misconfiguration")
    return True


class Fastboot(Deployment):
    """
    Strategy class for a fastboot deployment.
    Downloads the relevant parts, copies to the locations using fastboot.
    """
    compatibility = 1

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
        lava_test_results_dir = self.parameters['deployment_data']['lava_test_results_dir']
        lava_test_results_dir = lava_test_results_dir % self.job.job_id
        self.data['lava_test_results_dir'] = lava_test_results_dir
        namespace = self.parameters.get('namespace', None)
        if namespace:
            self.action_namespaces.append(namespace)
            self.set_common_data(namespace, 'lava_test_results_dir',
                                 lava_test_results_dir)
            lava_test_sh_cmd = self.parameters['deployment_data']['lava_test_sh_cmd']
            self.set_common_data(namespace, 'lava_test_sh_cmd',
                                 lava_test_sh_cmd)

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.internal_pipeline.add_action(OverlayAction())
        if hasattr(self.job.device, 'power_state'):
            if self.job.device.power_state in ['on', 'off']:
                self.internal_pipeline.add_action(ConnectDevice())
                self.internal_pipeline.add_action(PowerOn())
        self.internal_pipeline.add_action(EnterFastbootAction())
        self.internal_pipeline.add_action(LxcAddDeviceAction())

        image_keys = list(parameters['images'].keys())
        # Add the required actions
        checks = [('image', FastbootUpdateAction),
                  ('ptable', ApplyPtableAction),
                  ('boot', ApplyBootAction),
                  ('cache', ApplyCacheAction),
                  ('userdata', ApplyUserdataAction),
                  ('system', ApplySystemAction),
                  ('vendor', ApplyVendorAction)]
        for (key, cls) in checks:
            if key in image_keys:
                download = DownloaderAction(key, self.fastboot_dir)
                download.max_retries = 3  # overridden by failure_retry in the parameters, if set.
                self.internal_pipeline.add_action(download)
                self.internal_pipeline.add_action(cls())


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
        if 'adb_serial_number' not in self.job.device:
            self.errors = "device adb serial number missing"
            if self.job.device['adb_serial_number'] == '0000000000':
                self.errors = "device adb serial number unset"
        if 'fastboot_serial_number' not in self.job.device:
            self.errors = "device fastboot serial number missing"
            if self.job.device['fastboot_serial_number'] == '0000000000':
                self.errors = "device fastboot serial number unset"

    def run(self, connection, args=None):
        connection = super(EnterFastbootAction, self).run(connection, args)
        lxc_name = self.get_common_data('lxc', 'name')
        fastboot_serial_number = self.job.device['fastboot_serial_number']

        # Try to enter fastboot mode with adb.
        adb_serial_number = self.job.device['adb_serial_number']
        adb_cmd = ['lxc-attach', '-n', lxc_name, '--', 'adb', '-s',
                   adb_serial_number, 'devices']
        command_output = self.run_command(adb_cmd)
        if command_output and adb_serial_number in command_output:
            self.logger.debug("Device is in adb: %s", command_output)
            adb_cmd = ['lxc-attach', '-n', lxc_name, '--', 'adb',
                       '-s', adb_serial_number, 'reboot-bootloader']
            command_output = self.run_command(adb_cmd)
            if command_output and 'error' in command_output:
                raise JobError("Unable to enter fastboot: %s" %
                               command_output)  # FIXME: JobError needs a unit test
            return connection

        # Enter fastboot mode with fastboot.
        fastboot_cmd = ['lxc-attach', '-n', lxc_name, '--', 'fastboot', '-s',
                        fastboot_serial_number, 'devices']
        command_output = self.run_command(fastboot_cmd)
        if command_output and fastboot_serial_number in command_output:
            self.logger.debug("Device is in fastboot: %s", command_output)
            fastboot_cmd = ['lxc-attach', '-n', lxc_name, '--', 'fastboot',
                            '-s', fastboot_serial_number, 'reboot-bootloader']
            command_output = self.run_command(fastboot_cmd)
            if command_output and 'OKAY' not in command_output:
                raise JobError("Unable to enter fastboot: %s" %
                               command_output)  # FIXME: JobError needs a unit test
            else:
                status = [status.strip() for status in command_output.split(
                    '\n') if 'finished' in status][0]
                self.results = {'status': status}
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
        if 'fastboot_serial_number' not in self.job.device:
            self.errors = "device fastboot serial number missing"
            if self.job.device['fastboot_serial_number'] == '0000000000':
                self.errors = "device fastboot serial number unset"

    def run(self, connection, args=None):
        connection = super(FastbootUpdateAction, self).run(connection, args)
        lxc_name = self.get_common_data('lxc', 'name')
        src = self.data['download_action']['image']['file']
        dst = copy_to_lxc(lxc_name, src)
        serial_number = self.job.device['fastboot_serial_number']
        fastboot_cmd = ['lxc-attach', '-n', lxc_name, '--', 'fastboot',
                        '-s', serial_number, '-w', 'update', dst]
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
        if 'fastboot_serial_number' not in self.job.device:
            self.errors = "device fastboot serial number missing"
            if self.job.device['fastboot_serial_number'] == '0000000000':
                self.errors = "device fastboot serial number unset"

    def run(self, connection, args=None):
        connection = super(FastbootRebootAction, self).run(connection, args)
        lxc_name = self.get_common_data('lxc', 'name')
        serial_number = self.job.device['fastboot_serial_number']
        fastboot_cmd = ['lxc-attach', '-n', lxc_name, '--', 'fastboot',
                        '-s', serial_number, 'reboot']
        command_output = self.run_command(fastboot_cmd)
        if command_output and 'error' in command_output:
            raise JobError("Unable to reboot using fastboot: %s" %
                           command_output)  # FIXME: JobError needs a unit test
        return connection


class ApplyPtableAction(DeployAction):
    """
    Fastboot deploy ptable image.
    """

    def __init__(self):
        super(ApplyPtableAction, self).__init__()
        self.name = "fastboot_apply_ptable_action"
        self.description = "fastboot apply ptable image"
        self.summary = "fastboot apply ptable"
        self.retries = 3
        self.sleep = 10

    def validate(self):
        super(ApplyPtableAction, self).validate()
        if 'download_action' not in self.data:
            raise RuntimeError("download-action missing: %s" % self.name)
        if 'file' not in self.data['download_action']['ptable']:
            self.errors = "no file specified for fastboot ptable image"
        if 'fastboot_serial_number' not in self.job.device:
            self.errors = "device fastboot serial number missing"
            if self.job.device['fastboot_serial_number'] == '0000000000':
                self.errors = "device fastboot serial number unset"

    def run(self, connection, args=None):
        connection = super(ApplyPtableAction, self).run(connection, args)
        lxc_name = self.get_common_data('lxc', 'name')
        src = self.data['download_action']['ptable']['file']
        dst = copy_to_lxc(lxc_name, src)
        serial_number = self.job.device['fastboot_serial_number']
        fastboot_cmd = ['lxc-attach', '-n', lxc_name, '--', 'fastboot',
                        '-s', serial_number, 'flash', 'ptable', dst]
        command_output = self.run_command(fastboot_cmd)
        if command_output and 'error' in command_output:
            raise JobError("Unable to apply ptable image using fastboot: %s" %
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
        if 'fastboot_serial_number' not in self.job.device:
            self.errors = "device fastboot serial number missing"
            if self.job.device['fastboot_serial_number'] == '0000000000':
                self.errors = "device fastboot serial number unset"

    def run(self, connection, args=None):
        connection = super(ApplyBootAction, self).run(connection, args)
        serial_number = self.job.device['fastboot_serial_number']
        lxc_name = self.get_common_data('lxc', 'name')
        src = self.data['download_action']['boot']['file']
        dst = copy_to_lxc(lxc_name, src)
        fastboot_cmd = ['lxc-attach', '-n', lxc_name, '--', 'fastboot',
                        '-s', serial_number, 'flash', 'boot', dst]
        command_output = self.run_command(fastboot_cmd)
        if command_output and 'error' in command_output:
            raise JobError("Unable to apply boot image using fastboot: %s" %
                           command_output)  # FIXME: JobError needs a unit test
        return connection


class ApplyCacheAction(DeployAction):
    """
    Fastboot deploy cache image.
    """

    def __init__(self):
        super(ApplyCacheAction, self).__init__()
        self.name = "fastboot_apply_cache_action"
        self.description = "fastboot apply cache image"
        self.summary = "fastboot apply cache"
        self.retries = 3
        self.sleep = 10

    def validate(self):
        super(ApplyCacheAction, self).validate()
        if 'download_action' not in self.data:
            raise RuntimeError("download-action missing: %s" % self.name)
        if 'file' not in self.data['download_action']['cache']:
            self.errors = "no file specified for fastboot cache image"
        if 'fastboot_serial_number' not in self.job.device:
            self.errors = "device fastboot serial number missing"
            if self.job.device['fastboot_serial_number'] == '0000000000':
                self.errors = "device fastboot serial number unset"

    def run(self, connection, args=None):
        connection = super(ApplyCacheAction, self).run(connection, args)
        lxc_name = self.get_common_data('lxc', 'name')
        src = self.data['download_action']['cache']['file']
        dst = copy_to_lxc(lxc_name, src)
        serial_number = self.job.device['fastboot_serial_number']
        fastboot_cmd = ['lxc-attach', '-n', lxc_name, '--', 'fastboot',
                        '-s', serial_number, 'flash', 'cache', dst]
        command_output = self.run_command(fastboot_cmd)
        if command_output and 'error' in command_output:
            raise JobError("Unable to apply cache image using fastboot: %s" %
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
        if 'fastboot_serial_number' not in self.job.device:
            self.errors = "device fastboot serial number missing"
            if self.job.device['fastboot_serial_number'] == '0000000000':
                self.errors = "device fastboot serial number unset"

    def run(self, connection, args=None):
        connection = super(ApplyUserdataAction, self).run(connection, args)
        lxc_name = self.get_common_data('lxc', 'name')
        src = self.data['download_action']['userdata']['file']
        dst = copy_to_lxc(lxc_name, src)
        serial_number = self.job.device['fastboot_serial_number']
        fastboot_cmd = ['lxc-attach', '-n', lxc_name, '--', 'fastboot',
                        '-s', serial_number, 'flash', 'userdata', dst]
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
        if 'fastboot_serial_number' not in self.job.device:
            self.errors = "device fastboot serial number missing"
            if self.job.device['fastboot_serial_number'] == '0000000000':
                self.errors = "device fastboot serial number unset"

    def run(self, connection, args=None):
        connection = super(ApplySystemAction, self).run(connection, args)
        lxc_name = self.get_common_data('lxc', 'name')
        src = self.data['download_action']['system']['file']
        dst = copy_to_lxc(lxc_name, src)
        serial_number = self.job.device['fastboot_serial_number']
        fastboot_cmd = ['lxc-attach', '-n', lxc_name, '--', 'fastboot',
                        '-s', serial_number, 'flash', 'system', dst]
        command_output = self.run_command(fastboot_cmd)
        if command_output and 'error' in command_output:
            raise JobError("Unable to apply system image using fastboot: %s" %
                           command_output)  # FIXME: JobError needs a unit test
        return connection


class ApplyVendorAction(DeployAction):
    """
    Fastboot deploy vendor image.
    """

    def __init__(self):
        super(ApplyVendorAction, self).__init__()
        self.name = "fastboot_apply_vendor_action"
        self.description = "fastboot apply vendor image"
        self.summary = "fastboot apply vendor"
        self.retries = 3
        self.sleep = 10

    def validate(self):
        super(ApplyVendorAction, self).validate()
        if 'download_action' not in self.data:
            raise RuntimeError("download-action missing: %s" % self.name)
        if 'file' not in self.data['download_action']['vendor']:
            self.errors = "no file specified for fastboot vendor image"
        if 'fastboot_serial_number' not in self.job.device:
            self.errors = "device fastboot serial number missing"
            if self.job.device['fastboot_serial_number'] == '0000000000':
                self.errors = "device fastboot serial number unset"

    def run(self, connection, args=None):
        connection = super(ApplyVendorAction, self).run(connection, args)
        lxc_name = self.get_common_data('lxc', 'name')
        src = self.data['download_action']['vendor']['file']
        dst = copy_to_lxc(lxc_name, src)
        serial_number = self.job.device['fastboot_serial_number']
        fastboot_cmd = ['lxc-attach', '-n', lxc_name, '--', 'fastboot',
                        '-s', serial_number, 'flash', 'vendor', dst]
        command_output = self.run_command(fastboot_cmd)
        if command_output and 'error' in command_output:
            raise JobError("Unable to apply vendor image using fastboot: %s" %
                           command_output)  # FIXME: JobError needs a unit test
        return connection
