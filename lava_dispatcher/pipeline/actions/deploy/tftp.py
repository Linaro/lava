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

# List just the subclasses supported for this base strategy
# imported by the parser to populate the list of subclasses.

import os
from lava_dispatcher.pipeline.action import Pipeline, InfrastructureError
from lava_dispatcher.pipeline.logical import Deployment
from lava_dispatcher.pipeline.actions.deploy import DeployAction
from lava_dispatcher.pipeline.actions.deploy.download import DownloaderAction
from lava_dispatcher.pipeline.actions.deploy.apply_overlay import PrepareOverlayTftp
from lava_dispatcher.pipeline.actions.deploy.environment import DeployDeviceEnvironment
from lava_dispatcher.pipeline.utils.shell import which
from lava_dispatcher.pipeline.utils.filesystem import mkdtemp, tftpd_dir
from lava_dispatcher.pipeline.utils.constants import DISPATCHER_DOWNLOAD_DIR


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
        raise RuntimeError("Invalid device configuration")
    if 'deploy' not in device['actions']:
        return False
    if 'methods' not in device['actions']['deploy']:
        raise RuntimeError("Device misconfiguration")
    return True


class Tftp(Deployment):
    """
    Strategy class for a tftp ramdisk based Deployment.
    Downloads the relevant parts, copies to the tftp location.
    Limited to what the bootloader can deploy which means ramdisk or nfsrootfs.
    rootfs deployments would format the device and create a single partition for the rootfs.
    """
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
        self.summary = "tftp deploment"
        self.tftp_dir = tftpd_dir()
        self.suffix = None
        try:
            self.tftp_dir = mkdtemp(basedir=self.tftp_dir)
        except OSError:
            # allows for unit tests to operate as normal user.
            self.suffix = '/'
        self.download_dir = DISPATCHER_DOWNLOAD_DIR  # used for NFS
        try:
            self.download_dir = mkdtemp(basedir=DISPATCHER_DOWNLOAD_DIR)
        except OSError:
            pass

    def validate(self):
        super(TftpAction, self).validate()
        if 'kernel' not in self.parameters:
            self.errors = "%s needs a kernel to deploy" % self.name
        if not self.valid:
            return
        lava_test_results_dir = self.parameters['deployment_data']['lava_test_results_dir']
        self.data['lava_test_results_dir'] = lava_test_results_dir % self.job.job_id
        if self.suffix:
            self.data[self.name].setdefault('suffix', self.suffix)
        self.data[self.name].setdefault('suffix', os.path.basename(self.tftp_dir))
        try:
            which("in.tftpd")
        except InfrastructureError as exc:
            self.errors = str(exc)

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        if 'ramdisk' in parameters:
            download = DownloaderAction('ramdisk', path=self.tftp_dir)
            download.max_retries = 3  # overridden by failure_retry in the parameters, if set.
            self.internal_pipeline.add_action(download)
            self.set_common_data('tftp', 'ramdisk', True)
        if 'kernel' in parameters:
            download = DownloaderAction('kernel', path=self.tftp_dir)
            download.max_retries = 3
            self.internal_pipeline.add_action(download)
        if 'dtb' in parameters:
            download = DownloaderAction('dtb', path=self.tftp_dir)
            download.max_retries = 3
            self.internal_pipeline.add_action(download)
        if 'nfsrootfs' in parameters:
            download = DownloaderAction('nfsrootfs', path=self.download_dir)
            download.max_retries = 3
            self.internal_pipeline.add_action(download)
        if 'modules' in parameters:
            download = DownloaderAction('modules', path=self.tftp_dir)
            download.max_retries = 3
            self.internal_pipeline.add_action(download)
        # TftpAction is a deployment, so once the files are in place, just do the overlay
        self.internal_pipeline.add_action(PrepareOverlayTftp())
        self.internal_pipeline.add_action(DeployDeviceEnvironment())
