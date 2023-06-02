# Copyright (C) 2014-2019 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later


import os
import unittest
from unittest.mock import patch

import lava_dispatcher
from lava_common.exceptions import InfrastructureError, JobError
from lava_common.timeout import Timeout
from lava_common.yaml import yaml_safe_load
from lava_dispatcher.actions.boot.ssh import SchrootAction
from lava_dispatcher.protocols.multinode import MultinodeProtocol
from lava_dispatcher.utils.filesystem import check_ssh_identity_file
from tests.lava_dispatcher.test_basic import Factory, StdoutTestCase
from tests.utils import infrastructure_error


class ConnectionFactory(Factory):
    """
    Not Model based, this is not a Django factory.
    Factory objects are dispatcher based classes, independent
    of any database objects.
    """

    def create_ssh_job(self, filename):
        return self.create_job("ssh-host-01.jinja2", filename, validate=False)

    def create_bbb_job(self, filename):
        return self.create_job("bbb-02.jinja2", filename, validate=False)


class TestConnection(StdoutTestCase):
    def setUp(self):
        super().setUp()
        factory = ConnectionFactory()
        self.job = factory.create_ssh_job("sample_jobs/ssh-deploy.yaml")
        self.guest_job = factory.create_bbb_job("sample_jobs/bbb-ssh-guest.yaml")

    @unittest.skipIf(infrastructure_error("schroot"), "schroot not installed")
    def test_ssh_job(self):
        self.assertIsNotNone(self.job)
        self.job.validate()
        self.assertEqual([], self.job.pipeline.errors)
        # Check Pipeline
        description_ref = self.pipeline_reference("ssh-deploy.yaml", job=self.job)
        self.assertEqual(description_ref, self.job.pipeline.describe())

    @unittest.skipIf(infrastructure_error("schroot"), "schroot not installed")
    def test_ssh_authorize(self):
        overlay = [
            action
            for action in self.job.pipeline.actions
            if action.name == "scp-overlay"
        ][0]
        prepare = [
            action
            for action in overlay.pipeline.actions
            if action.name == "lava-overlay"
        ][0]
        authorize = [
            action
            for action in prepare.pipeline.actions
            if action.name == "ssh-authorize"
        ][0]
        self.assertFalse(authorize.active)
        self.job.validate()
        # only secondary connections set 'active' which then copies the identity file into the overlay.
        self.assertFalse(authorize.active)

    def test_ssh_identity(self):
        params = {
            "tftp": "None",
            "usb": "None",
            "ssh": {
                "host": "172.16.200.165",
                "options": [
                    "-o",
                    "Compression=yes",
                    "-o",
                    "UserKnownHostsFile=/dev/null",
                    "-o",
                    "PasswordAuthentication=no",
                    "-o",
                    "StrictHostKeyChecking=no",
                    "-o",
                    "LogLevel=FATAL",
                    "-l",
                    "root ",
                    "-p",
                    22,
                ],
                "identity_file": "dynamic_vm_keys/lava",
            },
        }
        check = check_ssh_identity_file(params)
        self.assertIsNone(check[0])
        self.assertIsNotNone(check[1])
        self.assertEqual(os.path.basename(check[1]), "lava")

    @unittest.skipIf(infrastructure_error("schroot"), "schroot not installed")
    def test_ssh_params(self):
        self.assertTrue(
            any(
                "ssh" in item
                for item in self.job.device["actions"]["deploy"]["methods"]
            )
        )
        params = self.job.device["actions"]["deploy"]["methods"]
        identity = os.path.realpath(
            os.path.join(
                lava_dispatcher.__file__, "../", params["ssh"]["identity_file"]
            )
        )
        self.assertTrue(os.path.exists(identity))
        test_command = [
            "ssh",
            "-o",
            "Compression=yes",
            "-o",
            "PasswordAuthentication=no",
            "-o",
            "LogLevel=FATAL",
            "-o",
            "UserKnownHostsFile=/dev/null",
            "-o",
            "StrictHostKeyChecking=no",
            "-i",
            identity,
            "-p",
            "8022",
        ]
        self.job.validate()
        login = [
            action for action in self.job.pipeline.actions if action.name == "login-ssh"
        ][0]
        self.assertIn(
            "ssh-connection", [action.name for action in login.pipeline.actions]
        )
        primary = [
            action
            for action in login.pipeline.actions
            if action.name == "ssh-connection"
        ][0]
        prepare = [
            action for action in login.pipeline.actions if action.name == "prepare-ssh"
        ][0]
        self.assertTrue(prepare.primary)
        self.assertEqual(identity, primary.identity_file)
        self.assertEqual(primary.host, params["ssh"]["host"])
        self.assertEqual(int(primary.ssh_port[1]), params["ssh"]["port"])
        self.assertEqual(set(test_command), set(primary.command))
        # idempotency check
        self.job.validate()
        self.assertEqual(identity, primary.identity_file)
        self.assertEqual(test_command, primary.command)
        bad_port = {
            "host": "localhost",
            "port": "bob",
            "options": [
                "-o",
                "Compression=yes",
                "-o",
                "UserKnownHostsFile=/dev/null",
                "-o",
                "PasswordAuthentication=no",
                "-o",
                "StrictHostKeyChecking=no",
                "-o",
                "LogLevel=FATAL",
            ],
            "identity_file": "dynamic_vm_keys/lava",
        }
        self.job.device["actions"]["deploy"]["methods"]["ssh"] = bad_port
        with self.assertRaises(JobError):
            self.job.validate()

    @unittest.skipIf(infrastructure_error("schroot"), "schroot not installed")
    def test_scp_command(self):
        self.job.validate()
        login = [
            action
            for action in self.guest_job.pipeline.actions
            if action.name == "login-ssh"
        ][0]
        scp = [
            action for action in login.pipeline.actions if action.name == "scp-deploy"
        ][0]
        self.assertIsNotNone(scp)
        # FIXME: schroot needs to make use of scp
        self.assertNotIn("ssh", scp.scp)
        self.assertFalse(scp.primary)

    @unittest.skipIf(infrastructure_error("schroot"), "schroot not installed")
    def test_tar_command(self):
        self.job.validate()
        login = [
            item for item in self.job.pipeline.actions if item.name == "login-ssh"
        ][0]
        tar_flags = login.get_namespace_data(
            action="scp-overlay", label="scp-overlay", key="tar_flags"
        )
        self.assertIsNotNone(tar_flags)
        self.assertEqual("--warning no-timestamp", tar_flags)

    @unittest.skipIf(infrastructure_error("schroot"), "schroot not installed")
    def test_schroot_params(self):
        self.assertIn(
            "schroot-login", [action.name for action in self.job.pipeline.actions]
        )
        schroot_action = [
            action
            for action in self.job.pipeline.actions
            if action.name == "schroot-login"
        ][0]
        self.job.validate()
        schroot_action.parsed_command(
            ["schroot", "-i", "-c", schroot_action.parameters["schroot"]],
            allow_fail=True,
        )
        if (
            "Chroot not found" in schroot_action.results["output"]
            or schroot_action.results["returncode"] != 0
        ):
            # schroot binary found but no matching chroot configured - skip test
            self.skipTest(
                f"no schroot support for {schroot_action.parameters['schroot']}"
            )

        self.assertIsInstance(schroot_action, SchrootAction)

        boot_act = [
            boot["boot"]
            for boot in self.job.parameters["actions"]
            if "boot" in boot and "schroot" in boot["boot"]
        ][0]
        self.assertEqual(boot_act["schroot"], schroot_action.parameters["schroot"])

    @unittest.skipIf(infrastructure_error("schroot"), "schroot not installed")
    def test_schroot_params_bad_schroot_name(self):
        schroot_action = [
            action
            for action in self.job.pipeline.actions
            if action.name == "schroot-login"
        ][0]

        bad_chroot = "unobtainium"
        schroot_action.parsed_command(
            ["schroot", "-i", "-c", bad_chroot], allow_fail=True
        )

        self.assertIn(
            "Chroot not found",
            schroot_action.results["output"],
            "Failed to catch a missing schroot name",
        )
        self.assertNotEqual(
            schroot_action.results["returncode"],
            0,
            "Failed to catch a missing schroot name",
        )

    def test_primary_ssh(self):
        factory = ConnectionFactory()
        job = factory.create_ssh_job("sample_jobs/primary-ssh.yaml")
        job.validate()
        overlay = [
            action for action in job.pipeline.actions if action.name == "scp-overlay"
        ][0]
        self.assertIsNotNone(overlay.parameters["deployment_data"])
        tar_flags = (
            overlay.parameters["deployment_data"]["tar_flags"]
            if "tar_flags" in overlay.parameters["deployment_data"].keys()
            else ""
        )
        self.assertIsNotNone(tar_flags)

    def test_guest_ssh(self):
        self.assertIsNotNone(self.guest_job)
        description_ref = self.pipeline_reference(
            "bbb-ssh-guest.yaml", job=self.guest_job
        )
        self.assertEqual(description_ref, self.guest_job.pipeline.describe())
        self.guest_job.validate()
        multinode = [
            protocol
            for protocol in self.guest_job.protocols
            if protocol.name == MultinodeProtocol.name
        ][0]
        self.assertEqual(int(multinode.system_timeout.duration), 900)
        self.assertEqual([], self.guest_job.pipeline.errors)
        self.assertEqual(
            len(
                [
                    item
                    for item in self.guest_job.pipeline.actions
                    if item.name == "scp-overlay"
                ]
            ),
            1,
        )
        scp_overlay = [
            item
            for item in self.guest_job.pipeline.actions
            if item.name == "scp-overlay"
        ][0]
        prepare = [
            item
            for item in scp_overlay.pipeline.actions
            if item.name == "prepare-scp-overlay"
        ][0]
        self.assertEqual(prepare.host_keys, ["ipv4"])
        self.assertEqual(
            prepare.get_namespace_data(
                action=prepare.name, label=prepare.name, key="overlay"
            ),
            prepare.host_keys,
        )
        params = prepare.parameters["protocols"][MultinodeProtocol.name]
        for call_dict in [
            call
            for call in params
            if "action" in call and call["action"] == prepare.name
        ]:
            self.assertEqual(
                call_dict,
                {
                    "action": "prepare-scp-overlay",
                    "message": {"ipaddr": "$ipaddr"},
                    "messageID": "ipv4",
                    "request": "lava-wait",
                    "timeout": {"minutes": 5},
                },
            )
        login = [
            action
            for action in self.guest_job.pipeline.actions
            if action.name == "login-ssh"
        ][0]
        scp = [
            action for action in login.pipeline.actions if action.name == "scp-deploy"
        ][0]
        self.assertFalse(scp.primary)
        ssh = [
            action for action in login.pipeline.actions if action.name == "prepare-ssh"
        ][0]
        self.assertFalse(ssh.primary)
        self.assertIsNotNone(scp.scp)
        self.assertFalse(scp.primary)
        autologin = [
            action
            for action in login.pipeline.actions
            if action.name == "auto-login-action"
        ][0]
        self.assertIsNone(autologin.params)
        self.assertIn("host_key", login.parameters["parameters"])
        self.assertIn("hostID", login.parameters["parameters"])
        self.assertIn(  # ipv4
            login.parameters["parameters"]["hostID"], prepare.host_keys
        )
        prepare.set_namespace_data(
            action=MultinodeProtocol.name,
            label=MultinodeProtocol.name,
            key="ipv4",
            value={"ipaddr": "172.16.200.165"},
        )
        self.assertEqual(
            prepare.get_namespace_data(
                action=prepare.name, label=prepare.name, key="overlay"
            ),
            prepare.host_keys,
        )
        self.assertIn(
            login.parameters["parameters"]["host_key"],
            prepare.get_namespace_data(
                action=MultinodeProtocol.name,
                label=MultinodeProtocol.name,
                key=login.parameters["parameters"]["hostID"],
            ),
        )
        host_data = prepare.get_namespace_data(
            action=MultinodeProtocol.name,
            label=MultinodeProtocol.name,
            key=login.parameters["parameters"]["hostID"],
        )
        self.assertEqual(
            host_data[login.parameters["parameters"]["host_key"]], "172.16.200.165"
        )
        data = scp_overlay.get_namespace_data(
            action=MultinodeProtocol.name, label=MultinodeProtocol.name, key="ipv4"
        )
        if "protocols" in scp_overlay.parameters:
            for params in scp_overlay.parameters["protocols"][MultinodeProtocol.name]:
                (replacement_key, placeholder) = [
                    (key, value) for key, value in params["message"].items()
                ][0]
                self.assertEqual(data[replacement_key], "172.16.200.165")
                self.assertEqual(placeholder, "$ipaddr")
        environment = scp_overlay.get_namespace_data(
            action=prepare.name, label="environment", key="env_dict"
        )
        self.assertIsNotNone(environment)
        self.assertIn("LANG", environment.keys())
        self.assertIn("C", environment.values())
        overlay = [
            item for item in scp_overlay.pipeline.actions if item.name == "lava-overlay"
        ]
        self.assertIn(
            "action", overlay[0].parameters["protocols"][MultinodeProtocol.name][0]
        )
        self.assertIn(
            "message", overlay[0].parameters["protocols"][MultinodeProtocol.name][0]
        )
        self.assertIn(
            "timeout", overlay[0].parameters["protocols"][MultinodeProtocol.name][0]
        )
        msg_dict = overlay[0].parameters["protocols"][MultinodeProtocol.name][0][
            "message"
        ]
        for key, value in msg_dict.items():
            self.assertTrue(value.startswith("$"))
            self.assertFalse(key.startswith("$"))
        self.assertIn(
            "request", overlay[0].parameters["protocols"][MultinodeProtocol.name][0]
        )
        multinode = [
            item
            for item in overlay[0].pipeline.actions
            if item.name == "lava-multinode-overlay"
        ]
        self.assertEqual(len(multinode), 1)
        # Check Pipeline
        description_ref = self.pipeline_reference("ssh-guest.yaml", job=self.guest_job)
        self.assertEqual(description_ref, self.guest_job.pipeline.describe())


