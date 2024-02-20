# Copyright (C) 2023 Linaro
#
# Author: Stevan Radaković <stevan.radakovic@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import glob
import os
import subprocess
import time

import requests

from lava_common.constants import DISPATCHER_DOWNLOAD_DIR
from lava_common.exceptions import JobError
from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.actions.boot import AutoLoginAction, BootHasMixin, OverlayUnpack
from lava_dispatcher.logical import Boot, RetryAction
from lava_dispatcher.power import ResetDevice
from lava_dispatcher.utils.docker import DockerRun

LAVA_NODEBOOTER_PATH = "/home/lava/downloads"
NODEBOOTER_HOME = "/data/nodebooter/"
NIC_NO_OF_SUPPORTED = 4


class BootNodebooter(Boot):
    @classmethod
    def action(cls):
        return BootNodebooterAction()

    @classmethod
    def accepts(cls, device, parameters):
        if "nodebooter" not in device["actions"]["boot"]["methods"]:
            return (
                False,
                '"nodebooter" was not in the device configuration boot methods',
            )
        if parameters["method"] != "nodebooter":
            return False, '"method" was not "nodebooter"'
        return True, "accepted"


class BootNodebooterAction(BootHasMixin, RetryAction):
    name = "boot-nodebooter"
    description = "boot nodebooter"
    summary = "boot nodebooter"

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        # TODO: auth with GAR and get image:
        # self.pipeline.add_action(GetNodebooterImage())
        self.pipeline.add_action(RunNodebooterContainer())
        self.pipeline.add_action(ConfigureNodebooter())

        self.pipeline.add_action(ResetDevice())
        if self.has_prompts(parameters):
            self.pipeline.add_action(AutoLoginAction())
        if "transfer_overlay" in parameters:
            self.pipeline.add_action(OverlayUnpack())


class RunNodebooterContainer(Action):
    name = "run-nodebooter-container"
    description = "run nodebooter container based on image"
    summary = "run nodebooter container"

    def __init__(self):
        super().__init__()
        self.dut_iface = None
        self.dut_mac = None
        self.container = ""
        self.cleanup_required = False

    def validate(self):
        super().validate()
        self.container = "nodebooter"

        if "docker" not in self.parameters:
            self.errors = "Specify docker parameter"
            raise JobError("Not specified 'docker' in parameters")

        if "environment" in self.job.device:
            if not isinstance(self.job.device["environment"], dict):
                self.errors("Incorrect environment format in device configuration")
            if "DUT_MAC" in self.job.device["environment"]:
                self.dut_mac = self.job.device["environment"]["DUT_MAC"]
            if "DUT_IFACE" in self.job.device["environment"]:
                self.dut_iface = self.job.device["environment"]["DUT_IFACE"]
        else:
            self.errors = "Missing 'environment' variable in the device configuration"

        if self.dut_mac is None:
            self.errors = (
                "Missing DUT_MAC parameter in the device config 'environment' variable"
            )
        if self.dut_iface is None:
            self.errors = "Missing DUT_IFACE parameter in the device config 'environment' variable"

    def run(self, connection, max_end_time):
        volumes = {
            f"{NODEBOOTER_HOME}docker_mount": "/home/shared",
            f"{NODEBOOTER_HOME}tftpboot": "/var/lib/tftpboot",
            f"{NODEBOOTER_HOME}dhcpd/etc/dhcp": "/etc/dhcp",
            f"{NODEBOOTER_HOME}dhcpd/var/lib/dhcp": "/var/lib/dhcp",
            f"{NODEBOOTER_HOME}dhcpd/var/db": "/var/db",
            f"{NODEBOOTER_HOME}logs": "/var/log",
            f"{NODEBOOTER_HOME}docker_shm": "/dev/shm",
            f"{NODEBOOTER_HOME}ovss": "/opt/ovss",
            f"{NODEBOOTER_HOME}custom_configs": "/home/custom_configs",
            DISPATCHER_DOWNLOAD_DIR: LAVA_NODEBOOTER_PATH,
            "/sys/fs/cgroup": "/sys/fs/cgroup",
        }
        init_exec = "/usr/sbin/init"

        # TODO: ipv4 and ipv6 addresses currently hardcoded in nodebooter
        config_dict = {
            "DUT_IFACE": self.dut_iface,
            "IPV4_ADDR": "192.168.1.1/24",
            "IPV6_ADDR": "2001:db8:1::/56",
        }

        os.makedirs(f"{NODEBOOTER_HOME}custom_configs", exist_ok=True)
        with open(f"{NODEBOOTER_HOME}custom_configs/config", "w") as f:
            for key, value in config_dict.items():
                f.write(f"{key}={value}\n")

        docker = DockerRun.from_parameters(self.parameters["docker"], self.job)
        docker.network = "host"

        for vol, mnt in volumes.items():
            os.makedirs(vol, exist_ok=True)
            option = "--volume=%s:%s" % (vol, mnt)
            docker.add_docker_run_options(option)

        docker.add_docker_run_options("--privileged")
        docker.add_docker_run_options("--rm")
        docker.add_docker_run_options("-it")
        docker.add_docker_run_options("-d")
        docker.add_docker_run_options("--network=host")
        self.logger.info(docker.cmdline())
        docker.local(True)
        docker.name(self.container)
        docker.init(False)

        try:
            docker.run(init_exec)
        except subprocess.CalledProcessError as exc:
            raise JobError(f"docker run command exited: {exc}")

        self.set_namespace_data(
            action="shared",
            label="shared",
            key="nodebooter_container",
            value=self.container,
        )


