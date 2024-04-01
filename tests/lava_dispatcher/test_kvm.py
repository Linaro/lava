# Copyright (C) 2014 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#         Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import glob
import os
import unittest
from unittest.mock import patch

from pexpect import EOF as pexpect_eof

from lava_common.exceptions import InfrastructureError, JobError
from lava_common.yaml import yaml_safe_load
from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.actions.boot import AutoLoginAction, LoginAction
from lava_dispatcher.actions.boot.qemu import BootQEMUImageAction, CallQemuAction
from lava_dispatcher.actions.deploy.download import DownloaderAction
from lava_dispatcher.actions.deploy.overlay import OverlayAction
from lava_dispatcher.actions.deploy.testdef import InlineRepoAction
from lava_dispatcher.connections.serial import QemuSession
from lava_dispatcher.utils.filesystem import mkdtemp
from lava_dispatcher.utils.messages import LinuxKernelMessages
from tests.lava_dispatcher.test_basic import Factory, LavaDispatcherTestCase
from tests.lava_dispatcher.test_defs import allow_missing_path, check_missing_path
from tests.lava_dispatcher.test_messages import create_shell_session_cat_file
from tests.utils import DummyLogger, infrastructure_error


class TestKVMSimulation(LavaDispatcherTestCase):
    def test_kvm_simulation(self):
        """
        Build a pipeline which simulates a KVM LAVA job
        without using the formal objects (to avoid validating
        data known to be broken). The details are entirely
        arbitrary.
        """
        factory = Factory()
        job = factory.create_kvm_job("sample_jobs/kvm.yaml")
        pipe = Pipeline(job=job)
        action = Action(job)
        action.name = "deploy_linaro_image"
        action.description = "deploy action using preset subactions in an internal pipe"
        action.summary = "deploy_linaro_image"
        # deliberately unlikely location
        # a successful validation would need to use the cwd
        action.parameters = {"image": "file:///none/images/bad-kvm-debian-wheezy.img"}
        pipe.add_action(action)
        self.assertEqual(action.level, "1")
        deploy_pipe = Pipeline(job=job, parent=action)
        action = Action(job)
        action.name = "downloader"
        action.description = "download image wrapper, including an internal retry pipe"
        action.summary = "downloader"
        deploy_pipe.add_action(action)
        self.assertEqual(action.level, "1.1")
        # a formal RetryAction would contain a pre-built pipeline which can be
        # inserted directly
        retry_pipe = Pipeline(job=job, parent=action)
        action = Action(job)
        action.name = "wget"
        action.description = "do the download with retries"
        action.summary = "wget"
        retry_pipe.add_action(action)
        self.assertEqual(action.level, "1.1.1")
        action = Action(job)
        action.name = "checksum"
        action.description = "checksum the downloaded file"
        action.summary = "md5sum"
        deploy_pipe.add_action(action)
        self.assertEqual(action.level, "1.2")
        action = Action(job)
        action.name = "overlay"
        action.description = "apply lava overlay"
        action.summary = "overlay"
        deploy_pipe.add_action(action)
        self.assertEqual(action.level, "1.3")
        action = Action(job)
        action.name = "boot"
        action.description = "boot image"
        action.summary = "qemu"
        # cmd_line built from device configuration
        action.parameters = {
            "cmd_line": [
                "qemu-system-x86_64",
                "-machine accel=kvm:tcg",
                "-hda" "%s" % "tbd",
                "-nographic",
                "-net",
                "nic,model=virtio",
                "-net user",
            ]
        }
        pipe.add_action(action)
        self.assertEqual(action.level, "2")

        action = Action(job)
        action.name = "simulated"
        action.description = "lava test shell"
        action.summary = "simulated"
        # a formal lava test shell action would include an internal pipe
        # which would handle the run.sh
        pipe.add_action(action)
        self.assertEqual(action.level, "3")
        # just a fake action
        action = Action(job)
        action.name = "fake"
        action.description = "faking results"
        action.summary = "fake action"
        pipe.add_action(action)
        self.assertEqual(action.level, "4")
        self.assertEqual(len(pipe.describe()), 4)


