# Copyright (C) 2025 Linaro Limited
#
# Author: Chase Qi <chase.qi@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from __future__ import annotations

import os
import re
import shutil
import subprocess
from typing import TYPE_CHECKING

from lava_common.constants import DEFAULT_TEST_NAME_CLASS
from lava_common.exceptions import InfrastructureError, JobError, LAVATimeoutError
from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.actions.deploy.download import DownloaderAction
from lava_dispatcher.logical import RetryAction
from lava_dispatcher.utils.compression import untar_file
from lava_dispatcher.utils.shell import which
from lava_dispatcher.utils.vcs import GitHelper

if TYPE_CHECKING:
    from lava_dispatcher.job import Job


class TestServices(Action):
    name = "lava-test-services"
    description = "Executing lava-test-services"
    summary = "Lava Test Services"

    def validate(self):
        super().validate()

        if self.job.device.get("parameters", {}).get("allow_test_services") is not True:
            self.errors = (
                "Device 'allow_test_services' must be set to 'true' "
                "for running test services on LAVA worker."
            )
            return

        names = [service["name"] for service in self.parameters["services"]]
        if len(names) != len(set(names)):
            self.errors = "Test service names need to be unique."
        exp = re.compile(DEFAULT_TEST_NAME_CLASS)
        for name in names:
            if not exp.match(name):
                self.errors = (
                    f"Invalid characters found in test service name {name!r}. "
                    "Allowed: letters, digits, underscore and hyphen."
                )

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        services = parameters.pop("services")
        for service in services:
            self.pipeline.add_action(
                TestServiceRetry(self.job),
                parameters={**service, **parameters},
            )


class TestServiceRetry(RetryAction):
    name = "lava-test-service-retry"
    description = "Retry wrapper for lava-test-service"
    summary = "Retry support for Lava Test Service"

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.pipeline.add_action(TestServiceAction(self.job))


class TestServiceAction(Action):
    name = "lava-test-service"
    description = "Executing lava-test-service"
    summary = "Lava Test Service"
    timeout_exception = LAVATimeoutError

    def __init__(self, job: Job):
        super().__init__(job)
        self.service_name: str = ""
        self.download_dir: str = ""
        self.repo_dir: str = ""
        self.project_name: str = ""
        self.start_cmd: list[str] = []
        self.stop_cmd: list[str] = []
        self.started: bool = False

    def populate(self, parameters):
        self.service_name = parameters["name"]
        self.download_dir = self.mkdtemp()

        if self.parameters["from"] == "url":
            self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
            parameters["url"] = parameters["repository"]
            self.pipeline.add_action(
                DownloaderAction(
                    self.job,
                    self.service_name,
                    self.download_dir,
                    params=parameters,
                    uniquify=False,
                )
            )

    def validate(self):
        super().validate()

        which("docker")
        try:
            subprocess.run(
                ["docker", "compose", "version"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
            )
            cmd_prefix = ["docker", "compose"]
        except subprocess.CalledProcessError:
            self.logger.debug("Docker Compose V2 not found, checking V1 ...")
            which("docker-compose")
            cmd_prefix = ["docker-compose"]

        self.repo_dir = f"{self.download_dir}/{self.service_name}"
        prefix = f"lava-{self.job.job_id}"
        if self.level:
            # '.' is not allowed in docker compose project name.
            prefix = f"{prefix}-{self.level.replace('.', '-')}"
        self.project_name = f"{prefix}-test-service-{self.service_name}"
        cmd_prefix += [
            "--project-name",
            self.project_name,
            "--file",
        ]

        # Use absolute path so it can be stopped from anywhere.
        self.stop_cmd = cmd_prefix + [
            f"{self.repo_dir}/{self.parameters['path']}",
            "down",
        ]
        # For stopping services via command: stop_test_services.
        cmd_list = self.get_namespace_data(
            action=self.name, label="stop-services", key="cmd-list"
        )
        if cmd_list:
            if self.stop_cmd not in cmd_list:
                cmd_list.append(self.stop_cmd)
        else:
            cmd_list = [self.stop_cmd]
        self.set_namespace_data(
            action="lava-test-service",
            label="stop-services",
            key="cmd-list",
            value=cmd_list,
        )

        self.start_cmd = cmd_prefix + [self.parameters["path"], "up", "--detach"]
        if service := self.parameters.get("service"):
            self.start_cmd.append(service)

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)

        self.results = {"name": self.service_name}
        repo_from = self.parameters["from"]
        # clone/untar
        if repo_from == "git":
            self.logger.info(f"Fetching {self.parameters['repository']} ...")
            vcs = GitHelper(self.parameters["repository"])
            if revision := self.parameters.get("revision"):
                shallow = False
            else:
                shallow = self.parameters.get("shallow", True)
            commit_id = vcs.clone(
                self.repo_dir,
                shallow=shallow,
                revision=revision,
                branch=self.parameters.get("branch"),
                history=self.parameters.get("history", True),
                recursive=self.parameters.get("recursive", False),
            )
            if commit_id is None:
                raise InfrastructureError(
                    f"Unable to clone repo {self.parameters['repository']}"
                )
            self.results = {
                "commit": commit_id,
            }
        elif repo_from == "url":
            fpath = self.get_namespace_data(
                action="download-action", label="file", key=self.service_name
            )
            if fpath is None:
                raise JobError(f"Repo archive not found.")

            self.logger.info(
                f"Untar tests from file {fpath} to directory {self.repo_dir}"
            )
            untar_file(fpath, self.repo_dir)
        else:
            raise JobError(
                f"Repository from {repo_from!r} is not supported. Allowed: 'git' and 'url'."
            )

        self.logger.info(f"Starting test service {self.service_name} ...")
        self.started = True
        self.run_cmd(self.start_cmd, allow_fail=False, cwd=self.repo_dir)

        return connection

    def cleanup(self, connection, max_end_time=None):
        super().cleanup(connection, max_end_time)

        if self.started:
            self.logger.debug(f"Stopping test service {self.service_name} ...")
            self.run_cmd(self.stop_cmd, allow_fail=True)

        if os.path.exists(self.repo_dir):
            self.logger.debug(f"Removing service repo directory: {self.repo_dir}")
            shutil.rmtree(self.repo_dir)
