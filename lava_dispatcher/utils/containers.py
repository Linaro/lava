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


from lava_common.exceptions import InfrastructureError
from lava_dispatcher.action import Action, InternalObject
from lava_dispatcher.utils.docker import DockerRun
from lava_dispatcher.utils.filesystem import copy_to_lxc
from lava_dispatcher.utils.lxc import is_lxc_requested, lxc_cmd_prefix
from lava_dispatcher.utils.udev import get_udev_devices


class OptionalContainerAction(Action):
    command_exception = InfrastructureError

    @property
    def driver(self):
        __driver__ = getattr(self, "__driver__", None)
        if not __driver__:
            lxc = is_lxc_requested(self.job)
            if lxc:
                self.__driver__ = LxcDriver(self, lxc)
            elif "docker" in self.parameters:
                image = self.parameters["docker"]["image"]
                self.__driver__ = DockerDriver(self, image)
            else:
                self.__driver__ = NullDriver(self)
        return self.__driver__

    def maybe_copy_to_container(self, src):
        return self.driver.maybe_copy_to_container(src)

    def is_container(self):
        return self.driver.is_container


class NullDriver(InternalObject):
    is_container = False

    def __init__(self, action):
        self.action = action

    def get_command_prefix(self):
        return []

    def maybe_copy_to_container(self, src):
        return src


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

    def __init__(self, action, image):
        super().__init__(action)
        self.image = image
        self.docker_options = []
        self.docker_run_options = []
        self.copied_files = []

    def get_command_prefix(self):
        docker = DockerRun(self.image)

        docker.add_docker_options(*self.docker_options)
        docker.add_docker_run_options(*self.docker_run_options)

        for device in self.__get_device_nodes__():
            docker.add_device(device)

        if not self.docker_options:
            for f in self.copied_files:
                docker.bind_mount(f)

        return docker.cmdline()

    def maybe_copy_to_container(self, src):
        self.copied_files.append(src)
        return src

    def __get_device_nodes__(self):
        device_info = self.action.job.device.get("device_info", {})
        if device_info:
            return get_udev_devices(device_info=device_info)
        else:
            return []
