# Copyright 2020-2023, 2025-2026 NXP
#
# Author: Larry Shen <larry.shen@nxp.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import shlex

from lava_common.exceptions import JobError
from lava_dispatcher.utils.containers import (
    DockerDriver,
    NullDriver,
    OptionalContainerAction,
)
from lava_dispatcher.utils.network import dispatcher_ip
from lava_dispatcher.utils.shell import which


class OptionalContainerUuuAction(OptionalContainerAction):
    @property
    def driver(self) -> NullDriver:
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
                    "--privileged",
                    "--volume=/dev:/dev",
                    "--net=host",
                    "-e",
                    "DISABLE_SUMMARY=true",
                ]
            else:
                self.__driver__ = NullDriver(self)
        return self.__driver__

    def which(self, path: str) -> str:
        if self.driver.is_container:
            return path
        return which(path)

    def run_bcu(
        self,
        cmd: list[str],
        allow_fail: bool = False,
        error_msg: str | None = None,
        cwd: str | None = None,
    ) -> int | None:
        return self.run_cmd(
            self.get_uuu_bcu_cmd(cmd, False),
            allow_fail=allow_fail,
            error_msg=error_msg,
            cwd=cwd,
        )

    def run_uuu(
        self,
        cmd: list[str],
        allow_fail: bool = False,
        error_msg: str | None = None,
        cwd: str | None = None,
    ) -> int | None:
        return self.run_cmd(
            self.get_uuu_bcu_cmd(cmd),
            allow_fail=allow_fail,
            error_msg=error_msg,
            cwd=cwd,
            env={"DISABLE_SUMMARY": "true"},
        )

    def get_uuu_bcu_cmd(self, cmd: list[str], copy_files: bool = True) -> list[str]:
        uuu_bcu_cmd = self.driver.get_command_prefix(
            copy_files
        ) + self.get_manipulated_command(cmd)
        return uuu_bcu_cmd

    def get_manipulated_command(self, cmd: list[str]) -> list[str]:
        if isinstance(self.driver, DockerDriver) and self.driver.docker_options:
            ip_addr = dispatcher_ip(self.job.parameters["dispatcher"])
            root_location: str | None = self.get_namespace_data(
                action="uuu-deploy", label="uuu-images", key="root_location"
            )
            if root_location is None:
                raise JobError(
                    "UUU root location not found: namespace data key "
                    "'root_location' (action 'uuu-deploy', label "
                    "'uuu-images') is not set"
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
