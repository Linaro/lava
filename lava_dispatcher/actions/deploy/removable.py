# Copyright (C) 2014 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

# List just the subclasses supported for this base strategy
# imported by the parser to populate the list of subclasses.

import os

from lava_common.constants import DD_PROMPTS, DISPATCHER_DOWNLOAD_DIR
from lava_dispatcher.action import Action, JobError, Pipeline, Timeout
from lava_dispatcher.actions.deploy.apply_overlay import ApplyOverlayImage
from lava_dispatcher.actions.deploy.download import DownloaderAction
from lava_dispatcher.actions.deploy.environment import DeployDeviceEnvironment
from lava_dispatcher.actions.deploy.overlay import OverlayAction
from lava_dispatcher.logical import Deployment
from lava_dispatcher.utils.network import dispatcher_ip
from lava_dispatcher.utils.strings import substitute


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

    name = "removable"

    @classmethod
    def action(cls):
        return MassStorage()

    @classmethod
    def accepts(cls, device, parameters):
        media = parameters.get("to")
        job_device = parameters.get("device")

        # Is the media supported?
        if media not in ["sata", "sd", "usb"]:
            return False, '"media" was not "sata", "sd", or "usb"'
        # "parameters.media" is not defined for every devices
        if "parameters" not in device or "media" not in device["parameters"]:
            return (
                False,
                '"parameters" was not in the device or "media" was not in the parameters',
            )
        # Is the device allowing this method?
        if job_device not in device["parameters"]["media"].get(media, {}):
            return False, 'media was not in the device "media" parameters'
        # Is the configuration correct?
        if "uuid" in device["parameters"]["media"][media].get(job_device, {}):
            return True, "accepted"
        return (
            False,
            '"uuid" was not in the parameters for the media device %s' % job_device,
        )


