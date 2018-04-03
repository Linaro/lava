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
from lava_dispatcher.utils.constants import (
    KERNEL_FREE_UNUSED_MSG, KERNEL_PANIC_MSG,
    KERNEL_FREE_INIT_MSG
)
from lava_dispatcher.action import JobError
from lava_dispatcher.utils.messages import LinuxKernelMessages
from lava_dispatcher.test.test_basic import StdoutTestCase


class Kernel(object):  # pylint: disable=too-few-public-methods

    def __init__(self):
        super().__init__()
        self.existing_prompt = None

    def run(self, prompt_list):
        if not self.existing_prompt:
            self.existing_prompt = prompt_list[:]
            prompt_list = LinuxKernelMessages.get_kernel_prompts()
        if isinstance(self.existing_prompt, list):
            prompt_list.extend(self.existing_prompt)
        else:
            prompt_list.append(self.existing_prompt)
        return prompt_list


class Child(Kernel):  # pylint: disable=too-few-public-methods

    def run(self, prompt_list):
        if KERNEL_FREE_INIT_MSG in prompt_list:
            index = prompt_list.index(KERNEL_FREE_INIT_MSG)
            if len(prompt_list) > index:
                index += 1
                self.existing_prompt = prompt_list[index:]
        else:
            self.existing_prompt = prompt_list[:]
        prompt_list = LinuxKernelMessages.get_init_prompts()
        super().run(prompt_list)
        return prompt_list


class FakeConnection(object):  # pylint: disable=too-few-public-methods

    def __init__(self, child, prompt_str):
        super().__init__()
        self.raw_connection = child
        self.prompt_str = prompt_str
        self.check_char = '#'
        self.faketimeout = 30
        self.connected = True
        self.name = "fake-connection"

    def sendline(self, s='', delay=0):  # pylint: disable=invalid-name
        pass

    def force_prompt_wait(self, remaining=None):  # pylint: disable=unused-argument
        return self.wait()

    def wait(self, max_end_time=None):  # pylint: disable=unused-argument
        ret = None
        try:
            ret = self.raw_connection.expect(self.prompt_str, timeout=self.faketimeout)
        except pexpect.EOF:
            pass
        return ret


class TestBootMessages(StdoutTestCase):  # pylint: disable=too-many-public-methods

    def setUp(self):
        super().setUp()
        self.max_end_time = time.time() + 30

    def test_existing_prompt(self):
        kernel = Kernel()
        prompt_list = kernel.run(['root@debian:'])
        self.assertIn(KERNEL_FREE_INIT_MSG, prompt_list)
        child = Child()
        prompt_list = child.run(prompt_list)
        self.assertNotIn(KERNEL_FREE_INIT_MSG, prompt_list)

    def test_kernel_txt(self):
        """
        The same logfile passes kernel boot and fails
        to find init - so the panic needs to be caught by InitMessages
        """
        logfile = os.path.join(os.path.dirname(__file__), 'kernel-panic.txt')
        self.assertTrue(os.path.exists(logfile))
        child = pexpect.spawn('cat', [logfile])
        message_list = LinuxKernelMessages.get_kernel_prompts()
        self.assertIsNotNone(message_list)
        self.assertIn(LinuxKernelMessages.MESSAGE_CHOICES[0][1], message_list)
        self.assertIn(LinuxKernelMessages.MESSAGE_CHOICES[1][1], message_list)
        self.assertIn(LinuxKernelMessages.MESSAGE_CHOICES[2][1], message_list)
        self.assertIn(LinuxKernelMessages.MESSAGE_CHOICES[3][1], message_list)
        self.assertIn(LinuxKernelMessages.MESSAGE_CHOICES[4][1], message_list)
        self.assertIn(LinuxKernelMessages.MESSAGE_CHOICES[5][1], message_list)
        connection = FakeConnection(child, message_list)
        with self.assertRaises(JobError):
            result = LinuxKernelMessages.parse_failures(connection, max_end_time=self.max_end_time)

    def test_kernel_1(self):
        logfile = os.path.join(os.path.dirname(__file__), 'kernel-1.txt')
        self.assertTrue(os.path.exists(logfile))
        child = pexpect.spawn('cat', [logfile])
        message_list = LinuxKernelMessages.get_kernel_prompts()
        connection = FakeConnection(child, message_list)
        results = LinuxKernelMessages.parse_failures(connection, max_end_time=self.max_end_time)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0],
                         {'message': 'kernel-messages',
                          'success': 'Freeing unused kernel memory'})

    def test_kernel_2(self):
        logfile = os.path.join(os.path.dirname(__file__), 'kernel-2.txt')
        self.assertTrue(os.path.exists(logfile))
        child = pexpect.spawn('cat', [logfile])
        message_list = LinuxKernelMessages.get_kernel_prompts()
        self.assertIsNotNone(message_list)
        self.assertIn(LinuxKernelMessages.MESSAGE_CHOICES[0][1], message_list)
        self.assertIn(LinuxKernelMessages.MESSAGE_CHOICES[1][1], message_list)
        self.assertIn(LinuxKernelMessages.MESSAGE_CHOICES[2][1], message_list)
        self.assertIn(LinuxKernelMessages.MESSAGE_CHOICES[3][1], message_list)
        self.assertIn(LinuxKernelMessages.MESSAGE_CHOICES[4][1], message_list)
        self.assertIn(LinuxKernelMessages.MESSAGE_CHOICES[5][1], message_list)
        connection = FakeConnection(child, message_list)
        results = LinuxKernelMessages.parse_failures(connection, max_end_time=self.max_end_time)
        self.assertEqual(len(list(results)), 14)
        message_list = LinuxKernelMessages.get_init_prompts()
        child = pexpect.spawn('cat', [logfile])
        connection = FakeConnection(child, message_list)
        results = LinuxKernelMessages.parse_failures(connection, max_end_time=self.max_end_time)
        self.assertEqual(len(list(results)), 13)

    def test_kernel_4(self):
        logfile = os.path.join(os.path.dirname(__file__), 'kernel-4.txt')
        self.assertTrue(os.path.exists(logfile))
        child = pexpect.spawn('cat', [logfile])
        message_list = LinuxKernelMessages.get_init_prompts()
        self.assertIsNotNone(message_list)
        connection = FakeConnection(child, message_list)
        with self.assertRaises(JobError):
            results = LinuxKernelMessages.parse_failures(connection, max_end_time=self.max_end_time)
