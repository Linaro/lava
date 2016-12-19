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

import os
from time import sleep
from lava_dispatcher.pipeline.logical import Deployment
from lava_dispatcher.pipeline.action import (
    Action,
    Pipeline,
    JobError,
)
from lava_dispatcher.pipeline.actions.deploy import DeployAction
from lava_dispatcher.pipeline.actions.deploy.overlay import OverlayAction
from lava_dispatcher.pipeline.actions.deploy.apply_overlay import ApplyLxcOverlay
from lava_dispatcher.pipeline.actions.deploy.environment import DeployDeviceEnvironment
from lava_dispatcher.pipeline.utils.shell import infrastructure_error
from lava_dispatcher.pipeline.protocols.lxc import LxcProtocol
from lava_dispatcher.pipeline.utils.constants import (
    LXC_TEMPLATE_WITH_MIRROR,
    USB_SHOW_UP_TIMEOUT,
)


def lxc_accept(device, parameters):
    """
    Each lxc deployment strategy uses these checks as a base, then makes the
    final decision on the style of lxc deployment.
    """
    if 'to' not in parameters:
        return False
    if 'os' not in parameters:
        return False
    if parameters['to'] != 'lxc':
        return False
    if not device:
        return False
    if 'actions' not in device:
        raise RuntimeError("Invalid device configuration")
    if 'deploy' not in device['actions']:
        return False
    if 'methods' not in device['actions']['deploy']:
        raise RuntimeError("Device misconfiguration")
    return True


class Lxc(Deployment):
    """
    Strategy class for a lxc deployment.
    Downloads the relevant parts, copies to the locations using lxc.
    """
    compatibility = 1

    def __init__(self, parent, parameters):
        super(Lxc, self).__init__(parent)
        self.action = LxcAction()
        self.action.section = self.action_type
        self.action.job = self.job
        parent.add_action(self.action, parameters)

    @classmethod
    def accepts(cls, device, parameters):
        if not lxc_accept(device, parameters):
            return False
        if 'lxc' in device['actions']['deploy']['methods']:
            return True
        return False


class LxcAction(DeployAction):  # pylint:disable=too-many-instance-attributes

    def __init__(self):
        super(LxcAction, self).__init__()
        self.name = "lxc-deploy"
        self.description = "download files and deploy using lxc"
        self.summary = "lxc deployment"
        self.lxc_data = {}

    def validate(self):
        super(LxcAction, self).validate()
        if LxcProtocol.name not in [protocol.name for protocol in self.job.protocols]:
            self.errors = "Invalid job - missing protocol"
        self.errors = infrastructure_error('lxc-create')
        lava_test_results_dir = self.parameters['deployment_data']['lava_test_results_dir']
        lava_test_results_dir = lava_test_results_dir % self.job.job_id
        self.set_namespace_data(action='test', label='results', key='lava_test_results_dir', value=lava_test_results_dir)
        lava_test_sh_cmd = self.parameters['deployment_data']['lava_test_sh_cmd']
        self.set_namespace_data(action=self.name, label='shared', key='lava_test_sh_cmd', value=lava_test_sh_cmd)

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job,
                                          parameters=parameters)
        self.internal_pipeline.add_action(LxcCreateAction())
        # needed if export device environment is also to be used
        self.internal_pipeline.add_action(DeployDeviceEnvironment())
        self.internal_pipeline.add_action(OverlayAction())
        self.internal_pipeline.add_action(ApplyLxcOverlay())


