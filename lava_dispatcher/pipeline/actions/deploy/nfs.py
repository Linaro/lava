# Copyright (C) 2016 Linaro Limited
#
# Author: Dean Arnold <dean.arnold@linaro.org>
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

from lava_dispatcher.pipeline.action import Pipeline
from lava_dispatcher.pipeline.logical import Deployment
from lava_dispatcher.pipeline.actions.deploy import DeployAction
from lava_dispatcher.pipeline.actions.deploy.download import DownloaderAction
from lava_dispatcher.pipeline.actions.deploy.apply_overlay import (
    PrepareOverlayTftp,
    ExtractNfsRootfs,
    OverlayAction,
    ExtractModules,
    ApplyOverlayTftp,
)
from lava_dispatcher.pipeline.actions.deploy.environment import DeployDeviceEnvironment
from lava_dispatcher.pipeline.utils.filesystem import mkdtemp
from lava_dispatcher.pipeline.utils.constants import DISPATCHER_DOWNLOAD_DIR


def nfs_accept(device, parameters):
    """
    Each NFS deployment strategy uses these checks
    as a base
    """
    if 'to' not in parameters:
        return False
    if parameters['to'] != 'nfs':
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


class Nfs(Deployment):
    """
    Strategy class for a NFS deployment.
    Downloads rootfs and deploys to NFS server on dispatcher
    """

    compatibility = 1

    def __init__(self, parent, parameters):
        super(Nfs, self).__init__(parent)
        self.action = NfsAction()
        self.action.section = self.action_type
        self.action.job = self.job
        parent.add_action(self.action, parameters)

    @classmethod
    def accepts(cls, device, parameters):
        if not nfs_accept(device, parameters):
            return False
        if 'nfs' in device['actions']['deploy']['methods']:
            return True
        return False


class NfsAction(DeployAction):  # pylint:disable=too-many-instance-attributes

    def __init__(self):
        super(NfsAction, self).__init__()
        self.name = "nfs-deploy"
        self.description = "deploy nfsrootfs"
        self.summary = "NFS deployment"
        self.download_dir = DISPATCHER_DOWNLOAD_DIR
        try:
            self.download_dir = mkdtemp(basedir=DISPATCHER_DOWNLOAD_DIR)
        except OSError:
            # allows for unit tests to operate as normal user.
            self.suffix = '/'

    def validate(self):
        super(NfsAction, self).validate()
        if not self.valid:
            return
        if 'nfsrootfs' in self.parameters and 'nfs_url' in self.parameters:
            self.errors = "Only one of nfsrootfs or nfs_url can be specified"
        lava_test_results_dir = self.parameters['deployment_data']['lava_test_results_dir']
        self.data['lava_test_results_dir'] = lava_test_results_dir % self.job.job_id

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        if 'nfsrootfs' in parameters:
            download = DownloaderAction('nfsrootfs', path=self.download_dir)
            download.max_retries = 3
            self.internal_pipeline.add_action(download)
        if 'modules' in parameters:
            download = DownloaderAction('modules', path=self.download_dir)
            download.max_retries = 3
            self.internal_pipeline.add_action(download)
        # NfsAction is a deployment, so once the nfsrootfs has been deployed, just do the overlay
        self.internal_pipeline.add_action(ExtractNfsRootfs())
        self.internal_pipeline.add_action(OverlayAction())
        self.internal_pipeline.add_action(ExtractModules())
        self.internal_pipeline.add_action(ApplyOverlayTftp())
        self.internal_pipeline.add_action(DeployDeviceEnvironment())
