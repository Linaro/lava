# Copyright (C) 2019 Linaro Limited
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
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
import uuid

from lava_common.exceptions import InfrastructureError
from lava_dispatcher.action import Action, InternalObject
from lava_dispatcher.utils.docker import DockerContainer, DockerRun
from lava_dispatcher.utils.filesystem import copy_to_lxc
from lava_dispatcher.utils.lxc import is_lxc_requested, lxc_cmd_prefix
from lava_dispatcher.utils.udev import get_udev_devices
from lava_dispatcher_host.action import DeviceContainerMappingMixin


class OptionalContainerAction(Action, DeviceContainerMappingMixin):
    command_exception = InfrastructureError

    def __init__(self):
        super().__init__()
        self._driver = None

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
        if self._driver is None:
            lxc = is_lxc_requested(self.job)
            if lxc:
                self._driver = LxcDriver(self, lxc)
            elif "docker" in self.parameters:
                params = self.parameters["docker"]
                self._driver = DockerDriver(self, params)
            else:
                self._driver = NullDriver(self)

        return self._driver

    def maybe_copy_to_container(self, src):
        return self.driver.maybe_copy_to_container(src)

    def is_container(self):
        return self.driver.is_container

    def run_maybe_in_container(self, cmd):
        self.driver.run(cmd)

    def get_output_maybe_in_container(self, cmd, **kwargs):
        return self.driver.get_output(cmd)


class NullDriver(InternalObject):
    is_container = False
    key = "null"

    def __init__(self, action):
        self.action = action

    def get_command_prefix(self):
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

    def get_command_prefix(self):
        return lxc_cmd_prefix(self.action.job)

    def maybe_copy_to_container(self, src):
        src = copy_to_lxc(self.lxc_name, src, self.action.job.parameters["dispatcher"])
        return src


class DockerDriver(NullDriver):
    is_container = True

    def __init__(self, action, params):
        super().__init__(action)
        self.params = params
        self.docker_options = []
        self.docker_run_options = []
        self.copied_files = []

    def get_container_name(self):
        return (
            "lava-"
            + str(self.action.job.job_id)
            + "-"
            + self.action.level
            + "-"
            + str(uuid.uuid4())
        )

    def build(self, cls):
        docker = cls.from_parameters(self.params, self.action.job)
        docker.add_docker_options(*self.docker_options)
        docker.add_docker_run_options(*self.docker_run_options)

        if not self.docker_options:
            for f in self.copied_files:
                docker.add_bind_mount(f)
        return docker

    def get_command_prefix(self):
        docker = self.build(DockerRun)
        return docker.cmdline()

    def run(self, cmd):
        docker = self.build(DockerContainer)
        name = self.get_container_name()
        docker.set_container_name(name)
        docker.start(self.action)
        try:
            self._map_devices(name)
            docker.run(cmd, self.action)
        finally:
            docker.stop()

    def get_output(self, cmd):
        # FIXME duplicates most of run()
        docker = self.build(DockerContainer)
        name = self.get_container_name()
        docker.set_container_name(name)
        docker.start(self.action)
        try:
            self._map_devices(name)
            return docker.get_output(cmd, self.action)
        finally:
            docker.stop()

    def maybe_copy_to_container(self, src):
        if src not in self.copied_files:
            self.copied_files.append(src)
        return src

    def _map_devices(self, container_name):
        action = self.action
        action.add_device_container_mappings(container_name, "docker")
        for dev in self._get_device_nodes():
            if not os.path.islink(dev):
                action.trigger_share_device_with_container(dev)

    def _get_device_nodes(self):
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
        docker.prepare(self.action)
