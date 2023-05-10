# Copyright (C) 2014 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later


import os
import unittest
from unittest.mock import MagicMock, patch

from lava_common.yaml import yaml_safe_dump, yaml_safe_load
from lava_dispatcher.action import Pipeline
from lava_dispatcher.actions.boot import BootloaderCommandOverlay
from lava_dispatcher.actions.boot.u_boot import (
    UBootAction,
    UBootCommandsAction,
    UBootSecondaryMedia,
)
from lava_dispatcher.actions.deploy.apply_overlay import CompressRamdisk
from lava_dispatcher.actions.deploy.tftp import TftpAction
from lava_dispatcher.device import NewDevice
from lava_dispatcher.job import Job
from lava_dispatcher.parser import JobParser
from lava_dispatcher.power import PDUReboot, ResetDevice
from lava_dispatcher.utils import filesystem
from lava_dispatcher.utils.network import dispatcher_ip
from lava_dispatcher.utils.strings import substitute
from tests.lava_dispatcher.test_basic import Factory, StdoutTestCase
from tests.utils import DummyLogger, infrastructure_error


class UBootFactory(Factory):
    """
    Not Model based, this is not a Django factory.
    Factory objects are dispatcher based classes, independent
    of any database objects.
    """

    def create_bbb_job(self, filename):
        return self.create_job("bbb-03.jinja2", filename)

    def create_x15_job(self, filename):
        return self.create_job("x15-01.jinja2", filename)

    def create_juno_job(self, filename):
        return self.create_job("juno-r2-01.jinja2", filename)

    def create_zcu102_job(self, filename):
        return self.create_job("zcu102.jinja2", filename)


