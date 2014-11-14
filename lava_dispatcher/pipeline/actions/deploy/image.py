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

from lava_dispatcher.pipeline.action import Deployment, Pipeline
from lava_dispatcher.pipeline.actions.deploy import DeployAction
from lava_dispatcher.pipeline.actions.deploy.download import (
    ChecksumAction,
    DownloaderAction,
    QCowConversionAction,
)
from lava_dispatcher.pipeline.actions.deploy.mount import (
    MountAction,
    UnmountAction,
)
from lava_dispatcher.pipeline.actions.deploy.apply_overlay import ApplyOverlayImage
from lava_dispatcher.pipeline.actions.deploy.overlay import (
    CustomisationAction,
    OverlayAction,
)


class DeployImageAction(DeployAction):

    def __init__(self):
        super(DeployImageAction, self).__init__()
        self.name = 'deployimage'
        self.description = "deploy image using loopback mounts"
        self.summary = "deploy image"

    def validate(self):
        # Nothing to do at this stage. Everything is done by internal actions
        super(DeployImageAction, self).validate()

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        download = DownloaderAction('image')
        download.max_retries = 3  # overridden by failure_retry in the parameters, if set.
        self.internal_pipeline.add_action(download)
        if parameters.get('format', '') == 'qcow2':
            self.internal_pipeline.add_action(QCowConversionAction('image'))
        self.internal_pipeline.add_action(ChecksumAction())
        self.internal_pipeline.add_action(MountAction())
        self.internal_pipeline.add_action(CustomisationAction())
        self.internal_pipeline.add_action(OverlayAction())  # idempotent, includes testdef
        self.internal_pipeline.add_action(ApplyOverlayImage())  # specific to image deployments
        self.internal_pipeline.add_action(UnmountAction())


# FIXME: may need to be renamed if it can only deal with KVM image deployment
class DeployImage(Deployment):
    """
    Strategy class for an Image based Deployment.
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

    def __init__(self, parent, parameters):
        super(DeployImage, self).__init__(parent)
        self.action = DeployImageAction()
        self.action.job = self.job
        parent.add_action(self.action, parameters)

    @classmethod
    def accepts(cls, device, parameters):
        """
        As a classmethod, this cannot set data
        in the instance of the class.
        This is *not* the same as validation of the action
        which can use instance data.
        """
        # FIXME: the device object has the device_types/*.conf - match against the job & support methods
        if hasattr(device, 'config'):
            if device.config.device_type != 'kvm':
                return False
        else:
            if device.parameters['device_type'] != 'kvm':
                return False
        # lookup if the job parameters match the available device methods
        if 'image' not in parameters:
            # python3 compatible
            print("Parameters %s have not been implemented yet." % parameters.keys())  # pylint: disable=superfluous-parens
            return False
        return True
