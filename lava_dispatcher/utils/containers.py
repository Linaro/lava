# Copyright (C) 2019 Linaro Limited
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import os
import uuid
from subprocess import CalledProcessError
from typing import TYPE_CHECKING

from lava_common.device_mappings import (
    add_device_container_mapping,
    remove_device_container_mappings,
)
from lava_common.exceptions import InfrastructureError, LAVABug
from lava_dispatcher.action import Action, InternalObject
from lava_dispatcher.utils.decorator import retry
from lava_dispatcher.utils.docker import DockerContainer, DockerRun
from lava_dispatcher.utils.filesystem import copy_to_lxc
from lava_dispatcher.utils.lxc import is_lxc_requested, lxc_cmd_prefix
from lava_dispatcher.utils.udev import get_udev_devices

if TYPE_CHECKING:
    from lava_dispatcher.job import Job


class DeviceContainerMappingMixin(Action):
    """
    This mixing should be included by action classes that add device/container
    mappings.
    """

    def __init__(self, job: Job):
        super().__init__(job)
        self.containers: list[DockerContainer] = []

    def add_device_container_mappings(self, container, container_type):
        device_info = self.job.device.get("device_info", [])
        static_info = self.job.device.get("static_info", [])
        job_id = self.job.job_id
        job_prefix = self.job.parameters["dispatcher"].get("prefix", "")
        devices = []
        for origdevice in device_info + static_info:
            device = origdevice.copy()
            if "board_id" in device:
                device["serial_number"] = device["board_id"]
                del device["board_id"]
            devices.append(device)
        for device in devices:
            add_device_container_mapping(
                job_prefix + job_id, device, container, container_type=container_type
            )
            self.logger.info(
                f"Added mapping for {device} to {container_type} container {container}"
            )

    def trigger_share_device_with_container(self, device):
        """
        Trigger udev to let lava-dispatcher-host into sharing the device with
        container.
        """
        self.run_cmd(["udevadm", "trigger", "--action=add", device], allow_fail=True)


class OptionalContainerAction(DeviceContainerMappingMixin):
    command_exception = InfrastructureError
    timeout_exception = InfrastructureError

    def validate(self):
        super().validate()
        key = self.driver.key
        validated = self.get_namespace_data(
            action="optional_container_action", label="prepare", key=key
        )
        if validated:
            return
        self.driver.validate()
        self.set_namespace_data(
            action="optional_container_action", label="prepare", key=key, value=True
        )

    @property
    def driver(self):
        __driver__ = getattr(self, "__driver__", None)
        if not __driver__:
            lxc = is_lxc_requested(self.job)
            if lxc:
                self.__driver__ = LxcDriver(self, lxc)
            elif "docker" in self.parameters:
                params = self.parameters["docker"]
                self.__driver__ = DockerDriver(self, params)
            else:
                self.__driver__ = NullDriver(self)
        return self.__driver__

    def maybe_copy_to_container(self, src):
        return self.driver.maybe_copy_to_container(src)

    def is_container(self):
        return self.driver.is_container

    def run_maybe_in_container(self, cmd):
        self.driver.run(cmd)

    def get_output_maybe_in_container(self, cmd, **kwargs):
        return self.driver.get_output(cmd)

    def cleanup(self, connection):
        super().cleanup(connection)

        if isinstance(self.driver, DockerDriver):
            for container in self.containers:
                self.logger.debug(f"Destroying docker container {container.__name__}")
                container.destroy()


class NullDriver(InternalObject):
    is_container = False
    key = "null"

    def __init__(self, action):
        self.action = action
        self.logger = action.logger

    def get_command_prefix(self, copy_files=True):
        return []

    def maybe_copy_to_container(self, src):
        return src

    def validate(self):
        pass

    def run(self, cmd):
        self.action.run_cmd(self.get_command_prefix() + cmd)

    def get_output(self, cmd):
        return self.action.parsed_command(self.get_command_prefix() + cmd)


