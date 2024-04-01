# Copyright (C) 2018 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later


from unittest.mock import patch

import pexpect

from lava_common.exceptions import (
    InfrastructureError,
    JobError,
    LAVATimeoutError,
    TestError,
)
from lava_dispatcher.actions.test.interactive import TestInteractiveAction
from tests.lava_dispatcher.test_basic import Factory, LavaDispatcherTestCase


class TestInteractive(LavaDispatcherTestCase):
    def test_pipeline(self):
        factory = Factory()
        job = factory.create_job("b2260-01", "sample_jobs/b2260-interactive.yaml")
        job.validate()
        description_ref = LavaDispatcherTestCase.pipeline_reference(
            "b2260-interactive.yaml", job=job
        )
        self.assertEqual(
            description_ref,
            job.pipeline.describe(),
        )

    def test_bbb(self):
        factory = Factory()
        job = factory.create_job("bbb-01", "sample_jobs/bbb-uboot-interactive.yaml")
        job.validate()
        description_ref = LavaDispatcherTestCase.pipeline_reference(
            "bbb-uboot-interactive.yaml", job=job
        )
        self.assertEqual(
            description_ref,
            job.pipeline.describe(),
        )

    def test_stages(self):
        factory = Factory()
        job = factory.create_job("docker-01", "sample_jobs/docker-interactive.yaml")
        with patch(
            "lava_dispatcher.actions.deploy.docker.which",
            return_value="/usr/bin/docker",
        ), patch("subprocess.check_output", return_value=b""):
            job.validate()

        description_ref = LavaDispatcherTestCase.pipeline_reference(
            "docker-interactive.yaml", job=job
        )
        self.assertEqual(
            description_ref,
            job.pipeline.describe(),
        )
        self.assertEqual(
            job.pipeline.actions[3].pipeline.actions[0].parameters["stage"],
            0,
        )

    def test_raise_exception(self):
        action = TestInteractiveAction(self.create_job_mock())
        action.validate()

        with self.assertRaisesRegex(InfrastructureError, "hello"):
            action.raise_exception("InfrastructureError", "hello")

        with self.assertRaisesRegex(JobError, "A strange error"):
            action.raise_exception("JobError", "A strange error")

        with self.assertRaisesRegex(TestError, "A strange error"):
            action.raise_exception("TestError", "A strange error")

        with self.assertRaisesRegex(
            JobError, "Unknown exception 'bug' with 'A strange error'"
        ):
            action.raise_exception("bug", "A strange error")


class Connection:
    class _Match:
        def __init__(self):
            self.d = {}

        def groupdict(self):
            return self.d

    def __init__(self, data):
        self.data = data
        self.match = self._Match()
        self.timeout = 30

    def sendline(self, line, delay):
        assert self.data.pop(0) == ("sendline", line)  # nosec - assert is ok

    def expect(self, expect, timeout=1):
        print(f"expect: {expect}")
        print(f"ref   : {self.data[0]}")
        data = self.data.pop(0)
        assert (data[0], data[1]) == ("expect", expect)  # nosec - assert is ok
        if isinstance(data[2], int):
            self.match.d = {}
            if len(data) > 3:
                self.match.d = data[3]
            return data[2]
        else:
            raise data[2](data[3])

    def readline(self):
        data = self.data.pop(0)
        assert data[0] == "readline"  # nosec
        return data[1]


class Logger:
    def __init__(self, data):
        self.data = data

    def _check(self, data):
        print(f"data: {data}")
        print(f"ref : {self.data[0]}")
        assert self.data.pop(0) == data  # nosec - assert is ok

    def debug(self, line, *args):
        self._check(("debug", line % args))

    def error(self, line, *args):
        self._check(("error", line % args))

    def info(self, line, *args):
        self._check(("info", line % args))

    def results(self, res):
        self._check(("results", res))


class Timing:
    def __init__(self):
        self.clock = 0

    def __call__(self):
        self.clock += 1
        return self.clock