class LxcCreateAction(DeployAction):
    """
    Creates Lxc container.
    """

    def __init__(self):
        super(LxcCreateAction, self).__init__()
        self.name = "lxc-create-action"
        self.description = "create lxc action"
        self.summary = "create lxc"
        self.retries = 10
        self.sleep = 10
        self.lxc_data = {}

    def _set_lxc_data(self):
        protocols = [protocol for protocol in self.job.protocols
                     if protocol.name == LxcProtocol.name]
        if protocols:
            protocol = protocols[0]
            self.set_namespace_data(action=self.name, label='lxc', key='name', value=protocol.lxc_name)
            self.lxc_data['lxc_name'] = protocol.lxc_name
            self.lxc_data['lxc_distribution'] = protocol.lxc_dist
            self.lxc_data['lxc_release'] = protocol.lxc_release
            self.lxc_data['lxc_arch'] = protocol.lxc_arch
            self.lxc_data['lxc_template'] = protocol.lxc_template
            self.lxc_data['lxc_mirror'] = protocol.lxc_mirror
            self.lxc_data['lxc_security_mirror'] = protocol.lxc_security_mirror

    def validate(self):
        super(LxcCreateAction, self).validate()
        # set lxc_data
        self._set_lxc_data()

    def run(self, connection, args=None):
        connection = super(LxcCreateAction, self).run(connection, args)
        if self.lxc_data['lxc_template'] in LXC_TEMPLATE_WITH_MIRROR:
            lxc_cmd = ['lxc-create', '-q', '-t', self.lxc_data['lxc_template'],
                       '-n', self.lxc_data['lxc_name'], '--', '--release',
                       self.lxc_data['lxc_release'], '--arch',
                       self.lxc_data['lxc_arch']]
            if self.lxc_data['lxc_mirror']:
                lxc_cmd += ['--mirror', self.lxc_data['lxc_mirror']]
            if self.lxc_data['lxc_security_mirror']:
                lxc_cmd += ['--security-mirror',
                            self.lxc_data['lxc_security_mirror']]
            if 'packages' in self.parameters:
                lxc_cmd += ['--packages',
                            ','.join(self.parameters['packages'])]
            cmd_out_str = 'Generation complete.'
        else:
            lxc_cmd = ['lxc-create', '-q', '-t', self.lxc_data['lxc_template'],
                       '-n', self.lxc_data['lxc_name'], '--', '--dist',
                       self.lxc_data['lxc_distribution'], '--release',
                       self.lxc_data['lxc_release'], '--arch',
                       self.lxc_data['lxc_arch']]
        if not self.run_command(lxc_cmd, allow_silent=True):
            raise JobError("Unable to create lxc container")
        else:
            self.results = {'status': self.lxc_data['lxc_name']}
        return connection


class LxcAddDeviceAction(Action):
    """Add usb device to lxc.
    """
    def __init__(self):
        super(LxcAddDeviceAction, self).__init__()
        self.name = "lxc-add-device-action"
        self.description = "action that adds usb devices to lxc"
        self.summary = "device add lxc"
        self.retries = 10
        self.sleep = 10

    def run(self, connection, args=None):
        connection = super(LxcAddDeviceAction, self).run(connection, args)
        # this is the device namespace - the lxc namespace is not accessible
        lxc_name = None
        protocol = [protocol for protocol in self.job.protocols if protocol.name == LxcProtocol.name][0]
        if protocol:
            lxc_name = protocol.lxc_name
        if not lxc_name:
            self.logger.debug("No LXC device requested")
            self.errors = "Unable to use fastboot"
            return connection
        if 'device_path' in list(self.job.device.keys()):
            device_path = self.job.device['device_path']
            if not isinstance(device_path, list):
                raise JobError("device_path should be a list")

            if device_path:
                # Wait USB_SHOW_UP_TIMEOUT seconds for usb device to show up
                self.logger.info("[%s] Wait %d seconds for usb device to show up",
                                 self.name, USB_SHOW_UP_TIMEOUT)
                sleep(USB_SHOW_UP_TIMEOUT)

                for path in device_path:
                    path = os.path.realpath(path)
                    if os.path.isdir(path):
                        devices = os.listdir(path)
                    else:
                        devices = [path]

                    for device in devices:
                        device = os.path.join(path, device)
                        if os.path.exists(device):
                            lxc_cmd = ['lxc-device', '-n', lxc_name, 'add',
                                       device]
                            log = self.run_command(lxc_cmd)
                            self.logger.debug(log)
                            self.logger.debug("%s: devices added from %s",
                                              lxc_name, path)
                        else:
                            self.logger.info("%s: skipped adding %s device",
                                             lxc_name, device)
            else:
                self.logger.warning("device_path is None")
        else:
            self.logger.error("No device path defined for this device.")
        return connection
