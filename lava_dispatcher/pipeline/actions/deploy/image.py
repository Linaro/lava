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

import os
from lava_dispatcher.pipeline.action import Pipeline, InfrastructureError, Action
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
from lava_dispatcher.pipeline.actions.deploy.apply_overlay import ApplyOverlayTftp
from lava_dispatcher.pipeline.utils.compression import untar_file

# pylint: disable=too-many-instance-attributes


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
            self.set_namespace_data(action=self.name, label='image', key='uefi_dir', value=uefi_path, parameters=parameters)
            # alternatively use the -bios option and standard image args
        for image in parameters['images'].keys():
            if image != 'yaml_line':
                download = DownloaderAction(image, path)
                download.max_retries = 3  # overridden by failure_retry in the parameters, if set.
                self.internal_pipeline.add_action(download)
                if parameters['images'][image].get('format', '') == 'qcow2':
                    self.internal_pipeline.add_action(QCowConversionAction(image))
        if self.test_needs_overlay(parameters):
            self.internal_pipeline.add_action(CustomisationAction())
            self.internal_pipeline.add_action(OverlayAction())  # idempotent, includes testdef
            self.internal_pipeline.add_action(ApplyOverlayGuest())
        if self.test_needs_deployment(parameters):
            self.internal_pipeline.add_action(DeployDeviceEnvironment())


class DeployQemuNfs(Deployment):
    """
    Strategy class for a kernel & NFS QEMU deployment.
    Does not use GuestFS, adds overlay to the NFS
    """
    compatibility = 5

    def __init__(self, parent, parameters):
        super(DeployQemuNfs, self).__init__(parent)
        self.action = DeployQemuNfsAction()
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
        if 'nfs' not in device['actions']['deploy']['methods']:
            return False
        if parameters['to'] != 'nfs':
            return False
        if 'qemu-nfs' not in device['actions']['boot']['methods']:
            return False
        if 'type' in parameters:
            if parameters['type'] != 'monitor':
                return False
        return True


class DeployQemuNfsAction(DeployAction):

    def __init__(self):
        super(DeployQemuNfsAction, self).__init__()
        self.name = 'deploy-qemu-nfs'
        self.description = "deploy qemu with NFS"
        self.summary = "deploy NFS for QEMU"

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        path = self.mkdtemp()
        if 'uefi' in parameters:
            uefi_path = self.mkdtemp()
            download = DownloaderAction('uefi', uefi_path)
            download.max_retries = 3
            self.internal_pipeline.add_action(download)
            # uefi option of QEMU needs a directory, not the filename
            self.set_namespace_data(action=self.name, label='image', key='uefi_dir', value=uefi_path, parameters=parameters)
            # alternatively use the -bios option and standard image args
        for image in parameters['images'].keys():
            if image != 'yaml_line':
                download = DownloaderAction(image, path)
                download.max_retries = 3  # overridden by failure_retry in the parameters, if set.
                self.internal_pipeline.add_action(download)
                if parameters['images'][image].get('format', '') == 'qcow2':
                    self.internal_pipeline.add_action(QCowConversionAction(image))
        self.internal_pipeline.add_action(ExtractNfsAction())
        self.internal_pipeline.add_action(OverlayAction())
        self.internal_pipeline.add_action(ApplyOverlayTftp())
        self.internal_pipeline.add_action(DeployDeviceEnvironment())


class ExtractNfsAction(Action):

    def __init__(self):
        super(ExtractNfsAction, self).__init__()
        self.name = "qemu-nfs-deploy"
        self.description = "deploy nfsrootfs for QEMU"
        self.summary = "NFS deployment for QEMU"
        self.param_key = 'nfsrootfs'
        self.file_key = "nfsroot"
        self.extra_compression = ['xz']
        self.use_tarfile = True
        self.use_lzma = False

    def validate(self):
        super(ExtractNfsAction, self).validate()
        if not self.valid:
            return
        lava_test_results_dir = self.parameters['deployment_data']['lava_test_results_dir']
        lava_test_results_dir = lava_test_results_dir % self.job.job_id
        self.set_namespace_data(action='test', label='results', key='lava_test_results_dir', value=lava_test_results_dir)
        if not self.parameters['images'].get(self.param_key, None):  # idempotency
            return
        if not self.get_namespace_data(
                action='download_action', label=self.param_key, key='file'):
            self.errors = "no file specified extract as %s" % self.param_key
        if not os.path.exists('/usr/sbin/exportfs'):
            raise InfrastructureError("NFS job requested but nfs-kernel-server not installed.")
        if 'prefix' in self.parameters['images'][self.param_key]:
            prefix = self.parameters['images'][self.param_key]['prefix']
            if prefix.startswith('/'):
                self.errors = 'prefix must not be an absolute path'
            if not prefix.endswith('/'):
                self.errors = 'prefix must be a directory and end with /'

    def run(self, connection, max_end_time, args=None):
        if not self.parameters['images'].get(self.param_key, None):  # idempotency
            return connection
        connection = super(ExtractNfsAction, self).run(connection, max_end_time, args)
        root = self.get_namespace_data(action='download_action', label=self.param_key, key='file')
        root_dir = self.mkdtemp()
        untar_file(root, root_dir)
        self.set_namespace_data(action='extract-rootfs', label='file', key=self.file_key, value=root_dir)
        self.logger.debug("Extracted %s to %s", self.file_key, root_dir)

        if 'prefix' in self.parameters['images'][self.param_key]:
            prefix = self.parameters['images'][self.param_key]['prefix']
            self.logger.warning("Adding '%s' prefix, any other content will not be visible.",
                                prefix)

            # Grab the path already defined in super().run() and add the prefix
            root_dir = self.get_namespace_data(
                action='extract-rootfs',
                label='file',
                key=self.file_key
            )
            root_dir = os.path.join(root_dir, prefix)
            # sets the directory into which the overlay is unpacked and which
            # is used in the substitutions into the bootloader command string.
            self.set_namespace_data(action='extract-rootfs', label='file', key=self.file_key, value=root_dir)
        return connection


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
        if 'image' not in device['actions']['deploy']['methods']:
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
            if parameters['type'] != 'monitor':
                return False
        return True