class TestInteractiveScript(LavaDispatcherTestCase):
    @patch("time.monotonic", Timing())
    def test_run_script(self):
        action = TestInteractiveAction(self.create_simple_job())
        action.last_check = 0
        action.parameters = {"stage": 0}
        action.logger = Logger(
            [
                ("info", "Sending nothing, waiting"),
                ("debug", "Waiting for '=> ', '/ # '"),
                ("debug", "Matched a prompt: '=> '"),
                (
                    "results",
                    {
                        "definition": "0_setup",
                        "case": "wait prompt",
                        "result": "pass",
                        "duration": "2.00",
                    },
                ),
                ("info", "Sending 'help'"),
                ("debug", "Waiting for '=> ', '/ # '"),
                ("debug", "Matched a prompt: '=> '"),
                (
                    "results",
                    {
                        "definition": "0_setup",
                        "case": "network.help",
                        "result": "pass",
                        "duration": "2.00",
                    },
                ),
                ("info", "Sending 'dhcp'"),
                ("debug", "Waiting for '=> ', '/ # ', 'DHCP client bound to address'"),
                ("info", "Matched a success: 'DHCP client bound to address'"),
                ("debug", "Matched a prompt: '=> '"),
                (
                    "results",
                    {
                        "definition": "0_setup",
                        "case": "network.dhcp",
                        "result": "pass",
                        "duration": "3.00",
                    },
                ),
                ("info", "Sending 'host lavasoftware.org'"),
                (
                    "debug",
                    "Waiting for '=> ', '/ # ', "
                    "'Host lavasoftware.org not found: 3(NXDOMAIN)', 'TIMEOUT'",
                ),
                (
                    "error",
                    "Matched a failure: 'Host lavasoftware.org not found: 3(NXDOMAIN)'",
                ),
                ("debug", "Matched a prompt: '=> '"),
                (
                    "results",
                    {
                        "definition": "0_setup",
                        "case": "network.host",
                        "result": "fail",
                        "duration": "3.00",
                    },
                ),
                ("info", "Sending 'dig lavasoftware.org'"),
                ("debug", "Waiting for '=> ', '/ # ', '192.168.0.1'"),
                ("error", "Matched a prompt (was expecting a success): '=> '"),
                (
                    "results",
                    {
                        "definition": "0_setup",
                        "case": "network.dig",
                        "result": "fail",
                        "duration": "2.00",
                    },
                ),
                ("info", "Sending 'ping -c 1 lavasoftware.org'"),
                ("debug", "Waiting for '=> ', '/ # ', 'Name or service not known'"),
                ("error", "Matched a failure: 'Name or service not known'"),
                (
                    "results",
                    {
                        "definition": "0_setup",
                        "case": "network.ping",
                        "result": "fail",
                        "duration": "2.00",
                    },
                ),
            ]
        )
        action.validate()

        conn_data = [
            ("expect", ["=> ", "/ # ", pexpect.TIMEOUT], 0),
            ("sendline", "help"),
            ("expect", ["=> ", "/ # ", pexpect.TIMEOUT], 0),
            ("sendline", "dhcp"),
            (
                "expect",
                ["=> ", "/ # ", "DHCP client bound to address", pexpect.TIMEOUT],
                2,
            ),
            ("expect", ["=> ", "/ # ", pexpect.TIMEOUT], 0),
            ("sendline", "host lavasoftware.org"),
            (
                "expect",
                [
                    "=> ",
                    "/ # ",
                    "Host lavasoftware.org not found: 3(NXDOMAIN)",
                    "TIMEOUT",
                    pexpect.TIMEOUT,
                ],
                2,
            ),
            ("expect", ["=> ", "/ # ", pexpect.TIMEOUT], 0),
            ("sendline", "dig lavasoftware.org"),
            ("expect", ["=> ", "/ # ", "192.168.0.1", pexpect.TIMEOUT], 0),
            ("sendline", "ping -c 1 lavasoftware.org"),
            (
                "expect",
                ["=> ", "/ # ", "Name or service not known", pexpect.TIMEOUT],
                2,
            ),
        ]
        script = {
            "prompts": ["=> ", "/ # "],
            "name": "setup",
            "script": [
                {"command": None, "name": "wait prompt"},
                {"command": "help", "name": "network.help"},
                {
                    "command": "dhcp",
                    "name": "network.dhcp",
                    "successes": [{"message": "DHCP client bound to address"}],
                },
                {
                    "command": "host {HOST}",
                    "name": "network.host",
                    "failures": [
                        {"message": "Host lavasoftware.org not found: 3(NXDOMAIN)"},
                        {"message": "TIMEOUT"},
                    ],
                },
                {
                    "command": "dig {HOST}",
                    "name": "network.dig",
                    "successes": [{"message": "192.168.0.1"}],
                },
                {
                    "command": "ping -c 1 {HOST}",
                    "name": "network.ping",
                    "failures": [
                        {
                            "message": "Name or service not known",
                            "exception": "InfrastructureError",
                            "error": "network setup failed",
                        }
                    ],
                },
            ],
        }
        test_connection = Connection(conn_data)
        substitutions = {"{HOST}": "lavasoftware.org"}
        with self.assertRaisesRegex(InfrastructureError, "network setup failed"):
            action.run_script(test_connection, script, substitutions)

        self.assertEqual(action.logger.data, [])
        self.assertEqual(test_connection.data, [])

    @patch("time.monotonic", Timing())
    def test_run_script_echo_discard(self):
        action = TestInteractiveAction(self.create_simple_job())
        action.last_check = 0
        action.parameters = {"stage": 0}
        action.logger = Logger(
            [
                ("info", "Sending nothing, waiting"),
                ("debug", "Waiting for '=> ', '/ # '"),
                ("debug", "Matched a prompt: '=> '"),
                (
                    "results",
                    {
                        "definition": "0_setup",
                        "case": "wait prompt",
                        "result": "pass",
                        "duration": "2.00",
                    },
                ),
                ("info", "Sending 'echo 'hello''"),
                ("debug", "Ignoring echo: 'hello'"),
                ("debug", "Waiting for '=> ', '/ # '"),
                ("debug", "Matched a prompt: '=> '"),
                (
                    "results",
                    {
                        "definition": "0_setup",
                        "case": "echo",
                        "result": "pass",
                        "duration": "2.00",
                    },
                ),
            ]
        )
        action.validate()

        conn_data = [
            ("expect", ["=> ", "/ # ", pexpect.TIMEOUT], 0),
            ("sendline", "echo 'hello'"),
            ("readline", "hello"),
            ("expect", ["=> ", "/ # ", pexpect.TIMEOUT], 0),
        ]
        script = {
            "prompts": ["=> ", "/ # "],
            "name": "setup",
            "echo": "discard",
            "script": [
                {"command": None, "name": "wait prompt"},
                {"command": "echo 'hello'", "name": "echo"},
            ],
        }
        test_connection = Connection(conn_data)
        substitutions = {}
        action.run_script(test_connection, script, substitutions)
        self.assertEqual(action.logger.data, [])
        self.assertEqual(test_connection.data, [])

    @patch("time.monotonic", Timing())
    def test_run_script_capture(self):
        action = TestInteractiveAction(self.create_simple_job())
        action.last_check = 0
        action.parameters = {"stage": 0}
        action.logger = Logger(
            [
                ("info", "Sending nothing, waiting"),
                ("debug", "Waiting for '=> ', '/ # '"),
                ("debug", "Matched a prompt: '=> '"),
                (
                    "results",
                    {
                        "definition": "0_setup",
                        "case": "wait prompt",
                        "result": "pass",
                        "duration": "2.00",
                    },
                ),
                ("info", "Sending nothing, waiting"),
                ("debug", "Waiting for '=> ', '/ # ', 'foo(?P<val>.+)'"),
                (
                    "info",
                    "Matched a success: 'foo(?P<val>.+)' (groups: {'val': 'bar'})",
                ),
                ("debug", "Matched a prompt: '=> '"),
                (
                    "results",
                    {
                        "definition": "0_setup",
                        "case": "test1",
                        "result": "pass",
                        "duration": "3.00",
                    },
                ),
                ("info", "Sending 'echo val: bar'"),
                ("debug", "Waiting for '=> ', '/ # '"),
                ("debug", "Matched a prompt: '=> '"),
            ]
        )
        action.validate()

        conn_data = [
            ("expect", ["=> ", "/ # ", pexpect.TIMEOUT], 0),
            (
                "expect",
                ["=> ", "/ # ", "foo(?P<val>.+)", pexpect.TIMEOUT],
                2,
                {"val": "bar"},
            ),
            ("expect", ["=> ", "/ # ", pexpect.TIMEOUT], 0),
            ("sendline", "echo val: bar"),
            ("expect", ["=> ", "/ # ", pexpect.TIMEOUT], 0),
        ]
        script = {
            "prompts": ["=> ", "/ # "],
            "name": "setup",
            "script": [
                {"command": None, "name": "wait prompt"},
                {
                    "command": None,
                    "name": "test1",
                    "successes": [{"message": "foo(?P<val>.+)"}],
                },
                {"command": "echo val: {val}"},
            ],
        }
        test_connection = Connection(conn_data)
        substitutions = {}
        action.run_script(test_connection, script, substitutions)
        self.assertEqual(
            substitutions,
            {"{val}": "bar"},
        )
        self.assertEqual(action.logger.data, [])
        self.assertEqual(test_connection.data, [])

    @patch("time.monotonic", Timing())
    def test_run_script_delay(self):
        sleep_calls = 0

        def check_sleep(val):
            nonlocal sleep_calls
            sleep_calls += 1
            self.assertEqual(val, 0.5)

        action = TestInteractiveAction(self.create_simple_job())
        action.last_check = 0
        action.parameters = {"stage": 0}
        action.logger = Logger(
            [
                ("info", "Sending nothing, waiting"),
                ("debug", "Waiting for '=> ', '/ # '"),
                ("debug", "Matched a prompt: '=> '"),
                (
                    "results",
                    {
                        "definition": "0_setup",
                        "case": "wait prompt",
                        "result": "pass",
                        "duration": "2.00",
                    },
                ),
                ("info", "Delaying for 0.5s"),
            ]
        )
        action.validate()

        conn_data = [("expect", ["=> ", "/ # ", pexpect.TIMEOUT], 0)]
        script = {
            "prompts": ["=> ", "/ # "],
            "name": "setup",
            "script": [{"command": None, "name": "wait prompt"}, {"delay": 0.5}],
        }
        test_connection = Connection(conn_data)
        substitutions = {}
        with patch("time.sleep", check_sleep):
            action.run_script(test_connection, script, substitutions)
        self.assertEqual(sleep_calls, 1)
        self.assertEqual(action.logger.data, [])
        self.assertEqual(test_connection.data, [])

    @patch("time.monotonic", Timing())
    def test_run_script_multinode(self):
        class Proto:
            def __init__(self):
                self.captured = []

            def request_send(self, *args):
                self.captured.append(("send", *args))
                return '{"response": "ack"}'

            def request_wait(self, *args):
                self.captured.append(("wait", *args))
                return '{"message": {"1": {"ipaddr": "172.17.0.3"}}, "response": "ack"}'

            def request_wait_all(self, *args):
                self.captured.append(("wait-all", *args))
                return '{"message": {"1": {"val2": "172.17.0.4"}}, "response": "ack"}'

            def request_sync(self, *args):
                self.captured.append(("sync", *args))
                return '{"response": "ack"}'

            def set_timeout(self, duration):
                pass

        action = TestInteractiveAction(self.create_simple_job())
        action.last_check = 0
        proto = Proto()
        action.multinode_proto = proto

        action.parameters = {"stage": 0}
        action.logger = Logger(
            [
                ("info", "Sending nothing, waiting"),
                ("debug", "Waiting for '=> ', '/ # '"),
                ("debug", "Matched a prompt: '=> '"),
                (
                    "results",
                    {
                        "definition": "0_setup",
                        "case": "wait prompt",
                        "result": "pass",
                        "duration": "2.00",
                    },
                ),
                (
                    "info",
                    'wait result: \'{"message": {"1": {"ipaddr": "172.17.0.3"}}, '
                    '"response": "ack"}\'',
                ),
                ("info", 'send result: \'{"response": "ack"}\''),
                (
                    "info",
                    'wait-all result: \'{"message": {"1": {"val2": "172.17.0.4"}}, '
                    '"response": "ack"}\'',
                ),
                (
                    "info",
                    'wait-all result: \'{"message": {"1": {"val2": "172.17.0.4"}}, '
                    '"response": "ack"}\'',
                ),
                ("info", 'sync result: \'{"response": "ack"}\''),
            ]
        )
        action.validate()

        conn_data = [("expect", ["=> ", "/ # ", pexpect.TIMEOUT], 0)]
        script = {
            "prompts": ["=> ", "/ # "],
            "name": "setup",
            "script": [
                {"command": None, "name": "wait prompt"},
                {"lava-wait": "msgid456"},
                {"lava-send": "msgid123 key1={ipaddr}"},
                {"lava-wait-all": "msgid789"},
                {"lava-wait-all": "msgid678 role=role1"},
                {"lava-sync": "msgid321"},
            ],
        }
        test_connection = Connection(conn_data)
        substitutions = {}
        action.run_script(test_connection, script, substitutions)
        self.assertEqual(
            substitutions,
            {"{ipaddr}": "172.17.0.3", "{val2}": "172.17.0.4"},
        )
        self.assertEqual(action.logger.data, [])
        self.assertEqual(test_connection.data, [])
        self.assertEqual(
            proto.captured,
            [
                ("wait", "msgid456"),
                ("send", "msgid123", {"key1": "172.17.0.3"}),
                ("wait-all", "msgid789", None),
                ("wait-all", "msgid678", "role1"),
                ("sync", "msgid321"),
            ],
        )

    @patch("time.monotonic", Timing())
    def test_run_script_raise_test_error_unnamed_command(self):
        action = TestInteractiveAction(self.create_simple_job())
        action.last_check = 0
        action.parameters = {"stage": 0}
        action.logger = Logger(
            [
                ("info", "Sending nothing, waiting"),
                ("debug", "Waiting for '=> ', '/ # '"),
                ("debug", "Matched a prompt: '=> '"),
                (
                    "results",
                    {
                        "definition": "0_setup",
                        "case": "wait prompt",
                        "result": "pass",
                        "duration": "2.00",
                    },
                ),
                ("info", "Sending 'echo 'hello''"),
                ("debug", "Ignoring echo: \"echo 'hello'\""),
                ("debug", "Waiting for '=> ', '/ # ', 'world'"),
                ("error", "Matched a failure: 'world'"),
                ("debug", "Matched a prompt: '=> '"),
            ]
        )
        action.validate()

        conn_data = [
            ("expect", ["=> ", "/ # ", pexpect.TIMEOUT], 0),
            ("sendline", "echo 'hello'"),
            ("readline", "echo 'hello'"),
            ("expect", ["=> ", "/ # ", "world", pexpect.TIMEOUT], 2),
            ("expect", ["=> ", "/ # ", pexpect.TIMEOUT], 0),
        ]
        script = {
            "prompts": ["=> ", "/ # "],
            "name": "setup",
            "echo": "discard",
            "script": [
                {"command": None, "name": "wait prompt"},
                {"command": "echo 'hello'", "failures": [{"message": "world"}]},
                {"command": "dhcp", "name": "dhcp"},
            ],
        }
        test_connection = Connection(conn_data)
        substitutions = {}
        with self.assertRaisesRegex(TestError, "Failed to run command 'echo 'hello'"):
            action.run_script(test_connection, script, substitutions)

        self.assertEqual(action.logger.data, [])
        self.assertEqual(test_connection.data, [])

    @patch("time.monotonic", Timing())
    def test_run_script_raise_timeout(self):
        action = TestInteractiveAction(self.create_simple_job())
        action.last_check = 0
        action.parameters = {"stage": 0}
        action.logger = Logger(
            [
                ("info", "Sending nothing, waiting"),
                ("debug", "Waiting for '=> ', '/ # '"),
                (
                    "results",
                    {
                        "definition": "0_setup",
                        "case": "wait prompt",
                        "result": "fail",
                        "duration": "1.00",
                    },
                ),
            ]
        )
        action.validate()

        conn_data = [("expect", ["=> ", "/ # ", pexpect.TIMEOUT], pexpect.TIMEOUT, "")]
        script = {
            "prompts": ["=> ", "/ # "],
            "name": "setup",
            "echo": "discard",
            "script": [
                {"command": None, "name": "wait prompt"},
                {"command": "dhcp", "name": "dhcp"},
            ],
        }
        test_connection = Connection(conn_data)
        substitutions = {}
        with self.assertRaisesRegex(
            LAVATimeoutError, "interactive connection timed out"
        ):
            action.run_script(test_connection, script, substitutions)

        self.assertEqual(action.logger.data, [])
        self.assertEqual(test_connection.data, [])

    def test_namespace_connection(self):
        factory = Factory()
        job = factory.create_job("b2260-01", "sample_jobs/b2260-interactive.yaml")
        action = job.pipeline.find_action(TestInteractiveAction)
        action.logger = Logger(
            [
                ("debug", "Using namespace: common"),
                (
                    "results",
                    {
                        "definition": "0_setup",
                        "case": "wait prompt",
                        "result": "fail",
                        "duration": "1.00",
                    },
                ),
            ]
        )

        conn_previous = [("expect", ["foo", pexpect.TIMEOUT], pexpect.TIMEOUT, "")]
        previous_connection = Connection(conn_previous)
        conn_data = [("expect", ["bar", pexpect.TIMEOUT], pexpect.TIMEOUT, "")]
        data_connection = Connection(conn_previous)
        action.set_namespace_data("shared", "shared", "connection", data_connection)

        # disable script run to avoid duplicate as it's already test by other test function
        action.parameters["interactive"] = {}

        new_connection = action.run(previous_connection, 10)
        self.assertEqual(new_connection, data_connection)

    def test_connection_namespace_connection(self):
        factory = Factory()
        job = factory.create_job("b2260-01", "sample_jobs/b2260-interactive.yaml")
        action = job.pipeline.find_action(TestInteractiveAction)
        action.parameters["connection-namespace"] = "foobar"
        action.logger = Logger(
            [
                ("debug", "Using connection namespace: foobar"),
                ("debug", "Using namespace: foobar"),
                (
                    "results",
                    {
                        "definition": "0_setup",
                        "case": "wait prompt",
                        "result": "fail",
                        "duration": "1.00",
                    },
                ),
            ]
        )

        conn_previous = [("expect", ["foo", pexpect.TIMEOUT], pexpect.TIMEOUT, "")]
        previous_connection = Connection(conn_previous)
        conn_data = [("expect", ["bar", pexpect.TIMEOUT], pexpect.TIMEOUT, "")]
        data_connection = Connection(conn_previous)
        action.set_namespace_data(
            "shared", "shared", "connection", data_connection, {"namespace": "foobar"}
        )

        # disable script run to avoid duplicate as it's already test by other test function
        action.parameters["interactive"] = {}

        new_connection = action.run(previous_connection, 10)
        self.assertEqual(new_connection, data_connection)