class TestConsoleConnections(StdoutTestCase):
    def setUp(self):
        super().setUp()
        factory = ConnectionFactory()
        self.job = factory.create_ssh_job("sample_jobs/ssh-deploy.yaml")
        self.guest_job = factory.create_bbb_job("sample_jobs/bbb-ssh-guest.yaml")

    def test_device_commands(self):
        device_data = """
commands:
    # deprecated
    # connect: telnet localhost 7019
    connections:
      uart1:
        connect: telnet localhost 7019
        tags:
        - primary
      uart0:
        connect: telnet localhost 7020
        """
        data = yaml_safe_load(device_data)
        self.assertIn("commands", data)
        self.assertIn("connections", data["commands"])
        self.assertNotIn("connect", data["commands"])
        for hardware, value in data["commands"]["connections"].items():
            if "connect" not in value:
                self.fail("Misconfigured device configuration")
            if "tags" in value and "primary" in value["tags"]:
                self.assertEqual("uart1", hardware)
            else:
                self.assertEqual("uart0", hardware)

    @patch(
        "lava_dispatcher.actions.deploy.tftp.which", return_value="/usr/bin/in.tftpd"
    )
    def test_connection_tags(self, which_mock):
        factory = ConnectionFactory()
        job = factory.create_bbb_job("sample_jobs/uboot-ramdisk.yaml")
        job.validate()
        self.assertIsNotNone(job.device["commands"]["connections"].items())
        for hardware, value in job.device["commands"]["connections"].items():
            self.assertEqual("uart0", hardware)
            self.assertIn("connect", value)
            self.assertIn("tags", value)
            self.assertEqual(["primary", "telnet"], value["tags"])
        boot = [
            action for action in job.pipeline.actions if action.name == "uboot-action"
        ][0]
        connect = [
            action
            for action in boot.pipeline.actions
            if action.name == "connect-device"
        ][0]
        for hardware, value in connect.tag_dict.items():
            self.assertEqual("uart0", hardware)
            self.assertNotIn("connect", value)
            self.assertNotIn("tags", value)
            self.assertEqual(["primary", "telnet"], value)
        self.assertIn(connect.hardware, connect.tag_dict)
        self.assertEqual(["primary", "telnet"], connect.tag_dict[connect.hardware])


