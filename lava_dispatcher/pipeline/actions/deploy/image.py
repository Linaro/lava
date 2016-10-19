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

from lava_dispatcher.pipeline.action import Pipeline
from lava_dispatcher.pipeline.logical import Deployment
from lava_dispatcher.pipeline.actions.deploy import DeployAction
from lava_dispatcher.pipeline.actions.deploy.download import (
    DownloaderAction,
    QCowConversionAction,
)
from lava_dispatcher.pipeline.actions.deploy.apply_overlay import ApplyOverlayGuest
from lava_dispatcher.pipeline.actions.deploy.environment import DeployDeviceEnvironment
from lava_dispatcher.pipeline.actions.deploy.overlay import (
    CustomisationAction,
    OverlayAction,
)


class DeployImagesAction(DeployAction):  # FIXME: Rename to DeployPosixImages

    def __init__(self):
        super(DeployImagesAction, self).__init__()
        self.name = 'deployimages'
        self.description = "deploy images using guestfs"
        self.summary = "deploy images"

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        path = self.mkdtemp()
        if 'uefi' in parameters:
            uefi_path = self.mkdtemp()
            download = DownloaderAction('uefi', uefi_path)
            download.max_retries = 3
            self.internal_pipeline.add_action(download)
            # uefi option of QEMU needs a directory, not the filename
            self.set_common_data('image', 'uefi_dir', uefi_path)  # just the path, not the filename
            # alternatively use the -bios option and standard image args
        for image in parameters['images'].keys():
            if image != 'yaml_line':
                download = DownloaderAction(image, path)
                download.max_retries = 3  # overridden by failure_retry in the parameters, if set.
                self.internal_pipeline.add_action(download)
                if parameters['images'][image].get('format', '') == 'qcow2':
                    self.internal_pipeline.add_action(QCowConversionAction(image))
        self.internal_pipeline.add_action(CustomisationAction())
        self.internal_pipeline.add_action(OverlayAction())  # idempotent, includes testdef
        self.internal_pipeline.add_action(ApplyOverlayGuest())
        self.internal_pipeline.add_action(DeployDeviceEnvironment())


class DeployMonitoredAction(DeployAction):

    def __init__(self):
        super(DeployMonitoredAction, self).__init__()
        self.name = 'deploy-monitor'
        self.description = "deploy images without POSIX"
        self.summary = "deploy without requiring POSIX"

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        path = self.mkdtemp()
        for image in parameters['images'].keys():
            if image != 'yaml_line':
                download = DownloaderAction(image, path)
                download.max_retries = 3  # overridden by failure_retry in the parameters, if set.
                self.internal_pipeline.add_action(download)


class DeployMonitoredQEMU(Deployment):
    """
    Strategy class for a QEMU deployment not using
    the POSIX Lava Test Shell overlays.
    """
    compatibility = 4

    def __init__(self, parent, parameters):
        super(DeployMonitoredQEMU, self).__init__(parent)
        self.action = DeployMonitoredAction()
        self.action.section = self.action_type
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
        if device['device_type'] != 'qemu':
            return False
        if parameters['to'] != 'tmpfs':
            return False
        # lookup if the job parameters match the available device methods
        if 'images' not in parameters:
            # python3 compatible
            # FIXME: too broad
            print("Parameters %s have not been implemented yet." % list(parameters.keys()))  # pylint: disable=superfluous-parens
            return False
        if 'type' not in parameters.keys():
            return False
        return True


class DeployMonitoredPyOCD(Deployment):
    """
    Strategy class for a PyOCD deployment not using
    the POSIX Lava Test Shell overlays.
    """
    compatibility = 4

    def __init__(self, parent, parameters):
        super(DeployMonitoredPyOCD, self).__init__(parent)
        self.action = DeployMonitoredAction()
        self.action.section = self.action_type
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
        if device['device_type'] not in ['nrf52-nitrogen', 'nxp-k64f', '943907AEVAL1F']:
            return False
        if parameters['to'] != 'tmpfs':
            return False
        # lookup if the job parameters match the available device methods
        if 'images' not in parameters:
            # python3 compatible
            # FIXME: too broad
            print("Parameters %s have not been implemented yet." % list(parameters.keys()))  # pylint: disable=superfluous-parens
            return False
        if 'type' not in parameters.keys():
            return False
        return True


# FIXME: needs to be renamed to DeployPosixImages
class DeployImages(Deployment):
    """
    Strategy class for an Image based Deployment.
    Accepts parameters to deploy a QEMU
    Uses existing Actions to download and checksum
    as well as creating a qcow2 image for the test files.
    Does not boot the device.
    Requires guestfs instead of loopback support.
    Prepares the following actions and pipelines:
        retry_pipeline
            download_action
        report_checksum_action
        customisation_action
        test_definitions_action
    """
    compatibility = 4

    def __init__(self, parent, parameters):
        super(DeployImages, self).__init__(parent)
        self.action = DeployImagesAction()
        self.action.section = self.action_type
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
        if device['device_type'] != 'qemu':
            return False
        if parameters['to'] != 'tmpfs':
            return False
        # lookup if the job parameters match the available device methods
        if 'images' not in parameters:
            # python3 compatible
            # FIXME: too broad
            print("Parameters %s have not been implemented yet." % list(parameters.keys()))  # pylint: disable=superfluous-parens
            return False
        if 'type' in parameters:
            return False
        return True
