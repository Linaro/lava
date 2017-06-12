# Copyright (C) 2014,2015 Linaro Limited
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

# List just the subclasses supported for this base strategy
# imported by the parser to populate the list of subclasses.

import os
import tempfile

from lava_dispatcher.pipeline.action import (
    ConfigurationError,
    Pipeline
)
from lava_dispatcher.pipeline.logical import Deployment
from lava_dispatcher.pipeline.actions.deploy import DeployAction
from lava_dispatcher.pipeline.actions.deploy.lxc import LxcAddDeviceAction
from lava_dispatcher.pipeline.actions.deploy.download import DownloaderAction
from lava_dispatcher.pipeline.actions.deploy.apply_overlay import PrepareOverlayTftp
from lava_dispatcher.pipeline.actions.deploy.environment import DeployDeviceEnvironment
from lava_dispatcher.pipeline.utils.shell import infrastructure_error
from lava_dispatcher.pipeline.utils.filesystem import tftpd_dir


def tftp_accept(device, parameters):
    """
    Each tftp deployment strategy uses these checks
    as a base, then makes the final decision on the
    style of tftp deployment.
    """
    if 'to' not in parameters:
        return False
    if parameters['to'] != 'tftp':
        return False
    if not device:
        return False
    if 'actions' not in device:
        raise ConfigurationError("Invalid device configuration")
    if 'deploy' not in device['actions']:
        return False
    if 'methods' not in device['actions']['deploy']:
        raise ConfigurationError("Device misconfiguration")
    return True


class Tftp(Deployment):
    """
    Strategy class for a tftp ramdisk based Deployment.
    Downloads the relevant parts, copies to the tftp location.
    Limited to what the bootloader can deploy which means ramdisk or nfsrootfs.
    rootfs deployments would format the device and create a single partition for the rootfs.
    """

    compatibility = 1

    def __init__(self, parent, parameters):
        super(Tftp, self).__init__(parent)
        self.action = TftpAction()
        self.action.section = self.action_type
        self.action.job = self.job
        parent.add_action(self.action, parameters)

    @classmethod
    def accepts(cls, device, parameters):
        if not tftp_accept(device, parameters):
            return False
        if 'tftp' in device['actions']['deploy']['methods']:
            return True
        return False


class TftpAction(DeployAction):  # pylint:disable=too-many-instance-attributes

    def __init__(self):
        super(TftpAction, self).__init__()
        self.name = "tftp-deploy"
        self.description = "download files and deploy using tftp"
        self.summary = "tftp deployment"
        self.tftp_dir = None

    def validate(self):
        super(TftpAction, self).validate()
        if 'kernel' not in self.parameters:
            self.errors = "%s needs a kernel to deploy" % self.name
        if not self.valid:
            return
        if 'nfs_url' in self.parameters:
            self.errors = "Use a persistent_nfs dictionary instead of nfs_url"
        if 'nfsrootfs' in self.parameters and 'persistent_nfs' in self.parameters:
            self.errors = "Only one of nfsrootfs or persistent_nfs can be specified"
        if self.test_needs_deployment(self.parameters):
            lava_test_results_base = self.parameters['deployment_data']['lava_test_results_dir']
            lava_test_results_dir = lava_test_results_base % self.job.job_id
            self.set_namespace_data(action='test', label='results', key='lava_test_results_dir', value=lava_test_results_dir)
        # Extract the 3 last path elements. See action.mkdtemp()
        suffix = os.path.join(*self.tftp_dir.split('/')[-2:])
        self.set_namespace_data(action=self.name, label='tftp', key='suffix', value=suffix)
        self.errors = infrastructure_error('in.tftpd')

        # Check that the tmp directory is in the tftpd_dir or in /tmp for the
        # unit tests
        tftpd_directory = os.path.realpath(tftpd_dir())
        tftp_dir = os.path.realpath(self.tftp_dir)
        tmp_dir = tempfile.gettempdir()
        if not tftp_dir.startswith(tftpd_directory) and \
           not tftp_dir.startswith(tmp_dir):
            self.errors = "tftpd directory is not configured correctly, see /etc/default/tftpd-hpa"

    def populate(self, parameters):
        self.tftp_dir = self.mkdtemp(override=tftpd_dir())
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.set_namespace_data(action=self.name, label='tftp', key='tftp_dir', value=self.tftp_dir, parameters=parameters)

        for key in ['ramdisk', 'kernel', 'dtb', 'nfsrootfs', 'modules', 'preseed']:
            if key in parameters:
                self.internal_pipeline.add_action(DownloaderAction(key, path=self.tftp_dir))
                if key == 'ramdisk':
                    self.set_namespace_data(action=self.name, label='tftp', key='ramdisk', value=True, parameters=parameters)

        # TftpAction is a deployment, so once the files are in place, just do the overlay
        self.internal_pipeline.add_action(PrepareOverlayTftp())
        self.internal_pipeline.add_action(LxcAddDeviceAction())
        if self.test_needs_deployment(parameters):
            self.internal_pipeline.add_action(DeployDeviceEnvironment())