class TestTimeouts(StdoutTestCase):
    """
    Test action and connection timeout parsing.
    """

    def setUp(self):
        super().setUp()
        self.factory = ConnectionFactory()

    @patch(
        "lava_dispatcher.actions.deploy.tftp.which", return_value="/usr/bin/in.tftpd"
    )
    def test_action_timeout(self, which_mock):
        factory = ConnectionFactory()
        job = factory.create_bbb_job("sample_jobs/uboot-ramdisk.yaml")
        job.validate()
        deploy = [
            action for action in job.pipeline.actions if action.name == "tftp-deploy"
        ][0]
        test_action = [
            action
            for action in job.pipeline.actions
            if action.name == "lava-test-retry"
        ][0]
        test_shell = [
            action
            for action in test_action.pipeline.actions
            if action.name == "lava-test-shell"
        ][0]
        self.assertEqual(
            test_shell.connection_timeout.duration, 240
        )  # job specifies 4 minutes
        self.assertEqual(
            test_shell.timeout.duration, 300
        )  # job (test action block) specifies 5 minutes
        self.assertEqual(deploy.timeout.duration, 120)  # job specifies 2 minutes
        self.assertEqual(deploy.connection_timeout.duration, Timeout.default_duration())
        self.assertNotEqual(
            deploy.connection_timeout.duration, test_shell.connection_timeout
        )
        self.assertEqual(test_action.timeout.duration, 300)
        uboot = [
            action for action in job.pipeline.actions if action.name == "uboot-action"
        ][0]
        retry = [
            action
            for action in uboot.pipeline.actions
            if action.name == "uboot-commands"
        ][0]
        auto = [
            action
            for action in retry.pipeline.actions
            if action.name == "auto-login-action"
        ][0]
        self.assertEqual(auto.timeout.duration / 60, 9)  # 9 minutes in the job def

    def test_job_connection_timeout(self):
        """
        Test connection timeout specified in the submission YAML
        """
        y_file = os.path.join(
            os.path.dirname(__file__), "./sample_jobs/uboot-ramdisk.yaml"
        )
        with open(y_file) as uboot_ramdisk:
            data = yaml_safe_load(uboot_ramdisk)
        data["timeouts"]["connection"] = {"seconds": 20}
        job = self.factory.create_custom_job("bbb-01.jinja2", data)
        for action in job.pipeline.actions:
            if action.pipeline:
                for check_action in action.pipeline.actions:
                    if check_action.connection_timeout and check_action.name not in [
                        "uboot-commands",
                        "lava-test-shell",
                    ]:
                        # lava-test-shell and uboot-commands have overrides in this sample job
                        # lava-test-shell from the job, uboot-commands from the device
                        self.assertEqual(check_action.connection_timeout.duration, 20)
        deploy = [
            action for action in job.pipeline.actions if action.name == "tftp-deploy"
        ][0]
        self.assertIsNotNone(deploy)
        test_action = [
            action
            for action in job.pipeline.actions
            if action.name == "lava-test-retry"
        ][0]
        test_shell = [
            action
            for action in test_action.pipeline.actions
            if action.name == "lava-test-shell"
        ][0]
        self.assertEqual(test_shell.timeout.duration, 300)
        uboot = [
            action for action in job.pipeline.actions if action.name == "uboot-action"
        ][0]
        retry = [
            action
            for action in uboot.pipeline.actions
            if action.name == "uboot-commands"
        ][0]
        auto = [
            action
            for action in retry.pipeline.actions
            if action.name == "auto-login-action"
        ][0]
        self.assertEqual(auto.connection_timeout.duration / 60, 12)

    def test_action_connection_timeout(self):
        """
        Test connection timeout specified for a particular action
        """
        y_file = os.path.join(
            os.path.dirname(__file__), "./sample_jobs/uboot-ramdisk.yaml"
        )
        with open(y_file) as uboot_ramdisk:
            data = yaml_safe_load(uboot_ramdisk)
        connection_timeout = Timeout.parse(
            data["timeouts"]["connections"]["lava-test-shell"]
        )
        data["timeouts"]["actions"]["uboot-commands"] = {}
        data["timeouts"]["actions"]["uboot-commands"]["seconds"] = 90
        data["timeouts"]["connections"]["uboot-commands"] = {}
        data["timeouts"]["connections"]["uboot-commands"]["seconds"] = 45
        self.assertEqual(connection_timeout, 240)
        job = self.factory.create_custom_job("bbb-01.jinja2", data)
        boot = [
            action for action in job.pipeline.actions if action.name == "uboot-action"
        ][0]
        retry = [
            action
            for action in boot.pipeline.actions
            if action.name == "uboot-commands"
        ][0]
        self.assertEqual(
            retry.timeout.duration, 90
        )  # Set by the job global action timeout
        self.assertEqual(retry.connection_timeout.duration, 45)


