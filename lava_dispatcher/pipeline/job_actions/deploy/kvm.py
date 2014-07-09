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

import requests
from contextlib import contextmanager
from lava_dispatcher.pipeline.action import Deployment
from lava_dispatcher.pipeline import Pipeline, Action, JobError
from lava_dispatcher.pipeline.job_actions.deploy.download import (
    DownloaderAction,
    ChecksumAction,
)
from lava_dispatcher.pipeline.job_actions.deploy.overlay import (
    MountAction,
    CustomisationAction,
    UnmountAction,
)
from lava_dispatcher.pipeline.job_actions.deploy.testdef import TestDefinitionAction


class DeployAction(Action):
    """
    Base class for all actions which deploy files
    to media on a device under test.
    The subclass selected to do the work will be the
    subclass returning True in the accepts(device, image)
    function.
    Each new subclass needs a unit test to ensure it is
    reliably selected for the correct deployment and not
    selected for an invalid deployment or a deployment
    accepted by a different subclass.
    """

    name = 'deploy'


class DeployKVMAction(DeployAction):

    def __init__(self):
        super(DeployKVMAction, self).__init__()
        self.name = 'deploykvm'
        self.description = "deploy kvm top level action"
        self.summary = "deploy kvm"

    def prepare(self):
        # mktemp dir
        r = requests.head(self.parameters['image'])  # just check the headers, do not download.
        if r.status_code != requests.codes.ok:
            # FIXME: this needs to use pipeline error handling
            return False
        return True

    def run(self, connection, args=None):
        connection = super(DeployKVMAction, self).run(connection, args)
        self.pipeline.run_actions(connection, args)

    def cleanup(self):
        # rm temp dir
        super(DeployKVMAction, self).cleanup()


class DeployKVM(Deployment):
    """
    Accepts parameters to deploy a KVM
    Uses existing Actions to download and checksum
    as well as copying test files.
    Does not boot the device.
    Prepares the following actions and pipelines:
        retry_pipeline
            download_action
        report_checksum_action
        mount_pipeline
            customisation_action
            test_definitions_action
        umount action
    """

    def __init__(self, parent):
        super(DeployKVM, self).__init__(parent)
        self.action = DeployKVMAction()
        self.action.job = self.job
        parent.add_action(self.action)

        internal_pipeline = Pipeline(self.action)
        internal_pipeline.add_action(DownloaderAction())
        internal_pipeline.add_action(ChecksumAction())
        internal_pipeline.add_action(MountAction())  # FIXME: RetryAction
        internal_pipeline.add_action(CustomisationAction())
        internal_pipeline.add_action(TestDefinitionAction())  # FIXME: validate needs to check if needed
        internal_pipeline.add_action(UnmountAction())  # FIXME: RetryAction with sleep

    @contextmanager
    def deploy(self):
        """
        As a Deployment Strategy, this simply selects the
        correct deploy action and allows it to be added to the
        default Pipeline.
        """
        if not self.check_image_url():
            # FIXME: this needs to use pipeline error handling
            raise JobError

    @classmethod
    def accepts(cls, device, parameters):
        """
        As a classmethod, this cannot set data
        in the instance of the class.
        This is *not* the same as validation of the action
        which can use instance data.
        """
        if device.config.device_type != 'kvm':
            return False
        # FIXME: only enable once all deployment strategies in basics.yaml are defined!
#        if 'image' not in parameters:
#            print parameters
#            return False
        return True
