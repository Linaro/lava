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
from lava_dispatcher.pipeline import Pipeline
from lava_dispatcher.pipeline.actions.deploy import DeployAction
from lava_dispatcher.pipeline.actions.deploy.download import (
    DownloaderAction,
    ChecksumAction,
)
from lava_dispatcher.pipeline.actions.deploy.mount import (
    MountAction,
    UnmountAction,
)
from lava_dispatcher.pipeline.actions.deploy.overlay import (
    CustomisationAction,
    LMPOverlayAction,
    MultinodeOverlayAction,
    OverlayAction,
)
from lava_dispatcher.pipeline.actions.deploy.testdef import TestDefinitionAction


class DeployImageAction(DeployAction):

    def __init__(self):
        super(DeployImageAction, self).__init__()
        self.name = 'deployimage'
        self.description = "deploy image using loopback mounts"
        self.summary = "deploy image"

    def prepare(self):
        # FIXME: move to validate or into DownloadAction?
        # mktemp dir
        req = requests.head(self.parameters['image'])  # just check the headers, do not download.
        if req.status_code != req.codes.ok:
            # FIXME: this needs to use pipeline error handling
            return False
        return True

    def validate(self):
        self.pipeline.validate_actions()

    def populate(self):
        self.internal_pipeline = Pipeline(parent=self, job=self.job)
        download = DownloaderAction()
        download.max_retries = 3  # overridden by failure_retry in the parameters, if set.
        self.internal_pipeline.add_action(download)
        self.internal_pipeline.add_action(ChecksumAction())
        self.internal_pipeline.add_action(MountAction())
        self.internal_pipeline.add_action(CustomisationAction())
        for action_params in self.job.parameters['actions']:
            if 'test' in action_params:
                # FIXME: does it matter if testdef_action runs before overlay?
                testdef_action = TestDefinitionAction()
                testdef_action.parameters = action_params
                self.internal_pipeline.add_action(testdef_action)
                if 'target_group' in self.job.parameters:
                    self.internal_pipeline.add_action(MultinodeOverlayAction())
                if 'lmp_module' in self.job.parameters:
                    self.internal_pipeline.add_action(LMPOverlayAction())
                self.internal_pipeline.add_action(OverlayAction())
        self.internal_pipeline.add_action(UnmountAction())

    def run(self, connection, args=None):
        print self.internal_pipeline.actions
        connection = self.internal_pipeline.run_actions(connection, args)
        return connection

    def cleanup(self):
        # rm temp dir
        # super(DeployImageAction, self).cleanup()
        pass


class DeployImage(Deployment):
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
        super(DeployImage, self).__init__(parent)
        self.action = DeployImageAction()
        self.action.job = self.job
        parent.add_action(self.action)

        # internal_pipeline = Pipeline(parent=self.action, job=self.job)

    @contextmanager
    def deploy(self):
        """
        As a Deployment Strategy, this simply selects the
        correct deploy action and allows it to be added to the
        default Pipeline.
        """
        pass
#        if not self.check_image_url():
#            # FIXME: this needs to use pipeline error handling
#            raise JobError

    @classmethod
    def accepts(cls, device, parameters):
        """
        As a classmethod, this cannot set data
        in the instance of the class.
        This is *not* the same as validation of the action
        which can use instance data.
        """
        # FIXME: read the device_types/*.conf and match against the job & support methods
        if hasattr(device, 'config'):
            if device.config.device_type != 'kvm':
                return False
        else:
            if device.parameters['device_type'] != 'kvm':
                return False
        # FIXME: only enable once all deployment strategies in basics.yaml are defined!
#        if 'image' not in parameters:
#            print parameters
#            return False
        return True

    def extract_results(self):
        pass