class TestKVMBasicDeploy(LavaDispatcherTestCase):
    def setUp(self):
        super().setUp()
        self.factory = Factory()
        job_ctx = {
            "arch": "amd64",
            "no_kvm": True,
        }  # override to allow unit tests on all types of systems
        self.job = self.factory.create_job("qemu01", "sample_jobs/kvm.yaml", job_ctx)

    def test_deploy_job(self):
        self.assertEqual(self.job.pipeline.job, self.job)
        action = self.job.pipeline.actions[0]
        self.assertEqual(action.job, self.job)

    def test_pipeline(self):
        description_ref = self.pipeline_reference("kvm.yaml", job=self.job)
        self.assertEqual(description_ref, self.job.pipeline.describe())

        overlay = self.job.pipeline.find_action(OverlayAction)
        self.assertIn(
            "persistent-nfs-overlay",
            [action.name for action in overlay.pipeline.actions],
        )

    def test_validate(self):
        try:
            allow_missing_path(
                self.job.pipeline.validate_actions, self, "qemu-system-x86_64"
            )
        except JobError as exc:
            self.fail(exc)
        for action in self.job.pipeline.actions:
            self.assertEqual([], action.errors)

    def test_available_architectures(self):
        job_ctx = {"arch": "unknown", "no_kvm": True}
        job = self.factory.create_job("qemu01", "sample_jobs/kvm.yaml", job_ctx)
        self.assertIsNotNone(job.device["available_architectures"])
        self.assertEqual(job.parameters["context"]["arch"], "unknown")
        self.assertRaises(JobError, job.pipeline.validate_actions)

    def test_overlay(self):
        overlay = self.job.pipeline.find_action(OverlayAction)
        self.assertIsNotNone(overlay)
        # these tests require that lava-dispatcher itself is installed,
        # not just running tests from a git clone
        self.assertTrue(os.path.exists(overlay.lava_test_dir))
        self.assertIsNot(overlay.lava_test_dir, "/")
        self.assertNotIn("lava_multi_node_test_dir", dir(overlay))
        self.assertNotIn("lava_multi_node_cache_file", dir(overlay))
        self.assertNotIn("lava_lmp_test_dir", dir(overlay))
        self.assertNotIn("lava_lmp_cache_file", dir(overlay))
        self.assertIsNotNone(
            overlay.parameters["deployment_data"]["lava_test_results_dir"]
        )
        self.assertIsNotNone(overlay.parameters["deployment_data"]["lava_test_sh_cmd"])
        self.assertEqual(overlay.parameters["deployment_data"]["distro"], "debian")
        self.assertIsNotNone(
            overlay.parameters["deployment_data"]["lava_test_results_part_attr"]
        )
        self.assertIsNotNone(glob.glob(os.path.join(overlay.lava_test_dir, "lava-*")))

    def test_boot(self):
        action = self.job.pipeline.find_action(BootQEMUImageAction)
        # get the action & populate it
        self.assertEqual(action.parameters["method"], "qemu")
        self.assertEqual(
            action.parameters["prompts"], ["linaro-test", "root@debian:~#"]
        )
        params = action.parameters.get("auto_login")

        if "login_prompt" in params:
            self.assertEqual(params["login_prompt"], "login:")
        if "username" in params:
            self.assertEqual(params["username"], "root")

    def test_testdefinitions(self):
        for action in self.job.pipeline.actions:
            if action.name == "test":
                # get the action & populate it
                self.assertEqual(len(action.parameters["definitions"]), 2)


class TestKVMPortable(LavaDispatcherTestCase):
    def setUp(self):
        super().setUp()
        factory = Factory()
        self.job = factory.create_kvm_job("sample_jobs/kvm-noos.yaml")

    def test_pipeline(self):
        description_ref = self.pipeline_reference("kvm-noos.yaml", job=self.job)
        self.assertEqual(description_ref, self.job.pipeline.describe())

    def test_validate(self):
        try:
            allow_missing_path(
                self.job.pipeline.validate_actions, self, "qemu-system-x86_64"
            )
        except JobError as exc:
            self.fail(exc)
        for action in self.job.pipeline.actions:
            self.assertEqual([], action.errors)


class TestKVMQcow2Deploy(LavaDispatcherTestCase):
    def setUp(self):
        super().setUp()
        factory = Factory()
        self.job = factory.create_kvm_job("sample_jobs/kvm-qcow2.yaml")

    def test_pipeline(self):
        description_ref = self.pipeline_reference("kvm-qcow2.yaml", job=self.job)
        self.assertEqual(description_ref, self.job.pipeline.describe())

    def test_validate(self):
        try:
            allow_missing_path(
                self.job.pipeline.validate_actions, self, "qemu-system-x86_64"
            )
        except JobError as exc:
            self.fail(exc)
        for action in self.job.pipeline.actions:
            self.assertEqual([], action.errors)