class TestDisconnect(StdoutTestCase):
    """
    Test disconnect action
    """

    def setUp(self):
        super().setUp()
        self.factory = ConnectionFactory()

    def test_handled_disconnect(self):
        factory = ConnectionFactory()
        job = factory.create_job(
            "mps2plus-01.jinja2", "sample_jobs/mps2plus.yaml", validate=False
        )
        job.validate()
        deploy = [
            action for action in job.pipeline.actions if action.name == "mps-deploy"
        ][0]
        self.assertIsNotNone(deploy)

    def test_disconnect_with_plain_connection_command(self):
        factory = ConnectionFactory()
        job = factory.create_job(
            "mps2plus-02.jinja2", "sample_jobs/mps2plus.yaml", validate=False
        )
        # mps2plus-02.jinja2 does not use tags for it's connection
        with self.assertRaises(JobError):
            job.validate()

    def test_unhandled_disconnect(self):
        factory = ConnectionFactory()
        job = factory.create_job(
            "mps2plus-03.jinja2", "sample_jobs/mps2plus.yaml", validate=False
        )
        try:
            job.validate()
        except JobError:
            pass
        except InfrastructureError:
            raise self.skipTest("Cannot validate if minicom is not on PATH")
        # mps2plus-03.jinja2 does use a tag, but minicom cannot be disconnected from currently
        # Want to check the exception message gives some useful information
        # on how to amend the device dictionary.
        with self.assertRaises(JobError) as exc:
            job.validate()
        the_exception = exc.exception
        err_msg = (
            "Invalid job data: ["
            "\"LAVA does not know how to disconnect: ensure that primary connection has one of the following tags: ('telnet', 'ssh', 'shell')\", "
            "\"LAVA does not know how to disconnect: ensure that primary connection has one of the following tags: ('telnet', 'ssh', 'shell')\", "
            "\"LAVA does not know how to disconnect: ensure that primary connection has one of the following tags: ('telnet', 'ssh', 'shell')\", "
            "\"LAVA does not know how to disconnect: ensure that primary connection has one of the following tags: ('telnet', 'ssh', 'shell')\"]"
        )
        self.assertEqual(str(the_exception).strip(), err_msg)
