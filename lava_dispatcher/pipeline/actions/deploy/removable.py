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
from lava_dispatcher.pipeline.action import (
    Action,
    Pipeline,
    JobError,
    Timeout,
)
from lava_dispatcher.pipeline.logical import Deployment
from lava_dispatcher.pipeline.actions.deploy.download import DownloaderAction
from lava_dispatcher.pipeline.actions.deploy.overlay import (
    CustomisationAction,
    OverlayAction,
)
from lava_dispatcher.pipeline.actions.deploy.apply_overlay import (
    ApplyOverlayImage,
)
from lava_dispatcher.pipeline.actions.deploy import DeployAction
from lava_dispatcher.pipeline.actions.deploy.environment import DeployDeviceEnvironment
from lava_dispatcher.pipeline.utils.network import dispatcher_ip
from lava_dispatcher.pipeline.utils.strings import substitute
from lava_dispatcher.pipeline.utils.constants import (
    SECONDARY_DEPLOYMENT_MSG,
)


class Removable(Deployment):
    """
    Deploys an image to a usb or sata mass storage device
    *Destroys* anything on that device, including partition table
    Requires a preceding boot (e.g. ramdisk) which may have a test shell of it's own.
    Does not require the ramdisk to be able to mount the usb storage, just for the kernel
    to be able to see the device (the filesystem will be replaced anyway).

    SD card partitions will use a similar approach but the UUID will be fixed in the device
    configuration and specifying a restricted UUID will invalidate the job to protect the bootloader.

    """

    compatibility = 1

    def __init__(self, parent, parameters):
        super(Removable, self).__init__(parent)
        self.action = MassStorage()
        self.action.job = self.job
        self.action.section = self.action_type
        parent.add_action(self.action, parameters)

    @classmethod
    def accepts(cls, device, parameters):
        job_device = None
        media = None
        if 'to' in parameters:
            # connection support
            # Which deployment method to use?
            if parameters['to'] == 'usb':
                if 'device' in parameters:
                    job_device = parameters['device']
                    media = 'usb'
            if parameters['to'] == 'sata':
                if 'device' in parameters:
                    job_device = parameters['device']
                    media = 'sata'
        # Matching a method ?
        if job_device is None:
            return False
        # Is the device allowing this method ?
        if job_device not in device['parameters']['media'][media]:
            return False
        # TODO: what if the key does not exist for this device configuration?
        if 'uuid' in device['parameters']['media'][media][job_device]:
            return True
        return False


