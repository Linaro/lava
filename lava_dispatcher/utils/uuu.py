# Copyright 2020-2023 NXP
#
# Author: Larry Shen <larry.shen@nxp.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later


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
        __driver__ = getattr(self, "__driver__", None)
        if not __driver__:
            docker_image = self.job.device["actions"]["boot"]["methods"]["uuu"][
                "options"
            ]["docker_image"]
            if docker_image or "docker" in self.parameters:
                params = self.parameters.get("docker", {"image": docker_image})
                remote_options = self.job.device["actions"]["boot"]["methods"]["uuu"][
                    "options"
                ]["remote_options"]
                self.__driver__ = DockerDriver(self, params)
                self.__driver__.docker_options = shlex.split(remote_options)
                self.__driver__.docker_run_options = [
                    "-t",
                    "--privileged",
                    "--volume=/dev:/dev",
                    "--net=host",
                ]
            else:
                self.__driver__ = NullDriver(self)
        return self.__driver__

    def which(self, path):
        if self.driver.is_container:
            return path
        return which(path)

    def run_bcu(self, cmd, allow_fail=False, error_msg=None, cwd=None):
        return self.run_cmd(self.get_uuu_bcu_cmd(cmd), allow_fail, error_msg, cwd)

    def run_uuu(self, cmd, allow_fail=False, error_msg=None, cwd=None):
        return self.run_cmd(self.get_uuu_bcu_cmd(cmd), allow_fail, error_msg, cwd)

    def get_uuu_bcu_cmd(self, cmd):
        uuu_bcu_cmd = self.driver.get_command_prefix() + self.get_manipulated_command(
            cmd
        )
        return uuu_bcu_cmd

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