class ConfigureNodebooter(Action):
    name = "configure-nodebooter"
    description = "update nodebooter settings and add dut via API"
    summary = "configure nodebooter"

    def __init__(self):
        super().__init__()
        # Validated in previous
        self.dut_mac = None

    def validate(self):
        # We assume the nodebooter container is running, otherwise previous
        # action in the pipeline would have failed.
        # All the device config validation is done before nodebooter start in RunNodebooterAction.
        super().validate()
        if "environment" in self.job.device:
            if not isinstance(self.job.device["environment"], dict):
                self.errors("Incorrect environment format in device configuration")
            if "DUT_MAC" in self.job.device["environment"]:
                self.dut_mac = self.job.device["environment"]["DUT_MAC"]
        else:
            self.errors = "Missing 'environment' variable in the device configuration"

        if self.dut_mac is None:
            self.errors = (
                "Missing DUT_MAC parameter in the device config 'environment' variable"
            )

        # Validate that the nic setup is present in the boot action if nic images are available in download action
        for counter in range(NIC_NO_OF_SUPPORTED):
            image_file_path = self.get_namespace_data(
                "download-action", label=f"nic{counter}", key="file"
            )
            if image_file_path:
                if f"NIC{counter}_MAC" not in self.job.device["environment"]:
                    self.errors = f"Missing nic{counter} MAC address (NIC{counter}_MAC) from 'environment' variable"

    def run(self, connection, max_end_time):
        # Make sure nodebooter container is stopped at the end.
        self.cleanup_required = True

        # Certain daemons require restart after the container is up.
        services_restart_required = ["setup_networks", "naas", "nodebooter"]
        for service in services_restart_required:
            try:
                subprocess.check_output(  # nosec - internal.
                    [
                        "docker",
                        "exec",
                        "-d",
                        "nodebooter",
                        "systemctl",
                        "restart",
                        service,
                    ],
                    stderr=subprocess.STDOUT,
                )
            except subprocess.CalledProcessError as exc:
                self.errors = str(exc)

        # Add DUT to Nodebooter via API (on localhost)
        url = "http://localhost:12901/nodebooter/api/v2/machines/"

        # Check that the nodebooter is online and receiving API calls
        self.logger.debug("Probing nodebooter API availability via %s", url)
        while True:
            try:
                res = requests.get(url)
                if res.status_code in (200, 302):
                    break
            except requests.exceptions.ConnectionError:
                pass
            time.sleep(1)
        self.logger.debug("Nodebooter API available at: %s", url)

        # Use API to add the machine to nodebooter with preconfigured data.
        try:
            res = None
            headers = {"Content-Type": "application/json"}
            boot_image = self.get_namespace_data(
                "download-action", label="boot", key="file"
            ).replace(DISPATCHER_DOWNLOAD_DIR, LAVA_NODEBOOTER_PATH)
            nic_images = []
            for counter in range(NIC_NO_OF_SUPPORTED):
                image_file_path = self.get_namespace_data(
                    "download-action", label=f"nic{counter}", key="file"
                )
                if image_file_path:
                    nic_images.append(
                        image_file_path.replace(
                            DISPATCHER_DOWNLOAD_DIR, LAVA_NODEBOOTER_PATH
                        )
                    )

            json = {
                "machine_name": "dut",
                "machine_model_data": {
                    "node_entities": {
                        "entities": {
                            "host-compute-node": {
                                "network_interfaces": {
                                    "network_interface": [
                                        {
                                            "device_name": "eth1",
                                            "hostname": "",
                                            "ipv6_subnet_key": "",
                                            "mac_address": self.dut_mac,
                                            "use_for_netboot": True,
                                        }
                                    ]
                                }
                            }
                        }
                    }
                },
                "boot_info": [
                    {
                        "node_entity_name": "host-compute-node",
                        "boot_file": boot_image,
                        "loader_file": "",
                    }
                ],
            }
            if nic_images:
                for counter, nic_image in enumerate(nic_images):
                    json["machine_model_data"]["node_entities"]["entities"][
                        f"nic_control_node{counter}"
                    ] = {
                        "network_interfaces": {
                            "network_interface": [
                                {
                                    "device_name": "eth1",
                                    "hostname": "",
                                    "ipv6_low64": "1729382256910270464",
                                    "ipv6_subnet_key": f"nic{counter}",
                                    "mac_address": self.job.device["environment"][
                                        f"NIC{counter}_MAC"
                                    ],
                                    "use_for_netboot": True,
                                }
                            ]
                        }
                    }
                    json["boot_info"].append(
                        {
                            "node_entity_name": f"nic_control_node{counter}",
                            "boot_file": nic_images[counter],
                            "loader_file": "",
                        }
                    )

            res = requests.post(url, json=json, headers=headers)

        except requests.RequestException as exc:
            self.logger.error("Resource not available")
            raise JobError(f"Could not update nodebooter API: {exc}")
        finally:
            if res is not None:
                self.logger.info(
                    f"Nodebooter API call response code: {res.status_code}"
                )
                res.close()

    def cleanup(self, connection):
        super().cleanup(connection)
        container = self.get_namespace_data(
            action="shared", label="shared", key="nodebooter_container"
        )
        self.logger.debug("Stopping container %s", container)
        # Stop nodebooter container
        self.run_cmd("docker stop %s" % (container), allow_fail=True)
        # Remove all files from nodebooter dir based on mac address
        # Nodebooter currently replaces ":" in mac address either with
        # "_" or "." delimiters to create initrd file names and images.
        mac_delimiters = [".", "_"]
        patterns = ["*%s*" % self.dut_mac.replace(":", x) for x in mac_delimiters]
        # Find all files that match the patterns in the directory tree
        file_list = []
        for pattern in patterns:
            file_list += glob.glob(
                os.path.join(DISPATCHER_DOWNLOAD_DIR, "**", pattern.lower()),
                recursive=True,
            )
        for file_path in file_list:
            os.remove(file_path)
