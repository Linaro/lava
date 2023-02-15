# Copyright 2020 NXP
#
# Author: Larry Shen <larry.shen@nxp.com>
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


import shlex

from lava_dispatcher.utils.containers import (
    DockerDriver,
    NullDriver,
    OptionalContainerAction,
)
from lava_dispatcher.utils.network import dispatcher_ip
from lava_dispatcher.utils.shell import which


class OptionalContainerUuuAction(OptionalContainerAction):
    @property
    def driver(self):
        if self._driver is None:
            docker_image = self.job.device["actions"]["boot"]["methods"]["uuu"][
                "options"
            ]["docker_image"]
            if docker_image or "docker" in self.parameters:
                params = self.parameters.get("docker", {"image": docker_image})
                remote_options = self.job.device["actions"]["boot"]["methods"]["uuu"][
                    "options"
                ]["remote_options"]
                self._driver = DockerDriver(self, params)
                self._driver.docker_options = shlex.split(remote_options)
                self._driver.docker_run_options = [
                    "-t",
                    "--privileged",
                    "--volume=/dev:/dev",
                    "--net=host",
                ]
            else:
                self._driver = NullDriver(self)

        return self._driver

    def which(self, path):
        if self.driver.is_container:
            return path
        return which(path)

    def run_uuu(self, cmd, allow_fail=False, error_msg=None, cwd=None):
        return self.run_cmd(self.get_uuu_cmd(cmd), allow_fail, error_msg, cwd)

    def get_uuu_cmd(self, cmd):
        uuu_cmd = self.driver.get_command_prefix() + self.get_manipulated_command(cmd)
        return uuu_cmd

    def get_manipulated_command(self, cmd):
        if self.driver.is_container and self.driver.docker_options:
            ip_addr = dispatcher_ip(self.job.parameters["dispatcher"])
            root_location = self.get_namespace_data(
                action="uuu-deploy", label="uuu-images", key="root_location"
            )
            cmd = [
                "mkdir",
                "-p",
                root_location,
                "&&",
                "mount",
                "-t",
                "nfs",
                "-o",
                "nolock",
                ip_addr + ":" + root_location,
                root_location,
                "&&",
            ] + cmd
            cmd = ["bash", "-c", " ".join(cmd)]

        return cmd
