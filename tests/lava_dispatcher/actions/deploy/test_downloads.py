# Copyright (C) 2019 Linaro Limited
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from unittest.mock import ANY as MOCK_ANY
from unittest.mock import MagicMock, patch

from lava_dispatcher.actions.deploy.download import DownloaderAction
from lava_dispatcher.actions.deploy.downloads import (
    DownloadsAction,
    PostprocessWithDocker,
)

from ...test_basic import Factory, LavaDispatcherTestCase


class TestDownloads(LavaDispatcherTestCase):
    def setUp(self):
        super().setUp()
        self.job = self.create_simple_job()

    def test_downloads_action(self):
        action = DownloadsAction(self.job)
        action.level = 2
        action.populate(
            {
                "images": {"rootfs": {"url": "https://example.com/image.img"}},
                "namespace": "common",
            }
        )
        download = action.pipeline.actions[0]
        self.assertIsInstance(download, DownloaderAction)
        self.assertEqual(download.key, "rootfs")
        self.assertEqual(str(download.path), f"{self.job.tmp_dir}/downloads/common")
        self.assertEqual(download.params, {"url": "https://example.com/image.img"})
        self.assertFalse(download.uniquify)

    def test_uniquify(self):
        action = DownloadsAction(self.job)
        action.level = 2
        action.populate(
            {
                "uniquify": True,
                "images": {
                    "rootfs": {"url": "https://example.com/rootfs/image"},
                    "boot": {"url": "https://example.com/boot/image"},
                },
                "namespace": "common",
            }
        )
        download_rootfs = action.pipeline.actions[0].pipeline.actions[0]
        download_boot = action.pipeline.actions[1].pipeline.actions[0]

        self.assertNotEqual(download_rootfs.path, download_boot.path)

    def test_downloads_action_adds_docker_action(self):
        factory = Factory()
        factory.validate_job_strict = True
        job = factory.create_job("qemu01", "sample_jobs/qemu-download-postprocess.yaml")

        deploy = job.pipeline.actions[0]
        action = deploy.pipeline.actions[-1]
        self.assertIsInstance(action, PostprocessWithDocker)
        self.assertEqual(str(action.path), f"{job.tmp_dir}/downloads/common")

    def test_postprocess_with_docker_populate_missing_data(self):
        action = PostprocessWithDocker(self.job, self.create_temporary_directory())
        action.populate({})

    def test_postprocess_with_docker_validate(self):
        action = PostprocessWithDocker(self.job, self.create_temporary_directory())
        self.assertFalse(action.validate())
        self.assertIn("postprocessing steps missing", action.errors)
        action.steps = ["date"]
        action.errors.clear()
        self.assertTrue(action.validate())
        self.assertEqual(len(action.errors), 0)


class TestPostprocessDocker(LavaDispatcherTestCase):
    def setUp(self):
        super().setUp()
        self.job = self.create_simple_job()
        self.action = PostprocessWithDocker(self.job, self.create_temporary_directory())
        self.action.job = self.job
        parameters = {
            "postprocess": {
                "docker": {"image": "foo", "steps": ["date", "echo HELLO WORLD"]}
            },
            "namespace": "common",
        }
        self.action.populate(parameters)
        # this simulates Pipeline.add_action method
        self.action.parameters = parameters

    def test_postprocess_with_docker_populate(self):
        self.assertEqual(self.action.docker_parameters["image"], "foo")
        self.assertIn("date", self.action.steps)
        self.assertIn("echo HELLO WORLD", self.action.steps)

    def test_postprocess_with_docker_run(self):
        origconn = MagicMock()
        with patch("lava_dispatcher.utils.docker.DockerRun.run") as docker_run_mock:
            conn = self.action.run(origconn, 4242)

        self.assertIs(conn, origconn)

        script = self.action.path / "postprocess.sh"
        self.assertTrue(script.exists())
        script_text = script.read_text()
        self.assertIn("date\n", script_text)
        self.assertIn("echo HELLO WORLD\n", script_text)

        docker_run_mock.assert_called_with(
            MOCK_ANY,
            action=self.action,
            error_msg="Post-processing of downloads failed",
        )