class TestKVMMultiTests(LavaDispatcherTestCase):
    def setUp(self):
        super().setUp()
        factory = Factory()
        self.job = factory.create_kvm_job("sample_jobs/kvm-multi.yaml")

    def test_pipeline(self):
        description_ref = self.pipeline_reference("kvm-multi.yaml", job=self.job)
        self.assertEqual(description_ref, self.job.pipeline.describe())


class TestKVMDownloadLocalDeploy(LavaDispatcherTestCase):
    def setUp(self):
        super().setUp()
        factory = Factory()
        self.job = factory.create_kvm_job("sample_jobs/kvm-local.yaml")

    def test_pipeline(self):
        description_ref = self.pipeline_reference("kvm-local.yaml", job=self.job)
        self.assertEqual(description_ref, self.job.pipeline.describe())


class TestKVMDeployOverlays(LavaDispatcherTestCase):
    def setUp(self):
        super().setUp()
        factory = Factory()
        self.job = factory.create_kvm_job("sample_jobs/kvm-overlays.yaml")

    def test_pipeline(self):
        description_ref = self.pipeline_reference("kvm-overlays.yaml", job=self.job)
        self.assertEqual(description_ref, self.job.pipeline.describe())


def prepare_test_connection(failure=False):
    if failure:
        logfile = os.path.join(os.path.dirname(__file__), "kernel-login-error.txt")
    else:
        logfile = os.path.join(os.path.dirname(__file__), "kernel-1.txt")
    if not os.path.exists(logfile):
        raise OSError("Missing test support file.")
    message_list = LinuxKernelMessages.get_init_prompts()
    return create_shell_session_cat_file(logfile, message_list)


class TestKVMInlineTestDeploy(LavaDispatcherTestCase):
    def setUp(self):
        super().setUp()
        self.factory = Factory()
        self.job = self.factory.create_kvm_job("sample_jobs/kvm-inline.yaml")

    def test_validate(self):
        try:
            self.job.pipeline.validate_actions()
        except JobError as exc:
            self.fail(exc)
        except InfrastructureError:
            pass
        for action in self.job.pipeline.actions:
            self.assertEqual([], action.errors)

    def test_extra_options(self):
        def override_qemu_extra(device_dict: dict[str, object]) -> None:
            device_dict["actions"]["boot"]["methods"]["qemu"]["parameters"]["extra"] = [
                "-smp",
                1,
                "-global",
                "virtio-blk-device.scsi=off",
                "device virtio-scsi-device,id=scsi",
                '--append "console=ttyAMA0 root=/dev/vda rw"',
            ]

        job = self.factory.create_job(
            "kvm01",
            "sample_jobs/kvm-inline.yaml",
            device_dict_preprocessor=override_qemu_extra,
        )
        job.validate()
        qemu = job.pipeline.find_action(CallQemuAction)
        self.assertIsInstance(qemu.sub_command, list)
        [self.assertIsInstance(item, str) for item in qemu.base_sub_command]
        self.assertIn("virtio-blk-device.scsi=off", qemu.base_sub_command)
        self.assertIn("1", qemu.base_sub_command)
        self.assertNotIn(1, qemu.base_sub_command)

    def test_pipeline(self):
        description_ref = self.pipeline_reference("kvm-inline.yaml", job=self.job)
        self.assertEqual(description_ref, self.job.pipeline.describe())

        self.assertEqual(len(self.job.pipeline.describe()), 4)

        inline_repo = self.job.pipeline.find_action(InlineRepoAction)
        # Test the InlineRepoAction directly
        location = mkdtemp()
        # other actions have not been run, so fake up
        inline_repo.set_namespace_data(
            action="test", label="results", key="lava_test_results_dir", value=location
        )
        inline_repo.set_namespace_data(
            action="test", label="test-definition", key="overlay_dir", value=location
        )
        inline_repo.set_namespace_data(
            action="test", label="shared", key="location", value=location
        )
        inline_repo.set_namespace_data(
            action="test", label="test-definiton", key="overlay_dir", value=location
        )

        inline_repo.run(None, None)
        yaml_file = os.path.join(
            location, "0/tests/0_smoke-tests-inline/inline/smoke-tests-basic.yaml"
        )
        self.assertTrue(os.path.exists(yaml_file))
        with open(yaml_file) as f_in:
            testdef = yaml_safe_load(f_in)
        expected_testdef = {
            "metadata": {
                "description": "Basic system test command for Linaro Ubuntu images",
                "devices": [
                    "panda",
                    "panda-es",
                    "arndale",
                    "vexpress-a9",
                    "vexpress-tc2",
                ],
                "format": "Lava-Test Test Definition 1.0",
                "name": "smoke-tests-basic",
                "os": ["ubuntu"],
                "scope": ["functional"],
            },
            "run": {
                "steps": [
                    "lava-test-case linux-INLINE-pwd --shell pwd",
                    "lava-test-case linux-INLINE-uname --shell uname -a",
                    "lava-test-case linux-INLINE-vmstat --shell vmstat",
                    "lava-test-case linux-INLINE-ifconfig --shell ifconfig -a",
                    "lava-test-case linux-INLINE-lscpu --shell lscpu",
                    "lava-test-case linux-INLINE-lsusb --shell lsusb",
                    "lava-test-case linux-INLINE-lsb_release --shell lsb_release -a",
                ]
            },
        }
        self.assertEqual(set(testdef), set(expected_testdef))