class DDAction(Action):
    """
    Runs dd against the realpath of the symlink provided by the static device information:
    device['parameters']['media'] (e.g. usb-SanDisk_Ultra_20060775320F43006019-0:0)
    in /dev/disk/by-id/ of the initial deployment, on device.
    """
    def __init__(self):
        super(DDAction, self).__init__()
        self.name = "dd-image"
        self.summary = "dd image to drive"
        self.description = "deploy image to drive"
        self.timeout = Timeout(self.name, 600)
        self.boot_params = None

    def validate(self):
        super(DDAction, self).validate()
        if 'device' not in self.parameters:
            self.errors = "missing device for deployment"
        if 'tool' not in self.parameters['download']:
            self.errors = "missing download tool for deployment"
        if 'options' not in self.parameters['download']:
            self.errors = "missing options for download tool"
        if not os.path.isabs(self.parameters['download']['tool']):
            self.errors = "download tool parameter needs to be an absolute path"
        uuid_required = False
        self.boot_params = self.job.device['parameters']['media'][self.parameters['to']]
        if 'media' in self.job.device:
            media_params = self.job.device['parameters']['media']
            interface_params = [
                interface for interface in media_params if interface == self.parameters['to']
            ]
            uuid_required = media_params[interface_params[0]]['UUID-required']
        if uuid_required:  # FIXME unit test required
            if 'uuid' not in self.boot_params[self.parameters['device']]:
                self.errors = "A UUID is required for %s on %s" % (
                    self.parameters['device'], self.job.device.hostname)
            if 'root_part' in self.boot_params[self.parameters['device']]:
                self.errors = "'root_part' is not valid for %s as a UUID is required" % self.job.device.hostname
        if self.parameters['device'] in self.boot_params:
            self.set_common_data(
                'u-boot',
                'boot_part',
                self.boot_params[self.parameters['device']]['device_id']
            )

    def run(self, connection, args=None):
        """
        Retrieve the decompressed image from the dispatcher by calling the tool specified
        by the test writer, from within the test image of the first deployment, using the
        device to write directly to the secondary media, without needing to cache on the device.
        """
        connection = super(DDAction, self).run(connection, args)
        if 'file' not in self.data['download_action']['image']:
            self.logger.debug("Skipping %s - nothing downloaded")
            return connection
        decompressed_image = os.path.basename(self.data['download_action']['image']['file'])
        try:
            device_path = os.path.realpath(
                "/dev/disk/by-id/%s" %
                self.boot_params[self.parameters['device']]['uuid'])
        except OSError:
            raise JobError("Unable to find disk by id %s" %
                           self.boot_params[self.parameters['device']]['uuid'])

        suffix = "%s/%s" % ("tmp", self.data['storage-deploy'].get('suffix', ''))

        # As the test writer can use any tool we cannot predict where the
        # download URL will be positioned in the download command.
        # Providing the download URL as a substitution option gets round this
        download_url = "http://%s/%s/%s" % (
            dispatcher_ip(), suffix, decompressed_image
        )
        substitutions = {
            '{DOWNLOAD_URL}': download_url
        }
        download_options = substitute([self.parameters['download']['options']], substitutions)[0]
        download_cmd = "%s %s" % (
            self.parameters['download']['tool'], download_options
        )

        dd_cmd = "dd of='%s' bs=4M" % device_path  # busybox dd does not support other flags

        # We must ensure that the secondary media deployment has completed before handing over
        # the connection.  Echoing the SECONDARY_DEPLOYMENT_MSG after the deployment means we
        # always have a constant string to match against
        prompt_string = connection.prompt_str
        connection.prompt_str = SECONDARY_DEPLOYMENT_MSG
        self.logger.debug("Changing prompt to %s", connection.prompt_str)
        connection.sendline("%s | %s ; echo %s" % (download_cmd, dd_cmd, SECONDARY_DEPLOYMENT_MSG))
        self.wait(connection)
        if not self.valid:
            self.logger.error(self.errors)

        # set prompt back
        connection.prompt_str = prompt_string
        self.logger.debug("Changing prompt to %s", connection.prompt_str)
        return connection


class MassStorage(DeployAction):  # pylint: disable=too-many-instance-attributes

    def __init__(self):
        super(MassStorage, self).__init__()
        self.name = "storage-deploy"
        self.description = "Deploy image to mass storage"
        self.summary = "write image to storage"
        self.suffix = None
        self.image_path = None

    def validate(self):
        super(MassStorage, self).validate()
        # if 'image' not in self.parameters.keys():
        #     self.errors = "%s needs an image to deploy" % self.name
        if 'device' not in self.parameters:
            self.errors = "No device specified for mass storage deployment"
        if not self.valid:
            return
        lava_test_results_dir = self.parameters['deployment_data']['lava_test_results_dir']
        self.data['lava_test_results_dir'] = lava_test_results_dir % self.job.job_id
        if 'device' in self.parameters:
            self.set_common_data('u-boot', 'device', self.parameters['device'])
        self.data[self.name].setdefault('suffix', os.path.basename(self.image_path))

    def populate(self, parameters):
        """
        The dispatcher does the first download as the first deployment is not guaranteed to
        have DNS resolution fully working, so we can use the IP address of the dispatcher
        to get it (with the advantage that the dispatcher decompresses it so that the ramdisk
        can pipe the raw image directly from wget to dd.
        This also allows the use of local file:// locations which are visible to the dispatcher
        but not the device.
        """
        self.image_path = self.mkdtemp()
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.internal_pipeline.add_action(CustomisationAction())
        self.internal_pipeline.add_action(OverlayAction())  # idempotent, includes testdef
        if 'image' in parameters:
            download = DownloaderAction('image', path=self.image_path)
            download.max_retries = 3
            self.internal_pipeline.add_action(download)
            self.internal_pipeline.add_action(ApplyOverlayImage())
            self.internal_pipeline.add_action(DDAction())
        # FIXME: could support tarballs too
        self.internal_pipeline.add_action(DeployDeviceEnvironment())
