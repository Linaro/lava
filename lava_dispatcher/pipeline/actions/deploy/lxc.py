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
from lava_dispatcher.pipeline.actions.deploy.apply_overlay import ApplyLxcOverlay
from lava_dispatcher.pipeline.utils.shell import infrastructure_error
from lava_dispatcher.pipeline.protocols.lxc import LxcProtocol


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

    def validate(self):
        super(LxcAction, self).validate()
        if LxcProtocol.name not in [protocol.name for protocol in self.job.protocols]:
            self.errors = "Invalid job - missing protocol"
        self.errors = infrastructure_error('lxc-create')
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
        self.protocols = [protocol for protocol in self.job.protocols if protocol.name == LxcProtocol.name]
        self.set_common_data('lxc', 'name', self.protocols[0].lxc_name)
        self.set_common_data('lxc', 'distribution', self.protocols[0].lxc_dist)
        self.set_common_data('lxc', 'release', self.protocols[0].lxc_release)
        self.set_common_data('lxc', 'arch', self.protocols[0].lxc_arch)
        self.internal_pipeline.add_action(LxcCreateAction())
        self.internal_pipeline.add_action(OverlayAction())
        self.internal_pipeline.add_action(ApplyLxcOverlay())


class LxcCreateAction(DeployAction):
    """
    Creates Lxc container.
    """

    def __init__(self):
        super(LxcCreateAction, self).__init__()
        self.name = "lxc_create_action"
        self.description = "create lxc action"
        self.summary = "create lxc"
        self.retries = 10
        self.sleep = 10

    def validate(self):
        super(LxcCreateAction, self).validate()

    def run(self, connection, args=None):
        connection = super(LxcCreateAction, self).run(connection, args)
        lxc_name = self.get_common_data('lxc', 'name')
        lxc_cmd = ['lxc-create', '-t', 'download', '-n', lxc_name, '--',
                   '--dist', self.get_common_data('lxc', 'distribution'),
                   '--release', self.get_common_data('lxc', 'release'),
                   '--arch', self.get_common_data('lxc', 'arch')]
        command_output = self.run_command(lxc_cmd)
        if command_output and 'Unpacking the rootfs' not in command_output:
            raise JobError("Unable to create lxc container: %s" %
                           command_output)  # FIXME: JobError needs a unit test
        else:
            self.results = {'status': lxc_name}
        return connection