class DDAction(Action):
    """
    Runs dd or a configurable writer against the realpath of the symlink
    provided by the static device information: device['parameters']['media']
    (e.g. usb-SanDisk_Ultra_20060775320F43006019-0:0) in /dev/disk/by-id/ of
    the initial deployment, on device.
    """

    name = "dd-image"
    description = "deploy image to drive"
    summary = "write image to drive"

    def __init__(self):
        super().__init__()
        self.timeout = Timeout(
            self.name, self, duration=600, exception=self.timeout_exception
        )
        self.boot_params = None
        self.tool_prompts = None
        self.tool_flags = None

    def validate(self):
        super().validate()
        if "device" not in self.parameters:
            self.errors = "missing device for deployment"

        download_params = self.parameters.get("download")
        writer_params = self.parameters.get("writer")
        if not download_params and not writer_params:
            self.errors = "Neither a download nor a write tool found in parameters"

        if download_params:
            if "tool" not in download_params:
                self.errors = "missing download or writer tool for deployment"
            if "options" not in download_params:
                self.errors = "missing options for download tool"
            if "prompt" not in download_params:
                self.errors = "missing prompt for download tool"
            if not os.path.isabs(download_params["tool"]):
                self.errors = "download tool parameter needs to be an absolute path"

        if writer_params:
            if "tool" not in writer_params:
                self.errors = "missing writer tool for deployment"
            if "options" not in writer_params:
                self.errors = "missing options for writer tool"
            if "download" not in self.parameters:
                if "prompt" not in writer_params:
                    self.errors = "missing prompt for writer tool"
            if not os.path.isabs(writer_params["tool"]):
                self.errors = "writer tool parameter needs to be an absolute path"

        if self.parameters["to"] not in self.job.device["parameters"].get("media", {}):
            self.errors = (
                "media '%s' unavailable for this device" % self.parameters["to"]
            )

        # The `image' parameter can be either directly in the Action parameters
        # if there is a single image file, or within `images' if there are
        # multiple image files.  In either case, there needs to be one `image'
        # parameter.
        img_params = self.parameters.get("images", self.parameters)
        if "image" not in img_params:
            self.errors = "Missing image parameter"

        # No need to go further if an error was already detected
        if not self.valid:
            return

        tool_params = self.parameters.get("tool")
        if tool_params:
            self.tool_prompts = tool_params.get("prompts", DD_PROMPTS)
            self.tool_flags = tool_params.get("flags")
        else:
            self.tool_prompts = DD_PROMPTS

        if not isinstance(self.tool_prompts, list):
            self.errors = "'tool prompts' should be a list"
        else:
            for msg in self.tool_prompts:
                if not msg:
                    self.errors = "items of 'tool prompts' cannot be empty"

        self.boot_params = self.job.device["parameters"]["media"][self.parameters["to"]]
        uuid_required = self.boot_params.get("UUID-required", False)

        if uuid_required:  # FIXME unit test required
            if "uuid" not in self.boot_params[self.parameters["device"]]:
                self.errors = "A UUID is required for %s" % (self.parameters["device"])
            if "root_part" in self.boot_params[self.parameters["device"]]:
                self.errors = "'root_part' is not valid as a UUID is required"
        if self.parameters["device"] in self.boot_params:
            self.set_namespace_data(
                action=self.name,
                label="u-boot",
                key="boot_part",
                value=self.boot_params[self.parameters["device"]]["device_id"],
            )

    def run(self, connection, max_end_time):
        """
        Retrieve the decompressed image from the dispatcher by calling the tool specified
        by the test writer, from within the test image of the first deployment, using the
        device to write directly to the secondary media, without needing to cache on the device.
        """
        connection = super().run(connection, max_end_time)
        d_file = self.get_namespace_data(
            action="download-action", label="image", key="file"
        )
        if not d_file:
            self.logger.debug("Skipping %s - nothing downloaded")
            return connection
        decompressed_image = os.path.basename(d_file)
        try:
            device_path = os.path.realpath(
                "/dev/disk/by-id/%s"
                % self.boot_params[self.parameters["device"]]["uuid"]
            )
        except OSError:
            raise JobError(
                "Unable to find disk by id %s"
                % self.boot_params[self.parameters["device"]]["uuid"]
            )

        # As the test writer can use any tool we cannot predict where the
        # download URL will be positioned in the download command.
        # Providing the download URL as a substitution option gets round this
        ip_addr = dispatcher_ip(self.job.parameters["dispatcher"], "http")
        path = d_file[len(DISPATCHER_DOWNLOAD_DIR) + 1 :]
        download_url = "http://%s/tmp/%s" % (ip_addr, path)
        substitutions = {"{DOWNLOAD_URL}": download_url, "{DEVICE}": device_path}

        download_cmd = None
        download_params = self.parameters.get("download")
        if download_params:
            download_options = substitute([download_params["options"]], substitutions)[
                0
            ]
            download_cmd = " ".join([download_params["tool"], download_options])

        writer_params = self.parameters.get("writer")
        if writer_params:
            tool_options = substitute([writer_params["options"]], substitutions)[0]
            tool_cmd = [writer_params["tool"], tool_options]
        else:
            tool_cmd = [
                f"dd of='{device_path}' bs=4M"
            ]  # busybox dd does not support other flags
        if self.tool_flags:
            tool_cmd.append(self.tool_flags)
        cmd = " ".join(tool_cmd)

        cmd_line = " ".join([download_cmd, "|", cmd]) if download_cmd else cmd

        # set prompt to either `download' or `writer' prompt to ensure that the
        # secondary deployment has started
        prompt_string = connection.prompt_str
        prompt_param = download_params or writer_params
        connection.prompt_str = prompt_param["prompt"]
        self.logger.debug("Changing prompt to %s", connection.prompt_str)

        connection.sendline(cmd_line)
        self.wait(connection)
        if not self.valid:
            self.logger.error(self.errors)

        # change prompt string to list of dd outputs
        connection.prompt_str = self.tool_prompts
        self.logger.debug("Changing prompt to %s", connection.prompt_str)
        self.wait(connection)

        # set prompt back once secondary deployment is complete
        connection.prompt_str = prompt_string
        self.logger.debug("Changing prompt to %s", connection.prompt_str)
        self.set_namespace_data(
            action="shared", label="shared", key="connection", value=connection
        )
        return connection


class MassStorage(Action):
    name = "storage-deploy"
    description = "Deploy image to mass storage"
    summary = "write image to storage"

    def __init__(self):
        super().__init__()
        self.suffix = None
        self.image_path = None

    def validate(self):
        super().validate()
        # if 'image' not in self.parameters.keys():
        #     self.errors = "%s needs an image to deploy" % self.name
        if "device" not in self.parameters:
            self.errors = "No device specified for mass storage deployment"
        if not self.valid:
            return

        self.set_namespace_data(
            action=self.name,
            label="u-boot",
            key="device",
            value=self.parameters["device"],
        )

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
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        if self.test_needs_overlay(parameters):
            self.pipeline.add_action(OverlayAction())  # idempotent, includes testdef
        uniquify = parameters.get("uniquify", True)
        if "images" in parameters:
            for k in sorted(parameters["images"].keys()):
                self.pipeline.add_action(
                    DownloaderAction(
                        k,
                        path=self.image_path,
                        uniquify=uniquify,
                        params=parameters["images"][k],
                    )
                )
                if parameters["images"][k].get("apply-overlay", False):
                    if self.test_needs_overlay(parameters):
                        self.pipeline.add_action(ApplyOverlayImage())
            self.pipeline.add_action(DDAction())
        elif "image" in parameters:
            self.pipeline.add_action(
                DownloaderAction(
                    "image",
                    path=self.image_path,
                    uniquify=uniquify,
                    params=parameters["image"],
                )
            )
            if self.test_needs_overlay(parameters):
                self.pipeline.add_action(ApplyOverlayImage())
            self.pipeline.add_action(DDAction())

        # FIXME: could support tarballs too
        if self.test_needs_deployment(parameters):
            self.pipeline.add_action(DeployDeviceEnvironment())
