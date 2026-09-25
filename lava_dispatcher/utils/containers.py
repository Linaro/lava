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
from lava_dispatcher.utils.udev import get_udev_devices

if TYPE_CHECKING:
    from typing import Any, ClassVar, TypeVar

    from lava_dispatcher.job import Job
    from lava_dispatcher.shell import ShellSession

    DockerType = TypeVar("DockerType", bound=DockerRun)


class DeviceContainerMappingMixin(Action):
    """
    This mixing should be included by action classes that add device/container
    mappings.
    """

    def __init__(self, job: Job):
        super().__init__(job)
        self.containers: list[DockerRun] = []

    def add_device_container_mappings(
        self,
        container: str,
        container_type: str,
    ) -> None:
        device_info: list[dict[str, Any]] = self.job.device.get("device_info", [])
        static_info: list[dict[str, Any]] = self.job.device.get("static_info", [])
        job_id = self.job.job_id
        job_prefix: str = self.job.parameters["dispatcher"].get("prefix", "")
        devices: list[dict[str, Any]] = []
        for origdevice in device_info + static_info:
            device = origdevice.copy()
            if "board_id" in device:
                device["serial_number"] = device["board_id"]
                del device["board_id"]
            devices.append(device)
        for origdevice, device in zip(device_info + static_info, devices):
            # persist the exact node path(s) the dispatcher resolved for this
            # device_info, so lava-dispatcher-host shares only those nodes and
            # never trusts a client-supplied path.
            device_paths = get_udev_devices(device_info=[origdevice])
            add_device_container_mapping(
                job_prefix + job_id,
                device,
                container,
                container_type=container_type,
                device_paths=device_paths,
            )
            self.logger.info(
                f"Added mapping for {device} to {container_type} container {container}"
            )

    def trigger_share_device_with_container(self, device: str) -> None:
        """
        Trigger udev to let lava-dispatcher-host into sharing the device with
        container.
        """
        self.run_cmd(["udevadm", "trigger", "--action=add", device], allow_fail=True)


class OptionalContainerAction(DeviceContainerMappingMixin):
    command_exception = InfrastructureError
    timeout_exception = InfrastructureError

    def validate(self) -> None:
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
    def driver(self) -> NullDriver:
        __driver__ = getattr(self, "__driver__", None)
        if not __driver__:
            if "docker" in self.parameters:
                params = self.parameters["docker"]
                self.__driver__: NullDriver = DockerDriver(self, params)
            else:
                self.__driver__ = NullDriver(self)
        return self.__driver__

    def maybe_copy_to_container(self, src: str) -> str:
        return self.driver.maybe_copy_to_container(src)

    def is_container(self) -> bool:
        return self.driver.is_container

    def run_maybe_in_container(self, cmd: list[str]) -> None:
        self.driver.run(cmd)

    def get_output_maybe_in_container(self, cmd: list[str]) -> str:
        return self.driver.get_output(cmd)

    def cleanup(
        self,
        connection: ShellSession | None,
        max_end_time: float | None = None,
    ) -> None:
        super().cleanup(connection, max_end_time)

        if isinstance(self.driver, DockerDriver):
            for container in self.containers:
                self.logger.debug(
                    f"Destroying docker container {container._container_name}"
                )
                container.destroy()


class NullDriver(InternalObject):
    is_container: ClassVar[bool] = False

    def __init__(self, action: DeviceContainerMappingMixin):
        self.action = action
        self.logger = action.logger

    @property
    def key(self) -> str:
        return "null"

    def get_command_prefix(self, copy_files: bool = True) -> list[str]:
        return []

    def maybe_copy_to_container(self, src: str) -> str:
        return src

    def validate(self) -> None:
        pass

    def run(self, cmd: list[str]) -> None:
        self.action.run_cmd(self.get_command_prefix() + cmd)

    def get_output(self, cmd: list[str]) -> str:
        return self.action.parsed_command(self.get_command_prefix() + cmd)


class DockerDriver(NullDriver):
    is_container = True

    def __init__(self, action: DeviceContainerMappingMixin, params: dict[str, Any]):
        super().__init__(action)
        self.params = params
        self.docker_options: list[str] = []
        self.docker_run_options: list[str] = []
        self.copied_files: list[str] = []
        self.job_dir: str = action.job.parameters.get("dispatcher", {}).get(
            "prefix", ""
        ) + str(action.job.job_id)

    def get_container_name(self) -> str:
        return (
            "lava-"
            + str(self.action.job.job_id)
            + "-"
            + str(self.action.level)
            + "-"
            + str(uuid.uuid4())
        )

    def build(
        self,
        cls: type[DockerType],
        copy_files: bool = True,
    ) -> DockerType:
        docker = cls.from_parameters(self.params, self.action.job)
        docker.add_docker_options(*self.docker_options)
        docker.add_docker_run_options(*self.docker_run_options)

        if not self.docker_options and copy_files:
            for f in self.copied_files:
                docker.bind_mount(f)
        return docker

    def get_command_prefix(self, copy_files: bool = True) -> list[str]:
        docker = self.build(DockerRun, copy_files)
        return docker.cmdline()

    def run(self, cmd: list[str]) -> None:
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

    def get_output(self, cmd: list[str]) -> str:
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
            return docker.run(cmd, self.action, capture=True)
        finally:
            remove_device_container_mappings(self.job_dir)
            self.action.logger.debug("Removed device container mappings")
            docker.stop(self.action)

    def maybe_copy_to_container(self, src: str) -> str:
        if src not in self.copied_files:
            self.copied_files.append(src)
        return src

    @retry(exception=LAVABug, retries=3, delay=1)
    def _retry_trigger_share_device_with_container(
        self, action: DeviceContainerMappingMixin, dev: str, docker: DockerRun
    ) -> None:
        """
        Re-trigger device sharing if device doesn't appear in docker container after 60s
        waiting. 60s is the default udev event processing timeout.
        """
        action.trigger_share_device_with_container(dev)
        action.logger.debug(
            f"Waiting for device {dev!r} to appear in docker container {docker._container_name} ..."
        )
        try:
            docker.wait_file(dev, 60)
        except CalledProcessError:
            raise LAVABug(
                f"Failed to share device {dev!r} to docker container {docker._container_name}"
            )
        action.logger.info(
            f"Shared device {dev!r} to docker container {docker._container_name}"
        )

    def __map_devices__(self, container_name: str, docker: DockerRun) -> None:
        action = self.action
        action.add_device_container_mappings(container_name, "docker")
        for dev in self.__get_device_nodes__():
            if not os.path.islink(dev):
                self._retry_trigger_share_device_with_container(action, dev, docker)

    def __get_device_nodes__(self) -> list[str]:
        device_info = self.action.job.device.get("device_info", [{}])
        if device_info:
            return get_udev_devices(device_info=device_info)
        else:
            return []

    @property
    def key(self) -> str:
        docker = DockerRun.from_parameters(self.params, self.action.job)
        return docker.image

    def validate(self) -> None:
        docker = DockerRun.from_parameters(self.params, self.action.job)
        docker.add_docker_options(*self.docker_options)
        docker.prepare(self.action)