class TestUbootAction(StdoutTestCase):
    def setUp(self):
        super().setUp()
        self.factory = UBootFactory()

    @unittest.skipIf(infrastructure_error("mkimage"), "u-boot-tools not installed")
    @patch(
        "lava_dispatcher.actions.deploy.tftp.which", return_value="/usr/bin/in.tftpd"
    )
    def test_simulated_action(self, which_mock):
        job = self.factory.create_bbb_job("sample_jobs/uboot-ramdisk.yaml")
        self.assertIsNotNone(job)

        # uboot and uboot-ramdisk have the same pipeline structure
        description_ref = self.pipeline_reference("uboot.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe())

        self.assertIsNone(job.validate())

    def test_action_parameters(self):
        job = self.factory.create_bbb_job("sample_jobs/uboot-ramdisk.yaml")
        self.assertIsNotNone(job.parameters)
        deploy = job.pipeline.actions[0]
        self.assertIsNone(deploy.parameters.get("parameters"))
        uboot = job.pipeline.actions[1]
        self.assertEqual(
            "reboot: Restarting system",  # modified in the job yaml
            uboot.parameters.get("parameters", {}).get(
                "shutdown-message", job.device.get_constant("shutdown-message")
            ),
        )
        self.assertIsInstance(uboot, UBootAction)
        retry = [
            action
            for action in uboot.pipeline.actions
            if action.name == "uboot-commands"
        ][0]
        self.assertEqual(
            "reboot: Restarting system",  # modified in the job yaml
            retry.parameters["parameters"].get(
                "shutdown-message", job.device.get_constant("shutdown-message")
            ),
        )
        self.assertIsInstance(retry, UBootCommandsAction)
        reset = retry.pipeline.actions[0]
        self.assertEqual(
            "reboot: Restarting system",  # modified in the job yaml
            reset.parameters["parameters"].get(
                "shutdown-message", job.device.get_constant("shutdown-message")
            ),
        )
        self.assertIsInstance(reset, ResetDevice)
        reboot = reset.pipeline.actions[0]
        self.assertEqual(
            "reboot: Restarting system",  # modified in the job yaml
            reboot.parameters["parameters"].get(
                "shutdown-message", job.device.get_constant("shutdown-message")
            ),
        )
        self.assertIsInstance(reboot, PDUReboot)
        self.assertIsNotNone(reboot.parameters.get("parameters"))
        self.assertEqual(
            "reboot: Restarting system",  # modified in the job yaml
            reboot.parameters["parameters"].get(
                "shutdown-message", job.device.get_constant("shutdown-message")
            ),
        )

    @patch(
        "lava_dispatcher.actions.deploy.tftp.which", return_value="/usr/bin/in.tftpd"
    )
    def test_tftp_pipeline(self, which_mock):
        job = self.factory.create_bbb_job("sample_jobs/uboot-ramdisk.yaml")
        self.assertEqual(
            [action.name for action in job.pipeline.actions],
            ["tftp-deploy", "uboot-action", "lava-test-retry", "finalize"],
        )
        tftp = [
            action for action in job.pipeline.actions if action.name == "tftp-deploy"
        ][0]
        self.assertTrue(
            tftp.get_namespace_data(action=tftp.name, label="tftp", key="ramdisk")
        )
        self.assertIsNotNone(tftp.pipeline)
        self.assertEqual(
            [action.name for action in tftp.pipeline.actions],
            [
                "download-retry",
                "download-retry",
                "download-retry",
                "prepare-tftp-overlay",
                "lxc-create-udev-rule-action",
                "deploy-device-env",
            ],
        )
        self.assertIn(
            "ramdisk",
            [action.key for action in tftp.pipeline.actions if hasattr(action, "key")],
        )
        self.assertIn(
            "kernel",
            [action.key for action in tftp.pipeline.actions if hasattr(action, "key")],
        )
        self.assertIn(
            "dtb",
            [action.key for action in tftp.pipeline.actions if hasattr(action, "key")],
        )
        self.assertNotIn("=", filesystem.tftpd_dir())
        job.validate()
        tftp.validate()
        self.assertEqual([], tftp.errors)

    @patch("lava_dispatcher.utils.shell.which", return_value="/usr/bin/in.tftpd")
    def test_device_bbb(self, which_mock):
        job = self.factory.create_bbb_job("sample_jobs/uboot.yaml")
        self.assertEqual(
            job.device["commands"]["connections"]["uart0"]["connect"],
            "telnet localhost 6000",
        )
        self.assertEqual(job.device["commands"].get("interrupt", " "), " ")
        methods = job.device["actions"]["boot"]["methods"]
        self.assertIn("u-boot", methods)
        self.assertEqual(
            methods["u-boot"]["parameters"].get("bootloader_prompt"), "U-Boot"
        )

    @unittest.skipIf(infrastructure_error("mkimage"), "u-boot-tools not installed")
    @patch(
        "lava_dispatcher.actions.deploy.tftp.which", return_value="/usr/bin/in.tftpd"
    )
    def test_uboot_action(self, which_mock):
        job = self.factory.create_bbb_job("sample_jobs/uboot-ramdisk.yaml")
        job.validate()
        self.assertEqual(job.pipeline.errors, [])
        self.assertIn("u-boot", job.device["actions"]["boot"]["methods"])
        params = job.device["actions"]["deploy"]["parameters"]
        self.assertIn("mkimage_arch", params)
        boot_message = params.get(
            "boot_message", job.device.get_constant("kernel-start-message")
        )
        self.assertIsNotNone(boot_message)
        for action in job.pipeline.actions:
            action.validate()
            if isinstance(action, UBootAction):
                self.assertIn("method", action.parameters)
                self.assertEqual("u-boot", action.parameters["method"])
                self.assertEqual(
                    "reboot: Restarting system",
                    action.parameters.get("parameters", {}).get(
                        "shutdown-message", job.device.get_constant("shutdown-message")
                    ),
                )
            if isinstance(action, TftpAction):
                self.assertIn("ramdisk", action.parameters)
                self.assertIn("kernel", action.parameters)
                self.assertIn("to", action.parameters)
                self.assertEqual("tftp", action.parameters["to"])
            if isinstance(action, CompressRamdisk):
                self.assertEqual(action.mkimage_arch, "arm")
            self.assertTrue(action.valid)

    @unittest.skipIf(infrastructure_error("lxc-start"), "lxc-start not installed")
    def test_fastboot_uboot(self):
        job = self.factory.create_x15_job("sample_jobs/x15-uboot.yaml")
        job.validate()
        description_ref = self.pipeline_reference("x15-uboot.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe())
        deploy = [
            action
            for action in job.pipeline.actions
            if action.name == "fastboot-deploy"
        ][0]
        enter = [
            action
            for action in deploy.pipeline.actions
            if action.name == "uboot-enter-fastboot"
        ][0]
        interrupt = [
            action
            for action in enter.pipeline.actions
            if action.name == "bootloader-interrupt"
        ][0]
        self.assertIsNotNone(interrupt.params)
        self.assertNotEqual(interrupt.params, {})
        self.assertEqual("u-boot", interrupt.method)

    @unittest.skipIf(infrastructure_error("lxc-start"), "lxc-start not installed")
    @patch("lava_dispatcher.utils.shell.which", return_value="/usr/bin/in.tftpd")
    def test_x15_uboot_nfs(self, which_mock):
        job = self.factory.create_x15_job("sample_jobs/x15-nfs.yaml")
        job.validate()
        description_ref = self.pipeline_reference("x15-nfs.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe())
        tftp_deploy = [
            action for action in job.pipeline.actions if action.name == "tftp-deploy"
        ][0]
        prepare = [
            action
            for action in tftp_deploy.pipeline.actions
            if action.name == "prepare-tftp-overlay"
        ][0]
        nfs = [
            action
            for action in prepare.pipeline.actions
            if action.name == "extract-nfsrootfs"
        ][0]
        self.assertIn("compression", nfs.parameters["nfsrootfs"])
        self.assertEqual(nfs.parameters["nfsrootfs"]["compression"], "gz")

    @patch("lava_dispatcher.utils.shell.which", return_value="/usr/bin/in.tftpd")
    def test_juno_uboot_nfs(self, which_mock):
        job = self.factory.create_juno_job("sample_jobs/juno-uboot-nfs.yaml")
        job.validate()
        description_ref = self.pipeline_reference("juno-uboot-nfs.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe())

    @patch("lava_dispatcher.utils.shell.which", return_value="/usr/bin/in.tftpd")
    def test_overlay_action(self, which_mock):
        parameters = {
            "dispatcher": {},  # fake dispatcher parameter. Normally added by parser
            "device_type": "beaglebone-black",
            "job_name": "uboot-pipeline",
            "job_timeout": "15m",
            "action_timeout": "5m",
            "priority": "medium",
            "actions": {
                "boot": {
                    "namespace": "common",
                    "method": "u-boot",
                    "commands": "ramdisk",
                    "prompts": ["linaro-test", "root@debian:~#"],
                },
                "deploy": {
                    "namespace": "common",
                    "ramdisk": {"url": "initrd.gz", "compression": "gz"},
                    "kernel": {"url": "zImage", "type": "zimage"},
                    "dtb": {"url": "broken.dtb"},
                    "tee": {"url": "uTee"},
                },
            },
        }
        data = yaml_safe_load(Factory().create_device("bbb-01.jinja2")[0])
        device = NewDevice(data)
        job = Job(4212, parameters, None)
        job.device = device
        pipeline = Pipeline(job=job, parameters=parameters["actions"]["boot"])
        job.pipeline = pipeline
        overlay = BootloaderCommandOverlay()
        connection = MagicMock()
        connection.timeout = MagicMock()
        pipeline.add_action(overlay)
        overlay.set_namespace_data(
            action="uboot-prepare-kernel",
            label="bootcommand",
            key="bootcommand",
            value="bootz",
        )
        overlay.validate()
        overlay.run(connection, 100)
        ip_addr = dispatcher_ip(None)
        parsed = []
        kernel_addr = job.device["parameters"][overlay.bootcommand]["ramdisk"]
        ramdisk_addr = job.device["parameters"][overlay.bootcommand]["ramdisk"]
        dtb_addr = job.device["parameters"][overlay.bootcommand]["dtb"]
        tee_addr = job.device["parameters"][overlay.bootcommand]["tee"]
        kernel = parameters["actions"]["deploy"]["kernel"]["url"]
        ramdisk = parameters["actions"]["deploy"]["ramdisk"]["url"]
        dtb = parameters["actions"]["deploy"]["dtb"]["url"]
        tee = parameters["actions"]["deploy"]["tee"]["url"]

        substitution_dictionary = {
            "{SERVER_IP}": ip_addr,
            # the addresses need to be hexadecimal
            "{KERNEL_ADDR}": kernel_addr,
            "{DTB_ADDR}": dtb_addr,
            "{RAMDISK_ADDR}": ramdisk_addr,
            "{TEE_ADDR}": tee_addr,
            "{BOOTX}": "%s %s %s %s"
            % (overlay.bootcommand, kernel_addr, ramdisk_addr, dtb_addr),
            "{RAMDISK}": ramdisk,
            "{KERNEL}": kernel,
            "{DTB}": dtb,
            "{TEE}": tee,
        }
        params = device["actions"]["boot"]["methods"]
        params["u-boot"]["ramdisk"]["commands"] = substitute(
            params["u-boot"]["ramdisk"]["commands"], substitution_dictionary
        )

        commands = params["u-boot"]["ramdisk"]["commands"]
        self.assertIs(type(commands), list)
        self.assertIn("tftp 0x83000000 zImage", commands)
        self.assertIn("tftp 0x83000000 initrd.gz", commands)
        self.assertIn("setenv initrd_size ${filesize}", commands)
        self.assertIn("tftp 0x88000000 broken.dtb", commands)
        self.assertIn("tftp 0x83000000 uTee", commands)
        self.assertNotIn("setenv kernel_addr_r '{KERNEL_ADDR}'", commands)
        self.assertNotIn("setenv initrd_addr_r '{RAMDISK_ADDR}'", commands)
        self.assertNotIn("setenv fdt_addr_r '{DTB_ADDR}'", commands)

        for line in params["u-boot"]["ramdisk"]["commands"]:
            line = line.replace("{SERVER_IP}", ip_addr)
            # the addresses need to be hexadecimal
            line = line.replace("{KERNEL_ADDR}", kernel_addr)
            line = line.replace("{DTB_ADDR}", dtb_addr)
            line = line.replace("{RAMDISK_ADDR}", ramdisk_addr)
            line = line.replace(
                "{BOOTX}",
                "%s %s %s %s"
                % (overlay.bootcommand, kernel_addr, ramdisk_addr, dtb_addr),
            )
            line = line.replace("{RAMDISK}", ramdisk)
            line = line.replace("{KERNEL}", kernel)
            line = line.replace("{DTB}", dtb)
            parsed.append(line)
        self.assertNotIn("setenv kernel_addr_r '{KERNEL_ADDR}'", parsed)
        self.assertNotIn("setenv initrd_addr_r '{RAMDISK_ADDR}'", parsed)
        self.assertNotIn("setenv fdt_addr_r '{DTB_ADDR}'", parsed)

    @patch("lava_dispatcher.utils.shell.which", return_value="/usr/bin/in.tftpd")
    def test_overlay_noramdisk(self, which_mock):
        parameters = {
            "dispatcher": {},  # fake dispatcher parameter. Normally added by parser
            "device_type": "beaglebone-black",
            "job_name": "uboot-pipeline",
            "job_timeout": "15m",
            "action_timeout": "5m",
            "priority": "medium",
            "actions": {
                "boot": {
                    "namespace": "common",
                    "method": "u-boot",
                    "commands": "ramdisk",
                    "prompts": ["linaro-test", "root@debian:~#"],
                },
                "deploy": {
                    "namespace": "common",
                    "ramdisk": {"url": ""},
                    "kernel": {"url": "zImage", "type": "zimage"},
                    "dtb": {"url": "broken.dtb"},
                },
            },
        }
        data = yaml_safe_load(Factory().create_device("bbb-01.jinja2")[0])
        device = NewDevice(data)
        ip_addr = dispatcher_ip(None)
        parsed = []
        kernel_addr = "0x83000000"
        ramdisk_addr = "0x83000000"
        dtb_addr = "0x88000000"
        kernel = parameters["actions"]["deploy"]["kernel"]["url"]
        ramdisk = parameters["actions"]["deploy"]["ramdisk"]["url"]
        dtb = parameters["actions"]["deploy"]["dtb"]["url"]

        substitution_dictionary = {
            "{SERVER_IP}": ip_addr,
            # the addresses need to be hexadecimal
            "{KERNEL_ADDR}": kernel_addr,
            "{DTB_ADDR}": dtb_addr,
            "{RAMDISK_ADDR}": ramdisk_addr,
            "{BOOTX}": "%s %s %s %s" % ("bootz", kernel_addr, ramdisk_addr, dtb_addr),
            "{RAMDISK}": ramdisk,
            "{KERNEL}": kernel,
            "{DTB}": dtb,
        }
        params = device["actions"]["boot"]["methods"]
        params["u-boot"]["ramdisk"]["commands"] = substitute(
            params["u-boot"]["ramdisk"]["commands"], substitution_dictionary, drop=True
        )

        commands = params["u-boot"]["ramdisk"]["commands"]
        self.assertIs(type(commands), list)
        self.assertIn("tftp 0x83000000 zImage", commands)
        self.assertNotIn("tftp 0x83000000 {RAMDISK}", commands)
        self.assertNotIn("tftp 0x83000000 ", commands)
        self.assertIn("setenv initrd_size ${filesize}", commands)
        self.assertIn("tftp 0x88000000 broken.dtb", commands)
        self.assertNotIn("setenv kernel_addr_r '{KERNEL_ADDR}'", commands)
        self.assertNotIn("setenv initrd_addr_r '{RAMDISK_ADDR}'", commands)
        self.assertNotIn("setenv fdt_addr_r '{DTB_ADDR}'", commands)

    @patch("lava_dispatcher.utils.shell.which", return_value="/usr/bin/in.tftpd")
    def test_overlay_notee(self, which_mock):
        parameters = {
            "dispatcher": {},  # fake dispatcher parameter. Normally added by parser
            "device_type": "beaglebone-black",
            "job_name": "uboot-pipeline",
            "job_timeout": "15m",
            "action_timeout": "5m",
            "priority": "medium",
            "actions": {
                "boot": {
                    "namespace": "common",
                    "method": "u-boot",
                    "commands": "ramdisk",
                    "prompts": ["linaro-test", "root@debian:~#"],
                },
                "deploy": {
                    "namespace": "common",
                    "ramdisk": {"url": "initrd.gz", "compression": "gz"},
                    "kernel": {"url": "zImage", "type": "zimage"},
                    "dtb": {"url": "broken.dtb"},
                    "tee": {"url": ""},
                },
            },
        }
        data = yaml_safe_load(Factory().create_device("bbb-01.jinja2")[0])
        device = NewDevice(data)
        ip_addr = dispatcher_ip(None)
        parsed = []
        kernel_addr = "0x83000000"
        ramdisk_addr = "0x83000000"
        dtb_addr = "0x88000000"
        tee_adr = "0x83000000"
        kernel = parameters["actions"]["deploy"]["kernel"]["url"]
        ramdisk = parameters["actions"]["deploy"]["ramdisk"]["url"]
        dtb = parameters["actions"]["deploy"]["dtb"]["url"]
        tee = parameters["actions"]["deploy"]["tee"]["url"]

        substitution_dictionary = {
            "{SERVER_IP}": ip_addr,
            # the addresses need to be hexadecimal
            "{KERNEL_ADDR}": kernel_addr,
            "{DTB_ADDR}": dtb_addr,
            "{RAMDISK_ADDR}": ramdisk_addr,
            "{BOOTX}": "%s %s %s %s" % ("bootz", kernel_addr, ramdisk_addr, dtb_addr),
            "{RAMDISK}": ramdisk,
            "{KERNEL}": kernel,
            "{DTB}": dtb,
            "{TEE}": tee,
        }
        params = device["actions"]["boot"]["methods"]
        params["u-boot"]["ramdisk"]["commands"] = substitute(
            params["u-boot"]["ramdisk"]["commands"], substitution_dictionary, drop=True
        )
        commands = params["u-boot"]["ramdisk"]["commands"]
        self.assertIs(type(commands), list)
        self.assertIn("tftp 0x83000000 zImage", commands)
        self.assertNotIn("tftp 0x83000000 {TEE}", commands)
        self.assertNotIn("tftp 0x83000000 ", commands)
        self.assertIn("setenv initrd_size ${filesize}", commands)
        self.assertIn("tftp 0x88000000 broken.dtb", commands)
        self.assertNotIn("setenv kernel_addr_r '{KERNEL_ADDR}'", commands)
        self.assertNotIn("setenv initrd_addr_r '{RAMDISK_ADDR}'", commands)
        self.assertNotIn("setenv fdt_addr_r '{DTB_ADDR}'", commands)

    @patch(
        "lava_dispatcher.actions.deploy.tftp.which", return_value="/usr/bin/in.tftpd"
    )
    def test_boot_commands(self, which_mock):
        job = self.factory.create_bbb_job(
            "sample_jobs/uboot-ramdisk-inline-commands.yaml"
        )
        job.validate()
        uboot = [
            action for action in job.pipeline.actions if action.name == "uboot-action"
        ][0]
        overlay = [
            action
            for action in uboot.pipeline.actions
            if action.name == "bootloader-overlay"
        ][0]
        self.assertEqual(
            overlay.commands,
            ["a list", "of commands", "with a {KERNEL_ADDR} substitution"],
        )

    @unittest.skipIf(infrastructure_error("nbd-server"), "nbd-server not installed")
    def test_nbd_boot(self):
        job = self.factory.create_bbb_job("sample_jobs/bbb-initrd-nbd.yaml")
        job.validate()
        self.assertEqual(job.pipeline.errors, [])
        description_ref = self.pipeline_reference("bbb-initrd-nbd.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe())
        # Fixme: more asserts
        self.assertIn("u-boot", job.device["actions"]["boot"]["methods"])
        params = job.device["actions"]["deploy"]["parameters"]
        self.assertIsNotNone(params)
        for action in job.pipeline.actions:
            action.validate()
            if isinstance(action, UBootAction):
                self.assertIn("method", action.parameters)
                self.assertEqual("u-boot", action.parameters["method"])
            elif isinstance(action, TftpAction):
                self.assertIn("initrd", action.parameters)
                self.assertIn("kernel", action.parameters)
                self.assertIn("nbdroot", action.parameters)
                self.assertIn("to", action.parameters)
                self.assertEqual("nbd", action.parameters["to"])
            self.assertTrue(action.valid)
        uboot = [
            action for action in job.pipeline.actions if action.name == "uboot-action"
        ][0]
        overlay = [
            action
            for action in uboot.pipeline.actions
            if action.name == "bootloader-overlay"
        ][0]
        for setenv in overlay.commands:
            if "setenv nbdbasekargs" in setenv:
                self.assertIn("rw", setenv.split("'")[1])
                self.assertIn("${extraargs}", setenv.split("'")[1])
                self.assertEqual(3, len(setenv.split("'")))

    @patch(
        "lava_dispatcher.actions.deploy.tftp.which", return_value="/usr/bin/in.tftpd"
    )
    def test_transfer_media(self, which_mock):
        """
        Test adding the overlay to existing rootfs
        """
        job = self.factory.create_bbb_job(
            "sample_jobs/uboot-ramdisk-inline-commands.yaml"
        )
        job.validate()
        description_ref = self.pipeline_reference(
            "uboot-ramdisk-inline-commands.yaml", job=job
        )
        self.assertEqual(description_ref, job.pipeline.describe())
        uboot = [
            action for action in job.pipeline.actions if action.name == "uboot-action"
        ][0]
        retry = [
            action
            for action in uboot.pipeline.actions
            if action.name == "uboot-commands"
        ][0]
        transfer = [
            action
            for action in retry.pipeline.actions
            if action.name == "overlay-unpack"
        ][0]
        self.assertIn("transfer_overlay", transfer.parameters)
        self.assertIn("download_command", transfer.parameters["transfer_overlay"])
        self.assertIn("unpack_command", transfer.parameters["transfer_overlay"])

    @patch(
        "lava_dispatcher.actions.boot.dispatcher_ip",
        return_value="foo",
    )
    @patch(
        "lava_dispatcher.actions.boot.OverlayUnpack.get_namespace_data",
        return_value="/var/lib/lava/dispatcher/tmp/bar",
    )
    def test_transfer_media_cmd(self, get_namespace_data, dispatcher_ip_mock):
        """
        Test command used to add the overlay to existing rootfs
        """
        job = self.factory.create_bbb_job(
            "sample_jobs/uboot-ramdisk-inline-commands.yaml"
        )
        uboot = [
            action for action in job.pipeline.actions if action.name == "uboot-action"
        ][0]
        retry = [
            action
            for action in uboot.pipeline.actions
            if action.name == "uboot-commands"
        ][0]

        transfer = [
            action
            for action in retry.pipeline.actions
            if action.name == "overlay-unpack"
        ][0]

        class Connection:
            def __init__(self):
                self.cmds = []

            def sendline(self, cmd, delay):
                self.cmds.append(cmd)

            def wait(self):
                pass

        # http method
        http_transfer_connection = Connection()
        transfer.run(http_transfer_connection, 0)
        self.assertEqual(
            http_transfer_connection.cmds,
            [
                "rm bar",
                "wget -S --progress=dot:giga http://foo/tmp/bar",
                "tar -C / -xzf bar",
            ],
        )

        # nfs method
        self.assertIn("transfer_overlay", transfer.parameters)
        transfer.parameters["transfer_overlay"]["transfer_method"] = "nfs"
        transfer.parameters["transfer_overlay"]["download_command"] = "fs-nfs3"
        transfer.parameters["transfer_overlay"]["unpack_command"] = "cp -rf"
        nfs_transfer_connection = Connection()
        transfer.run(nfs_transfer_connection, 0)
        self.assertEqual(
            nfs_transfer_connection.cmds,
            [
                "mkdir -p /bar; fs-nfs3 foo:/var/lib/lava/dispatcher/tmp/bar /bar",
                "cp -rf /bar/* /; umount /bar; rm -fr /bar",
            ],
        )

    @patch(
        "lava_dispatcher.actions.deploy.tftp.which", return_value="/usr/bin/in.tftpd"
    )
    def test_download_action(self, which_mock):
        job = self.factory.create_bbb_job("sample_jobs/uboot.yaml")
        for action in job.pipeline.actions:
            action.validate()
            self.assertTrue(action.valid)
        job.validate()
        self.assertEqual(job.pipeline.errors, [])
        deploy = None
        overlay = None
        extract = None
        for action in job.pipeline.actions:
            if action.name == "tftp-deploy":
                deploy = action
        if deploy:
            for action in deploy.pipeline.actions:
                if action.name == "prepare-tftp-overlay":
                    overlay = action
        if overlay:
            for action in overlay.pipeline.actions:
                if action.name == "extract-nfsrootfs":
                    extract = action
        test_dir = overlay.get_namespace_data(
            action="test", label="results", key="lava_test_results_dir"
        )
        self.assertIsNotNone(test_dir)
        self.assertIn("/lava-", test_dir)
        self.assertIsNotNone(extract)
        self.assertEqual(extract.timeout.duration, 240)

    @patch(
        "lava_dispatcher.actions.deploy.tftp.which", return_value="/usr/bin/in.tftpd"
    )
    def test_reset_actions(self, which_mock):
        job = self.factory.create_bbb_job("sample_jobs/uboot.yaml")
        uboot_action = None
        uboot_commands = None
        reset_action = None
        for action in job.pipeline.actions:
            action.validate()
            self.assertTrue(action.valid)
            if action.name == "uboot-action":
                uboot_action = action
        names = [r_action.name for r_action in uboot_action.pipeline.actions]
        self.assertIn("connect-device", names)
        self.assertIn("uboot-commands", names)
        for action in uboot_action.pipeline.actions:
            if action.name == "uboot-commands":
                uboot_commands = action
        names = [r_action.name for r_action in uboot_commands.pipeline.actions]
        self.assertIn("reset-device", names)
        self.assertIn("bootloader-interrupt", names)
        self.assertIn("expect-shell-connection", names)
        self.assertIn("bootloader-commands", names)
        for action in uboot_commands.pipeline.actions:
            if action.name == "reset-device":
                reset_action = action
        names = [r_action.name for r_action in reset_action.pipeline.actions]
        self.assertIn("pdu-reboot", names)

    @patch(
        "lava_dispatcher.actions.deploy.tftp.which", return_value="/usr/bin/in.tftpd"
    )
    def test_secondary_media(self, which_mock):
        """
        Test UBootSecondaryMedia validation
        """
        job_parser = JobParser()
        (rendered, _) = self.factory.create_device("cubie1.jinja2")
        cubie = NewDevice(yaml_safe_load(rendered))
        sample_job_file = os.path.join(
            os.path.dirname(__file__), "sample_jobs/cubietruck-removable.yaml"
        )
        sample_job_data = open(sample_job_file)
        job = job_parser.parse(sample_job_data, cubie, 4212, None, "")
        job.logger = DummyLogger()
        job.validate()
        sample_job_data.close()
        uboot_action = [
            action
            for action in job.pipeline.actions
            if action.name == "uboot-action"
            and action.parameters["namespace"] == "boot2"
        ][0]
        u_boot_media = [
            action
            for action in uboot_action.pipeline.actions
            if action.name == "uboot-from-media"
            and action.parameters["namespace"] == "boot2"
        ][0]
        self.assertIsInstance(u_boot_media, UBootSecondaryMedia)
        self.assertEqual([], u_boot_media.errors)
        self.assertEqual(
            u_boot_media.parameters["kernel"], "/boot/vmlinuz-3.16.0-4-armmp-lpae"
        )
        self.assertEqual(
            u_boot_media.parameters["kernel"],
            u_boot_media.get_namespace_data(
                action="download-action", label="file", key="kernel"
            ),
        )
        self.assertEqual(
            u_boot_media.parameters["ramdisk"],
            u_boot_media.get_namespace_data(
                action="compress-ramdisk", label="file", key="ramdisk"
            ),
        )
        self.assertEqual(
            u_boot_media.parameters["dtb"],
            u_boot_media.get_namespace_data(
                action="download-action", label="file", key="dtb"
            ),
        )
        # use the base class name so that uboot-from-media can pick up the value reliably.
        self.assertEqual(
            u_boot_media.parameters["root_uuid"],
            u_boot_media.get_namespace_data(
                action="bootloader-from-media", label="uuid", key="root"
            ),
        )
        device = u_boot_media.get_namespace_data(
            action="storage-deploy", label="u-boot", key="device"
        )
        self.assertIsNotNone(device)
        part_reference = "%s:%s" % (
            job.device["parameters"]["media"]["usb"][device]["device_id"],
            u_boot_media.parameters["boot_part"],
        )
        self.assertEqual(
            part_reference,
            u_boot_media.get_namespace_data(
                action=u_boot_media.name, label="uuid", key="boot_part"
            ),
        )
        self.assertEqual(part_reference, "0:1")

    @patch(
        "lava_dispatcher.actions.deploy.tftp.which", return_value="/usr/bin/in.tftpd"
    )
    def test_prefix(self, which_mock):
        job = self.factory.create_bbb_job("sample_jobs/bbb-skip-install.yaml")
        job.validate()
        tftp_deploy = [
            action for action in job.pipeline.actions if action.name == "tftp-deploy"
        ][0]
        prepare = [
            action
            for action in tftp_deploy.pipeline.actions
            if action.name == "prepare-tftp-overlay"
        ][0]
        nfs = [
            action
            for action in prepare.pipeline.actions
            if action.name == "extract-nfsrootfs"
        ][0]
        self.assertIn("prefix", nfs.parameters["nfsrootfs"])
        self.assertEqual(nfs.parameters["nfsrootfs"]["prefix"], "jessie/")
        self.assertEqual(nfs.param_key, "nfsrootfs")

    @patch(
        "lava_dispatcher.actions.deploy.tftp.which", return_value="/usr/bin/in.tftpd"
    )
    def test_zcu102(self, which_mock):
        job = self.factory.create_zcu102_job("sample_jobs/zcu102-ramdisk.yaml")
        job.validate()
        self.assertEqual(job.pipeline.errors, [])
        description_ref = self.pipeline_reference("zcu102-ramdisk.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe())

    @unittest.skipIf(infrastructure_error("lxc-start"), "lxc-start not installed")
    def test_imx8m(self):
        job = self.factory.create_job(
            "imx8mq-evk-01.jinja2", "sample_jobs/imx8mq-evk.yaml"
        )
        self.assertIsNotNone(job)
        job.validate()
        self.assertEqual(job.pipeline.errors, [])
        description_ref = self.pipeline_reference("imx8mq-evk.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe())
        deploy = [
            action
            for action in job.pipeline.actions
            if action.name == "fastboot-deploy"
        ][0]
        fastboot = [
            action
            for action in deploy.pipeline.actions
            if action.name == "uboot-enter-fastboot"
        ][0]
        bootloader = [
            action
            for action in fastboot.pipeline.actions
            if action.name == "bootloader-interrupt"
        ][0]
        self.assertEqual("u-boot", bootloader.method)


class TestKernelConversion(StdoutTestCase):
    def setUp(self):
        data = yaml_safe_load(Factory().create_device("bbb-01.jinja2")[0])
        self.device = NewDevice(data)
        bbb_yaml = os.path.join(
            os.path.dirname(__file__), "sample_jobs/uboot-ramdisk.yaml"
        )
        with open(bbb_yaml) as sample_job_data:
            self.base_data = yaml_safe_load(sample_job_data)
        self.deploy_block = [
            block for block in self.base_data["actions"] if "deploy" in block
        ][0]["deploy"]
        self.boot_block = [
            block for block in self.base_data["actions"] if "boot" in block
        ][0]["boot"]
        self.parser = JobParser()

    @patch(
        "lava_dispatcher.actions.deploy.tftp.which", return_value="/usr/bin/in.tftpd"
    )
    def test_zimage_bootz(self, which_mock):
        self.deploy_block["kernel"]["type"] = "zimage"
        job = self.parser.parse(
            yaml_safe_dump(self.base_data), self.device, 4212, None, ""
        )
        job.logger = DummyLogger()
        job.validate()
        deploy = [
            action for action in job.pipeline.actions if action.name == "tftp-deploy"
        ][0]
        overlay = [
            action
            for action in deploy.pipeline.actions
            if action.name == "prepare-tftp-overlay"
        ][0]
        prepare = [
            action
            for action in overlay.pipeline.actions
            if action.name == "prepare-kernel"
        ][0]
        uboot_prepare = [
            action
            for action in prepare.pipeline.actions
            if action.name == "uboot-prepare-kernel"
        ][0]
        self.assertEqual("zimage", uboot_prepare.kernel_type)
        self.assertEqual("bootz", uboot_prepare.bootcommand)
        self.assertFalse(uboot_prepare.mkimage_conversion)

    @patch(
        "lava_dispatcher.actions.deploy.tftp.which", return_value="/usr/bin/in.tftpd"
    )
    def test_image(self, which_mock):
        self.deploy_block["kernel"]["type"] = "image"
        job = self.parser.parse(
            yaml_safe_dump(self.base_data), self.device, 4212, None, ""
        )
        job.logger = DummyLogger()
        job.validate()
        deploy = [
            action for action in job.pipeline.actions if action.name == "tftp-deploy"
        ][0]
        overlay = [
            action
            for action in deploy.pipeline.actions
            if action.name == "prepare-tftp-overlay"
        ][0]
        prepare = [
            action
            for action in overlay.pipeline.actions
            if action.name == "prepare-kernel"
        ][0]
        uboot_prepare = [
            action
            for action in prepare.pipeline.actions
            if action.name == "uboot-prepare-kernel"
        ][0]
        self.assertEqual("image", uboot_prepare.kernel_type)
        # bbb-01.yaml does not contain booti parameters, try to convert to a uImage
        self.assertEqual("bootm", uboot_prepare.bootcommand)
        self.assertTrue(uboot_prepare.mkimage_conversion)

    @patch(
        "lava_dispatcher.actions.deploy.tftp.which", return_value="/usr/bin/in.tftpd"
    )
    def test_uimage(self, which_mock):
        self.deploy_block["kernel"]["type"] = "uimage"
        job = self.parser.parse(
            yaml_safe_dump(self.base_data), self.device, 4212, None, ""
        )
        job.logger = DummyLogger()
        job.validate()
        deploy = [
            action for action in job.pipeline.actions if action.name == "tftp-deploy"
        ][0]
        overlay = [
            action
            for action in deploy.pipeline.actions
            if action.name == "prepare-tftp-overlay"
        ][0]
        prepare = [
            action
            for action in overlay.pipeline.actions
            if action.name == "prepare-kernel"
        ][0]
        uboot_prepare = [
            action
            for action in prepare.pipeline.actions
            if action.name == "uboot-prepare-kernel"
        ][0]
        self.assertEqual("uimage", uboot_prepare.kernel_type)
        self.assertEqual("bootm", uboot_prepare.bootcommand)
        self.assertFalse(uboot_prepare.mkimage_conversion)

    @patch(
        "lava_dispatcher.actions.deploy.tftp.which", return_value="/usr/bin/in.tftpd"
    )
    def test_zimage_nobootz(self, which_mock):
        print(which_mock)
        # drop bootz from the device for this part of the test
        del self.device["parameters"]["bootz"]
        self.deploy_block["kernel"]["type"] = "zimage"
        job = self.parser.parse(
            yaml_safe_dump(self.base_data), self.device, 4212, None, ""
        )
        job.logger = DummyLogger()
        job.validate()
        deploy = [
            action for action in job.pipeline.actions if action.name == "tftp-deploy"
        ][0]
        overlay = [
            action
            for action in deploy.pipeline.actions
            if action.name == "prepare-tftp-overlay"
        ][0]
        prepare = [
            action
            for action in overlay.pipeline.actions
            if action.name == "prepare-kernel"
        ][0]
        uboot_prepare = [
            action
            for action in prepare.pipeline.actions
            if action.name == "uboot-prepare-kernel"
        ][0]
        self.assertEqual("zimage", uboot_prepare.kernel_type)
        self.assertEqual("bootm", uboot_prepare.bootcommand)
        self.assertTrue(uboot_prepare.mkimage_conversion)


class TestOverlayCommands(StdoutTestCase):
    def setUp(self):
        super().setUp()
        self.factory = UBootFactory()

    def test_combined_ramdisk_nfs(self):
        job = self.factory.create_bbb_job("sample_jobs/bbb-ramdisk-nfs.yaml")
        tftp_deploy = [
            action for action in job.pipeline.actions if action.name == "tftp-deploy"
        ][0]
        prepare = [
            action
            for action in tftp_deploy.pipeline.actions
            if action.name == "prepare-tftp-overlay"
        ][0]
        nfs = [
            action
            for action in prepare.pipeline.actions
            if action.name == "extract-nfsrootfs"
        ][0]
        ramdisk = [
            action
            for action in prepare.pipeline.actions
            if action.name == "extract-overlay-ramdisk"
        ][0]
        modules = [
            action
            for action in prepare.pipeline.actions
            if action.name == "extract-modules"
        ][0]
        overlay = [
            action
            for action in prepare.pipeline.actions
            if action.name == "apply-overlay-tftp"
        ][0]
        self.assertIsNotNone(ramdisk.parameters.get("ramdisk"))
        self.assertIsNotNone(ramdisk.parameters["ramdisk"].get("url"))
        self.assertIsNotNone(ramdisk.parameters["ramdisk"].get("compression"))
        self.assertTrue(ramdisk.parameters["ramdisk"].get("install_modules", True))
        self.assertTrue(ramdisk.parameters["ramdisk"].get("install_overlay", True))
        self.assertIsNotNone(modules.parameters.get("ramdisk"))
        self.assertIsNotNone(modules.parameters.get("nfsrootfs"))
        self.assertIsNotNone(nfs.parameters.get("nfsrootfs"))
        self.assertIsNotNone(overlay.parameters.get("nfsrootfs"))
        self.assertIsNotNone(overlay.parameters.get("ramdisk"))

    def test_ramdisk_nfs_nomodules(self):
        job = self.factory.create_bbb_job("sample_jobs/bbb-uinitrd-nfs.yaml")
        tftp_deploy = [
            action for action in job.pipeline.actions if action.name == "tftp-deploy"
        ][0]
        prepare = [
            action
            for action in tftp_deploy.pipeline.actions
            if action.name == "prepare-tftp-overlay"
        ][0]
        nfs = [
            action
            for action in prepare.pipeline.actions
            if action.name == "extract-nfsrootfs"
        ][0]
        ramdisk = [
            action
            for action in prepare.pipeline.actions
            if action.name == "extract-overlay-ramdisk"
        ][0]
        modules = [
            action
            for action in prepare.pipeline.actions
            if action.name == "extract-modules"
        ][0]
        overlay = [
            action
            for action in prepare.pipeline.actions
            if action.name == "apply-overlay-tftp"
        ][0]
        self.assertIsNotNone(ramdisk.parameters.get("ramdisk"))
        self.assertIsNotNone(ramdisk.parameters["ramdisk"].get("url"))
        self.assertIsNone(ramdisk.parameters["ramdisk"].get("compression"))
        self.assertFalse(ramdisk.parameters["ramdisk"].get("install_overlay", True))
        self.assertIsNotNone(modules.parameters.get("ramdisk"))
        self.assertIsNotNone(modules.parameters.get("nfsrootfs"))
        self.assertIsNotNone(nfs.parameters.get("nfsrootfs"))
        self.assertIsNotNone(overlay.parameters.get("nfsrootfs"))
        self.assertIsNotNone(overlay.parameters.get("ramdisk"))