class TestKvmConnection(LavaDispatcherTestCase):
    def setUp(self):
        super().setUp()
        factory = Factory()
        self.job = factory.create_kvm_job("sample_jobs/qemu-reboot.yaml")
        self.job.logger = DummyLogger()

    def test_kvm_connection(self):
        self.job.validate()
        description_ref = self.pipeline_reference("qemu-reboot.yaml", job=self.job)
        self.assertEqual(description_ref, self.job.pipeline.describe())

        for call_qemu in self.job.pipeline.find_all_actions(CallQemuAction):
            self.assertEqual(call_qemu.session_class, QemuSession)


class TestAutoLogin(LavaDispatcherTestCase):
    def setUp(self):
        super().setUp()
        factory = Factory()
        self.job = factory.create_kvm_job("sample_jobs/kvm-inline.yaml")
        self.job.logger = DummyLogger()

    def test_autologin_prompt_patterns(self):
        self.assertEqual(len(self.job.pipeline.describe()), 4)
        self.job.validate()

        autologinaction = self.job.pipeline.find_action(AutoLoginAction)

        autologinaction.parameters.update(
            {
                "auto_login": {"login_prompt": "login:", "username": "root"},
                "prompts": ["root@debian:~#", pexpect_eof],
            }
        )
        # Propagate parameters update
        autologinaction.populate(autologinaction.parameters)

        # initialise the first Connection object, a command line shell
        shell_connection = prepare_test_connection()
        autologinaction.set_namespace_data(
            action="deploy-device-env",
            label="environment",
            key="line_separator",
            value="testsep",
        )

        # Test the AutoLoginAction directly
        with autologinaction.timeout(None, None) as max_end_time:
            conn = autologinaction.run(shell_connection, max_end_time)
        self.assertEqual(shell_connection.raw_connection.linesep, "testsep")

        self.assertIn("root@debian:~#", conn.prompt_str)
        conn.prompt_str = "root@stretch:"
        self.assertNotIn("root@debian:~#", conn.prompt_str)
        self.assertIn("root@stretch:", conn.prompt_str)

    def test_autologin_void_login_prompt(self):
        self.assertEqual(len(self.job.pipeline.describe()), 4)

        autologinaction = self.job.pipeline.find_action(AutoLoginAction)

        autologinaction.parameters.update(
            {
                "auto_login": {"login_prompt": "", "username": "root"},
                "prompts": ["root@debian:~#"],
            }
        )

        with self.assertRaises((JobError, InfrastructureError)) as check:
            self.job.validate()
            check_missing_path(self, check, "qemu-system-x86_64")

    def test_missing_autologin_void_prompts_list(self):
        self.assertEqual(len(self.job.pipeline.describe()), 4)

        autologinaction = self.job.pipeline.find_action(AutoLoginAction)

        autologinaction.parameters.update({"prompts": []})
        autologinaction.parameters.update({"method": "qemu"})

        with self.assertRaises((JobError, InfrastructureError)) as check:
            self.job.validate()
            check_missing_path(self, check, "qemu-system-x86_64")

    def test_missing_autologin_void_prompts_list_item(self):
        self.assertEqual(len(self.job.pipeline.describe()), 4)

        autologinaction = self.job.pipeline.find_action(AutoLoginAction)

        autologinaction.parameters.update({"prompts": [""]})

        with self.assertRaises((JobError, InfrastructureError)) as check:
            self.job.validate()
            check_missing_path(self, check, "qemu-system-x86_64")

    def test_missing_autologin_void_prompts_list_item2(self):
        self.assertEqual(len(self.job.pipeline.describe()), 4)

        autologinaction = self.job.pipeline.find_action(AutoLoginAction)

        autologinaction.parameters.update({"prompts": ["root@debian:~#", ""]})

        with self.assertRaises((JobError, InfrastructureError)) as check:
            self.job.validate()
            check_missing_path(self, check, "qemu-system-x86_64")

    def test_missing_autologin_prompts_list(self):
        self.assertEqual(len(self.job.pipeline.describe()), 4)

        autologinaction = self.job.pipeline.find_action(AutoLoginAction)

        autologinaction.parameters.update({"prompts": ["root@debian:~#", pexpect_eof]})
        autologinaction.parameters.update({"method": "qemu"})
        # Propagate parameters update
        autologinaction.populate(autologinaction.parameters)
        autologinaction.validate()

        # initialise the first Connection object, a command line shell
        shell_connection = prepare_test_connection()

        # Test the AutoLoginAction directly
        with autologinaction.timeout(None, None) as max_end_time:
            conn = autologinaction.run(shell_connection, max_end_time)

        self.assertIn("root@debian:~#", conn.prompt_str)

    def test_missing_autologin_void_prompts_str(self):
        self.assertEqual(len(self.job.pipeline.describe()), 4)

        autologinaction = self.job.pipeline.find_action(AutoLoginAction)

        autologinaction.parameters.update({"prompts": ""})

        with self.assertRaises((JobError, InfrastructureError)) as check:
            self.job.validate()
            check_missing_path(self, check, "qemu-system-x86_64")

    def test_missing_autologin_prompts_str(self):
        self.assertEqual(len(self.job.pipeline.describe()), 4)

        autologinaction = self.job.pipeline.find_action(AutoLoginAction)

        autologinaction.parameters.update({"prompts": ["root@debian:~#", pexpect_eof]})
        autologinaction.parameters.update({"method": "qemu"})
        # Propagate parameters update
        autologinaction.populate(autologinaction.parameters)
        autologinaction.validate()

        # initialise the first Connection object, a command line shell
        shell_connection = prepare_test_connection()

        # Test the AutoLoginAction directly
        with autologinaction.timeout(None, None) as max_end_time:
            conn = autologinaction.run(shell_connection, max_end_time)

        self.assertIn("root@debian:~#", conn.prompt_str)

    def test_autologin_login_incorrect(self):
        self.assertEqual(len(self.job.pipeline.describe()), 4)

        autologinaction = self.job.pipeline.find_action(AutoLoginAction)

        autologinaction.parameters.update({"prompts": ["root@debian:~#"]})
        autologinaction.parameters.update(
            {"auto_login": {"login_prompt": "debian login:", "username": "root"}}
        )
        autologinaction.parameters.update({"method": "qemu"})
        autologinaction.validate()

        loginaction = autologinaction.pipeline.find_action(LoginAction)
        loginaction.parameters = autologinaction.parameters

        # initialise the first Connection object, a command line shell
        shell_connection = prepare_test_connection(True)

        # Test the AutoLoginAction directly
        with self.assertRaisesRegex(
            JobError, "Login incorrect"
        ), autologinaction.timeout(None, None) as max_end_time:
            autologinaction.run(shell_connection, max_end_time)

        self.assertIn("root@debian:~#", shell_connection.prompt_str)
        self.assertIn("Login incorrect", shell_connection.prompt_str)
        self.assertIn("Login timed out", shell_connection.prompt_str)
        self.assertIn("2 retries failed for auto-login-action", autologinaction.errors)


