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
    DD_PROMPTS,
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
        media = parameters.get('to', None)
        job_device = parameters.get('device', None)

        # Is the media supported?
        if media not in ['sata', 'sd', 'usb']:
            return False
        # Matching a method?
        if job_device is None:
            return False
        # "parameters.media" is not defined for every devices
        if 'parameters' not in device or 'media' not in device['parameters']:
            return False

        # Is the device allowing this method?
        if job_device not in device['parameters']['media'].get(media, {}):
            return False
        # Is the configuration correct?
        if 'uuid' in device['parameters']['media'][media].get(job_device, {}):
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
        self.dd_prompts = None
        self.dd_flags = None

    def validate(self):
        super(DDAction, self).validate()
        if 'device' not in self.parameters:
            self.errors = "missing device for deployment"
        if 'tool' not in self.parameters['download']:
            self.errors = "missing download tool for deployment"
        if 'options' not in self.parameters['download']:
            self.errors = "missing options for download tool"
        if 'prompt' not in self.parameters['download']:
            self.errors = "missing prompt for download tool"
        if not os.path.isabs(self.parameters['download']['tool']):
            self.errors = "download tool parameter needs to be an absolute path"

        if self.parameters['to'] not in self.job.device['parameters'].get('media', {}):
            self.errors = "media '%s' unavailable for this device" % self.parameters['to']

        # No need to go further if an error was already detected
        if not self.valid:
            return

        dd_params = self.parameters.get('dd', None)
        if dd_params:
            self.dd_prompts = self.parameters['dd'].get('prompts', DD_PROMPTS)
            self.dd_flags = self.parameters['dd'].get('flags', None)
        else:
            self.dd_prompts = DD_PROMPTS

        if not isinstance(self.dd_prompts, list):
            self.errors = "'dd prompts' should be a list"
        else:
            for msg in self.dd_prompts:
                if not msg:
                    self.errors = "items of 'dd prompts' cannot be empty"

        uuid_required = False
        self.boot_params = self.job.device['parameters']['media'][self.parameters['to']]
        uuid_required = self.boot_params.get('UUID-required', False)

        if uuid_required:  # FIXME unit test required
            if 'uuid' not in self.boot_params[self.parameters['device']]:
                self.errors = "A UUID is required for %s on %s" % (
                    self.parameters['device'], self.job.device.hostname)
            if 'root_part' in self.boot_params[self.parameters['device']]:
                self.errors = "'root_part' is not valid for %s as a UUID is required" % self.job.device.hostname
        if self.parameters['device'] in self.boot_params:
            self.set_namespace_data(
                action=self.name,
                label='u-boot',
                key='boot_part',
                value=self.boot_params[self.parameters['device']]['device_id']
            )

    def run(self, connection, max_end_time, args=None):  # pylint: disable=too-many-locals
        """
        Retrieve the decompressed image from the dispatcher by calling the tool specified
        by the test writer, from within the test image of the first deployment, using the
        device to write directly to the secondary media, without needing to cache on the device.
        """
        connection = super(DDAction, self).run(connection, max_end_time, args)
        d_file = self.get_namespace_data(action='download-action', label='image', key='file')
        if not d_file:
            self.logger.debug("Skipping %s - nothing downloaded")
            return connection
        decompressed_image = os.path.basename(d_file)
        try:
            device_path = os.path.realpath(
                "/dev/disk/by-id/%s" %
                self.boot_params[self.parameters['device']]['uuid'])
        except OSError:
            raise JobError("Unable to find disk by id %s" %
                           self.boot_params[self.parameters['device']]['uuid'])
        storage_suffix = self.get_namespace_data(action='storage-deploy', label='storage', key='suffix')
        if not storage_suffix:
            storage_suffix = ''
        suffix = "%s/%s" % ("tmp", storage_suffix)

        # As the test writer can use any tool we cannot predict where the
        # download URL will be positioned in the download command.
        # Providing the download URL as a substitution option gets round this
        ip_addr = dispatcher_ip(self.job.parameters['dispatcher'])
        download_url = "http://%s/%s/%s" % (
            ip_addr, suffix, decompressed_image
        )
        substitutions = {
            '{DOWNLOAD_URL}': download_url
        }
        download_options = substitute([self.parameters['download']['options']], substitutions)[0]
        download_cmd = "%s %s" % (
            self.parameters['download']['tool'], download_options
        )
        dd_cmd = "dd of='%s' bs=4M" % device_path  # busybox dd does not support other flags
        if self.dd_flags:
            dd_cmd = "%s %s" % (dd_cmd, self.dd_flags)

        # set prompt to download prompt to ensure that the secondary deployment has started
        prompt_string = connection.prompt_str
        connection.prompt_str = self.parameters['download']['prompt']
        self.logger.debug("Changing prompt to %s", connection.prompt_str)
        connection.sendline("%s | %s" % (download_cmd, dd_cmd))
        self.wait(connection)
        if not self.valid:
            self.logger.error(self.errors)

        # change prompt string to list of dd outputs
        connection.prompt_str = self.dd_prompts
        self.logger.debug("Changing prompt to %s", connection.prompt_str)
        self.wait(connection)

        # set prompt back once secondary deployment is complete
        connection.prompt_str = prompt_string
        self.logger.debug("Changing prompt to %s", connection.prompt_str)
        self.set_namespace_data(action='shared', label='shared', key='connection', value=connection)
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

        if self.test_needs_deployment(self.parameters):
            lava_test_results_dir = self.parameters['deployment_data']['lava_test_results_dir']
            self.set_namespace_data(action='test', label='results', key='lava_test_results_dir', value=lava_test_results_dir % self.job.job_id)

        self.set_namespace_data(action=self.name, label='u-boot', key='device', value=self.parameters['device'])
        suffix = os.path.join(*self.image_path.split('/')[-2:])
        suffix = os.path.join(suffix, "image")
        self.set_namespace_data(action=self.name, label='storage', key='suffix', value=suffix)

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
        if self.test_needs_overlay(parameters):
            self.internal_pipeline.add_action(OverlayAction())  # idempotent, includes testdef
        if 'image' in parameters:
            self.internal_pipeline.add_action(DownloaderAction('image', path=self.image_path))
            if self.test_needs_overlay(parameters):
                self.internal_pipeline.add_action(ApplyOverlayImage())
            self.internal_pipeline.add_action(DDAction())
        # FIXME: could support tarballs too
        if self.test_needs_deployment(parameters):
            self.internal_pipeline.add_action(DeployDeviceEnvironment())
