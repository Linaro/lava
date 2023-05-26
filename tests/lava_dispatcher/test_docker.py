# Copyright 2022 NXP
#
# Author: Larry Shen <larry.shen@nxp.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from pathlib import Path
from unittest.mock import MagicMock, patch

from tests.lava_dispatcher.test_basic import Factory, StdoutTestCase


class DockerFactory(Factory):
    """
    Not Model based, this is not a Django factory.
    Factory objects are dispatcher based classes, independent
    of any database objects.
    """

    def create_docker_job(self, filename):
        return self.create_job("docker-01.jinja2", filename)


class TestDocker(StdoutTestCase):
    def setUp(self):
        super().setUp()
        self.factory = DockerFactory()
        self.job = self.factory.create_docker_job("sample_jobs/docker-interactive.yaml")

    def test_pipeline(self):
        description_ref = self.pipeline_reference("docker-interactive.yaml", self.job)
        self.assertEqual(description_ref, self.job.pipeline.describe())

    @patch(
        "lava_dispatcher.actions.deploy.docker.which",
        return_value="/bin/test_docker",
    )
    @patch("subprocess.check_output")
    @patch("lava_dispatcher.action.Action.run")
    @patch("lava_dispatcher.actions.deploy.docker.DockerAction.run_cmd")
    def test_deploy(self, run_cmd, *args):
        self.job.validate()

        deploy = [
            action
            for action in self.job.pipeline.actions
            if action.name == "deploy-docker"
        ][0]

        connection = MagicMock()
        connection.timeout = MagicMock()
        deploy.run(connection, 0)

        run_cmd.assert_called_with(
            ["docker", "pull", "archlinux"],
            error_msg="Unable to pull docker image 'archlinux'",
        )

    @patch(
        "lava_dispatcher.actions.deploy.docker.which",
        return_value="/bin/test_docker",
    )
    @patch("subprocess.check_output")
    @patch("lava_dispatcher.actions.deploy.docker.DockerAction.run_cmd")
    @patch(
        "lava_dispatcher.actions.boot.docker.CallDockerAction.get_namespace_data",
        return_value="foo/bar",
    )
    @patch("lava_dispatcher.actions.boot.docker.ShellSession")
    @patch("lava_dispatcher.actions.boot.docker.ShellCommand")
    def test_boot(self, shell_command, *args):
        self.job.validate()

        boot = [
            action
            for action in self.job.pipeline.actions
            if action.name == "boot-docker"
        ][0]
        call = [
            action for action in boot.pipeline.actions if action.name == "docker-run"
        ][0]

        connection = MagicMock()
        connection.timeout = MagicMock()

        call.run(connection, 0)
        shell_command.assert_called_with(
            "docker run --rm --interactive --tty --hostname lava --name lava-4999-2.1 --volume foo/bar/foo/bar:foo/bar foo/bar bash",
            call.timeout,
            logger=call.logger,
        )

        # verify lava managed downloads
        managed_downloads_dir = Path(self.job.tmp_dir) / "downloads/common"
        managed_downloads_dir.mkdir(parents=True)
        call.run(connection, 0)
        shell_command.assert_called_with(
            f"docker run --rm --interactive --tty --hostname lava --name lava-4999-2.1 --volume foo/bar/foo/bar:foo/bar --volume {self.job.tmp_dir}/downloads/common:/lava-downloads foo/bar bash",
            call.timeout,
            logger=call.logger,
        )


class DockerDb410cFactory(Factory):
    """
    Not Model based, this is not a Django factory.
    Factory objects are dispatcher based classes, independent
    of any database objects.
    """

    def create_docker_db410c_job(self, filename):
        return self.create_job("db410c-01.jinja2", filename)


class TestDockerDb410c(StdoutTestCase):
    def setUp(self):
        super().setUp()
        self.factory = DockerDb410cFactory()
        self.job = self.factory.create_docker_db410c_job(
            "sample_jobs/docker-test-db410c.yaml"
        )

    def test_pipeline(self):
        description_ref = self.pipeline_reference("docker-test-db410c.yaml", self.job)
        self.assertEqual(description_ref, self.job.pipeline.describe())