class TestKvmGuest(LavaDispatcherTestCase):
    def setUp(self):
        super().setUp()
        factory = Factory()
        self.job = factory.create_kvm_job("sample_jobs/kvm-local.yaml")

    def test_guest_size(self):
        self.assertIn(
            "guest",
            self.job.device["actions"]["deploy"]["methods"]["image"]["parameters"],
        )
        self.assertEqual(
            512,
            self.job.device["actions"]["deploy"]["methods"]["image"]["parameters"][
                "guest"
            ]["size"],
        )


class TestKvmUefi(LavaDispatcherTestCase):
    def setUp(self):
        super().setUp()
        factory = Factory()
        self.job = factory.create_kvm_job("sample_jobs/kvm-uefi.yaml")

    @unittest.skipIf(
        infrastructure_error("qemu-system-x86_64"), "qemu-system-x86_64 not installed"
    )
    def test_uefi_path(self):
        downloaders = self.job.pipeline.find_all_actions(DownloaderAction)

        self.assertEqual(len(downloaders), 2)
        uefi_download = downloaders[0]
        image_download = downloaders[1]
        self.assertEqual(image_download.key, "disk1")
        uefi_dir = uefi_download.get_namespace_data(
            action="deployimages", label="image", key="uefi_dir"
        )
        self.assertIsNotNone(uefi_dir)
        self.assertTrue(
            os.path.exists(uefi_dir)
        )  # no download has taken place, but the directory needs to exist
        self.assertFalse(uefi_dir.endswith("bios-256k.bin"))

        execute = self.job.pipeline.find_action(CallQemuAction)
        self.job.validate()
        execute.run(None, 1)
        self.assertEqual(["-drive format=raw,file={disk1}"], execute.commands)
        self.assertEqual(
            [
                "/usr/bin/qemu-system-x86_64",
                "-nographic",
                "-net nic,model=virtio,macaddr=52:54:00:12:34:59 -net user",
                "-m 256",
                "-monitor none",
                "-drive format=raw,file=%s"
                % execute.get_namespace_data(
                    action="download-action", label="disk1", key="file"
                ),
                "-L",
                execute.get_namespace_data(
                    action="deployimages", label="image", key="uefi_dir"
                ),
                "-monitor",
                "none",
            ],
            execute.sub_command,
        )