class LxcDriver(NullDriver):
    is_container = True

    def __init__(self, action, lxc_name):
        super().__init__(action)
        self.lxc_name = lxc_name

    def get_command_prefix(self, copy_files=True):
        return lxc_cmd_prefix(self.action.job)

    def maybe_copy_to_container(self, src):
        src = copy_to_lxc(
            self.action, self.lxc_name, src, self.action.job.parameters["dispatcher"]
        )
        return src


class DockerDriver(NullDriver):
    is_container = True

    def __init__(self, action, params):
        super().__init__(action)
        self.params = params
        self.docker_options = []
        self.docker_run_options = []
        self.copied_files = []
        self.job_dir = action.job.parameters.get("dispatcher", {}).get(
            "prefix", ""
        ) + str(action.job.job_id)

    def get_container_name(self):
        return (
            "lava-"
            + str(self.action.job.job_id)
            + "-"
            + self.action.level
            + "-"
            + str(uuid.uuid4())
        )

    def build(self, cls, copy_files=True):
        docker = cls.from_parameters(self.params, self.action.job)
        docker.add_docker_options(*self.docker_options)
        docker.add_docker_run_options(*self.docker_run_options)

        if not self.docker_options and copy_files:
            for f in self.copied_files:
                docker.bind_mount(f)
        return docker

    def get_command_prefix(self, copy_files=True):
        docker = self.build(DockerRun, copy_files)
        return docker.cmdline()

    def run(self, cmd):
        docker = self.build(DockerContainer)
        name = self.get_container_name()
        docker.name(name)
        self.action.containers.append(docker)
        docker_test_method_conf = (
            self.action.job.device["actions"]
            .get("test", {})
            .get("methods", {})
            .get("docker", {})
        )
        docker.add_device_docker_method_options(docker_test_method_conf)
        docker.start(self.action)
        try:
            self.__map_devices__(name, docker)
            docker.run(cmd, self.action)
        finally:
            remove_device_container_mappings(self.job_dir)
            self.action.logger.debug("Removed device container mappings")
            docker.stop(self.action)

    def get_output(self, cmd):
        # FIXME duplicates most of run()
        docker = self.build(DockerContainer)
        name = self.get_container_name()
        docker.name(name)
        self.action.containers.append(docker)
        docker_test_method_conf = (
            self.action.job.device["actions"]
            .get("test", {})
            .get("methods", {})
            .get("docker", {})
        )
        docker.add_device_docker_method_options(docker_test_method_conf)
        docker.start(self.action)
        try:
            self.__map_devices__(name, docker)
            return docker.get_output(cmd, self.action)
        finally:
            remove_device_container_mappings(self.job_dir)
            self.action.logger.debug("Removed device container mappings")
            docker.stop(self.action)

    def maybe_copy_to_container(self, src):
        if src not in self.copied_files:
            self.copied_files.append(src)
        return src

    @retry(exception=LAVABug, retries=3, delay=1)
    def _retry_trigger_share_device_with_container(
        self, action: Action, dev: str, docker: DockerContainer
    ) -> None:
        """
        Re-trigger device sharing if device doesn't appear in docker container after 60s
        waiting. 60s is the default udev event processing timeout.
        """
        action.trigger_share_device_with_container(dev)
        action.logger.debug(
            f"Waiting for device '{dev}' to appear in docker container {docker.__name__} ..."
        )
        try:
            docker.wait_file(dev, 60)
        except CalledProcessError:
            raise LAVABug(
                f"Failed to share device '{dev}' to docker container {docker.__name__}"
            )
        action.logger.info(
            f"Shared device '{dev}' to docker container {docker.__name__}"
        )

    def __map_devices__(self, container_name, docker):
        action = self.action
        action.add_device_container_mappings(container_name, "docker")
        for dev in self.__get_device_nodes__():
            if not os.path.islink(dev):
                self._retry_trigger_share_device_with_container(action, dev, docker)

    def __get_device_nodes__(self):
        device_info = self.action.job.device.get("device_info", {})
        if device_info:
            return get_udev_devices(device_info=device_info)
        else:
            return []

    @property
    def key(self):
        docker = DockerRun.from_parameters(self.params, self.action.job)
        return docker.image

    def validate(self):
        docker = DockerRun.from_parameters(self.params, self.action.job)
        docker.add_docker_options(*self.docker_options)
        docker.prepare(self.action)
