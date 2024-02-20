# Copyright (C) 2015 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later


import os

from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.actions.deploy.apply_overlay import ExtractModules, ExtractRootfs
from lava_dispatcher.actions.deploy.download import DownloaderAction
from lava_dispatcher.actions.deploy.environment import DeployDeviceEnvironment
from lava_dispatcher.actions.deploy.overlay import OverlayAction
from lava_dispatcher.logical import Deployment
from lava_dispatcher.protocols.multinode import MultinodeProtocol

# Deploy SSH can mean a few options:
# for a primary connection, the device might need to be powered_on
# for a secondary connection, the device must be deployed
# In each case, files need to be copied to the device
# For primary: to: ssh is used to implicitly copy the authorization
# For secondary, authorize: ssh is needed as 'to' is already used.


class Ssh(Deployment):
    """
    Copies files to the target to support further actions,
    typically the overlay.
    """

    name = "ssh"

    @classmethod
    def action(cls):
        return ScpOverlay()

    @classmethod
    def accepts(cls, device, parameters):
        if "ssh" not in device["actions"]["deploy"]["methods"]:
            return False, '"ssh" is not in the device configuration deploy methods'
        if parameters["to"] != "ssh":
            return False, '"to" parameter is not "ssh"'
        return True, "accepted"


class ScpOverlay(Action):
    """
    Prepares the overlay and copies it to the target
    """

    name = "scp-overlay"
    description = "prepare overlay and scp to device"
    summary = "copy overlay to device"

    def __init__(self):
        super().__init__()
        self.items = []

    def validate(self):
        super().validate()
        self.items = ["firmware", "kernel", "dtb", "rootfs", "modules"]
        if not self.test_has_shell(self.parameters):
            self.errors = "Scp overlay needs a test action."
            return
        if "serial" not in self.job.device["actions"]["deploy"]["connections"]:
            self.errors = "Device not configured to support serial connection."

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        tar_flags = (
            parameters["deployment_data"]["tar_flags"]
            if "tar_flags" in parameters["deployment_data"].keys()
            else ""
        )
        self.set_namespace_data(
            action=self.name,
            label=self.name,
            key="tar_flags",
            value=tar_flags,
            parameters=parameters,
        )
        self.pipeline.add_action(OverlayAction())
        for item in self.items:
            if item in parameters:
                self.pipeline.add_action(
                    DownloaderAction(item, path=self.mkdtemp()), params=parameters[item]
                )
                self.set_namespace_data(
                    action=self.name,
                    label="scp",
                    key=item,
                    value=True,
                    parameters=parameters,
                )
        # we might not have anything to download, just the overlay to push
        self.pipeline.add_action(PrepareOverlayScp())
        # prepare the device environment settings in common data for enabling in the boot step
        self.pipeline.add_action(DeployDeviceEnvironment())


class PrepareOverlayScp(Action):
    """
    Copy the overlay to the device using scp and then unpack remotely.
    Needs the device to be ready for SSH connection.
    """

    name = "prepare-scp-overlay"
    description = "copy the overlay over an existing ssh connection"
    summary = "scp the overlay to the remote device"

    def __init__(self):
        super().__init__()
        self.host_keys = []

    def validate(self):
        super().validate()
        environment = self.get_namespace_data(
            action="deploy-device-env", label="environment", key="env_dict"
        )
        if not environment:
            environment = {}
        environment.update({"LC_ALL": "C.UTF-8", "LANG": "C"})
        self.set_namespace_data(
            action=self.name, label="environment", key="env_dict", value=environment
        )
        if "protocols" in self.parameters:
            # set run to call the protocol, retrieve the data and store.
            for params in self.parameters["protocols"][MultinodeProtocol.name]:
                if isinstance(params, str):
                    self.errors = (
                        "Invalid protocol action setting - needs to be a list."
                    )
                    continue
                if "action" not in params or params["action"] != self.name:
                    continue
                if "messageID" not in params:
                    self.errors = "Invalid protocol block: %s" % params
                    return
                if "message" not in params or not isinstance(params["message"], dict):
                    self.errors = "Missing message block for scp deployment"
                    return
                self.host_keys.append(params["messageID"])
        self.set_namespace_data(
            action=self.name, label=self.name, key="overlay", value=self.host_keys
        )

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.pipeline.add_action(
            ExtractRootfs()
        )  # idempotent, checks for nfsrootfs parameter
        self.pipeline.add_action(
            ExtractModules()
        )  # idempotent, checks for a modules parameter

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)
        overlay_file = self.get_namespace_data(
            action="compress-overlay", label="output", key="file"
        )
        self.logger.info("Preparing to copy: %s", os.path.basename(overlay_file))
        self.set_namespace_data(
            action=self.name, label="scp-deploy", key="overlay", value=overlay_file
        )
        for host_key in self.host_keys:
            data = self.get_namespace_data(
                action=MultinodeProtocol.name,
                label=MultinodeProtocol.name,
                key=host_key,
            )
            if not data:
                self.logger.warning("Missing data for host_key %s", host_key)
                continue
            for params in self.parameters["protocols"][MultinodeProtocol.name]:
                replacement_key = [key for key, _ in params["message"].items()][0]
                if replacement_key not in data:
                    self.logger.error(
                        "Mismatched replacement key %s and received data %s",
                        replacement_key,
                        list(data.keys()),
                    )
                    continue
                self.set_namespace_data(
                    action=self.name,
                    label=self.name,
                    key=host_key,
                    value=str(data[replacement_key]),
                )
                self.logger.info(
                    "data %s replacement key is %s",
                    host_key,
                    self.get_namespace_data(
                        action=MultinodeProtocol.name, label=self.name, key=host_key
                    ),
                )
        return connection