class TestQemuNFS(LavaDispatcherTestCase):
    def setUp(self):
        super().setUp()
        factory = Factory()
        self.job = factory.create_job("kvm02", "sample_jobs/qemu-nfs.yaml")
        self.job.logger = DummyLogger()

    @unittest.skipIf(
        infrastructure_error("qemu-system-aarch64"), "qemu-system-arm not installed"
    )
    def test_qemu_nfs(self):
        self.assertIsNotNone(self.job)
        description_ref = self.pipeline_reference("qemu-nfs.yaml", job=self.job)
        self.assertEqual(description_ref, self.job.pipeline.describe())

        execute = self.job.pipeline.find_action(CallQemuAction)

        with patch(f"{execute.__module__}.SYS_CLASS_KVM", "/"):
            self.job.validate()
            execute.run(None, 1)
        self.assertEqual(["-kernel {kernel}", "-initrd {initrd}"], execute.commands)
        self.assertEqual(
            [
                "/usr/bin/qemu-system-x86_64",
                "-cpu host",
                "-enable-kvm",
                "-nographic",
                "-net nic,model=virtio,macaddr=52:54:00:12:34:59 -net tap",
                "-m 256",
                "-monitor none",
                "-smp",
                "1",
                "-kernel %s"
                % execute.get_namespace_data(
                    action="download-action", label="kernel", key="file"
                ),
                "-initrd %s"
                % execute.get_namespace_data(
                    action="download-action", label="initrd", key="file"
                ),
                "--append",
                '"console=ttyAMA0 root=/dev/nfs nfsroot=192.168.0.2:{NFSROOTFS},tcp,hard rw ip=dhcp"',
            ],
            execute.sub_command,
        )

        args = execute.methods["qemu-nfs"]["parameters"]["append"]["nfsrootargs"]
        self.assertIn("{NFS_SERVER_IP}", args)
        self.assertIn("{NFSROOTFS}", args)


class TestMonitor(LavaDispatcherTestCase):
    def setUp(self):
        super().setUp()
        factory = Factory()
        self.job = factory.create_kvm_job("sample_jobs/qemu-monitor.yaml")

    def test_qemu_monitor(self):
        self.assertIsNotNone(self.job)
        self.assertIsNotNone(self.job.pipeline)
        self.assertIsNotNone(self.job.pipeline.actions)
        self.job.validate()
