# Copyright (C) 2016 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
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

import os
import time
import pexpect
from lava_common.exceptions import JobError
from lava_dispatcher.action import Action
from lava_dispatcher.utils.messages import LinuxKernelMessages
from tests.lava_dispatcher.test_basic import StdoutTestCase


class Kernel:
    def __init__(self):
        super().__init__()
        self.existing_prompt = None

    def run(self, prompt_list):
        if not self.existing_prompt:
            self.existing_prompt = prompt_list[:]
            prompt_list = LinuxKernelMessages.get_init_prompts()
        if isinstance(self.existing_prompt, list):
            prompt_list.extend(self.existing_prompt)
        else:
            prompt_list.append(self.existing_prompt)
        return prompt_list


class Child(Kernel):
    def run(self, prompt_list):
        self.existing_prompt = prompt_list[:]
        prompt_list = LinuxKernelMessages.get_init_prompts()
        super().run(prompt_list)
        return prompt_list


class FakeConnection:
    def __init__(self, child, prompt_str):
        super().__init__()
        self.raw_connection = child
        self.prompt_str = prompt_str
        self.check_char = "#"
        self.faketimeout = 30
        self.connected = True
        self.name = "fake-connection"

    def sendline(self, s="", delay=0):
        pass

    def force_prompt_wait(self, remaining=None):
        return self.wait()

    def wait(self, max_end_time=None, searchwindowsize=-1):
        ret = None
        try:
            ret = self.raw_connection.expect(self.prompt_str, timeout=self.faketimeout)
        except pexpect.EOF:
            pass
        return ret


class TestBootMessages(StdoutTestCase):
    def setUp(self):
        super().setUp()
        self.max_end_time = time.monotonic() + 30

    def test_kernel_txt(self):
        """
        The same logfile passes kernel boot and fails
        to find init - so the panic needs to be caught by InitMessages
        """
        logfile = os.path.join(os.path.dirname(__file__), "kernel-panic.txt")
        self.assertTrue(os.path.exists(logfile))
        child = pexpect.spawn("cat", [logfile])
        message_list = LinuxKernelMessages.get_init_prompts()
        self.assertIsNotNone(message_list)
        connection = FakeConnection(child, message_list)
        with self.assertRaises(JobError):
            LinuxKernelMessages.parse_failures(
                connection, action=Action(), max_end_time=self.max_end_time, fail_msg=""
            )

    def test_kernel_1(self):
        logfile = os.path.join(os.path.dirname(__file__), "kernel-1.txt")
        self.assertTrue(os.path.exists(logfile))
        child = pexpect.spawn("cat", [logfile])
        message_list = LinuxKernelMessages.get_init_prompts()
        connection = FakeConnection(child, message_list)
        results = LinuxKernelMessages.parse_failures(
            connection, action=Action(), max_end_time=self.max_end_time, fail_msg=""
        )
        self.assertEqual(results, [])

    def test_kernel_2(self):
        logfile = os.path.join(os.path.dirname(__file__), "kernel-2.txt")
        self.assertTrue(os.path.exists(logfile))
        child = pexpect.spawn("cat", [logfile])
        message_list = LinuxKernelMessages.get_init_prompts()
        self.assertIsNotNone(message_list)
        connection = FakeConnection(child, message_list)
        results = LinuxKernelMessages.parse_failures(
            connection,
            action=Action(),
            max_end_time=self.max_end_time,
            fail_msg="",
        )
        self.assertEqual(len(results), 13)
        message_list = LinuxKernelMessages.get_init_prompts()
        child = pexpect.spawn("cat", [logfile])
        connection = FakeConnection(child, message_list)
        results = LinuxKernelMessages.parse_failures(
            connection, action=Action(), max_end_time=self.max_end_time, fail_msg=""
        )
        self.assertEqual(len(results), 13)
        for res in results:
            self.assertEqual(res["kind"], "exception")
            self.assertIsNotNone(res["message"])

    def test_kernel_4(self):
        logfile = os.path.join(os.path.dirname(__file__), "kernel-4.txt")
        self.assertTrue(os.path.exists(logfile))
        child = pexpect.spawn("cat", [logfile])
        message_list = LinuxKernelMessages.get_init_prompts()
        self.assertIsNotNone(message_list)
        connection = FakeConnection(child, message_list)
        with self.assertRaises(JobError):
            results = LinuxKernelMessages.parse_failures(
                connection, action=Action(), max_end_time=self.max_end_time, fail_msg=""
            )
