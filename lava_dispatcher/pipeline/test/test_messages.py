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
import unittest
import pexpect
from lava_dispatcher.pipeline.utils.constants import (
    KERNEL_FREE_UNUSED_MSG, KERNEL_PANIC_MSG,
    KERNEL_FREE_INIT_MSG
)
from lava_dispatcher.pipeline.utils.messages import LinuxKernelMessages


class Kernel(object):  # pylint: disable=too-few-public-methods

    def __init__(self):
        super(Kernel, self).__init__()
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
        super(Child, self).run(prompt_list)
        return prompt_list


class FakeConnection(object):  # pylint: disable=too-few-public-methods

    def __init__(self, child, prompt_str):
        super(FakeConnection, self).__init__()
        self.raw_connection = child
        self.prompt_str = prompt_str
        self.check_char = '#'
        self.timeout = 30

    def sendline(self, s='', delay=0, send_char=True):  # pylint: disable=invalid-name
        pass

    def wait(self):
        return self.raw_connection.expect(self.prompt_str, timeout=self.timeout)


class TestBootMessages(unittest.TestCase):

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
        logfile = os.path.join(os.path.dirname(__file__), 'kernel.txt')
        self.assertTrue(os.path.exists(logfile))
        child = pexpect.spawn('cat', [logfile])
        message_list = LinuxKernelMessages.get_kernel_prompts()
        self.assertIsNotNone(message_list)
        connection = FakeConnection(child, message_list)
        result = LinuxKernelMessages.parse_failures(connection)
        self.assertIn('success', result[0])
        self.assertEqual(result[0]['success'], KERNEL_FREE_UNUSED_MSG)
        message_list = LinuxKernelMessages.get_init_prompts()
        self.assertIn(KERNEL_PANIC_MSG, message_list)
        self.assertNotIn(KERNEL_FREE_UNUSED_MSG, message_list)
        connection.prompt_str = message_list
        result = LinuxKernelMessages.parse_failures(connection)
        self.assertEqual(len(result), 1)
        self.assertIn('panic', result[0])
        self.assertIn('message', result[0])
        self.assertTrue('Attempted to kill init' in str(result[0]['message']))
        self.assertTrue('(unwind_backtrace) from' in str(result[0]['message']))

    def test_kernel_2(self):
        logfile = os.path.join(os.path.dirname(__file__), 'kernel-2.txt')
        self.assertTrue(os.path.exists(logfile))
        child = pexpect.spawn('cat', [logfile])
        message_list = LinuxKernelMessages.get_kernel_prompts()
        self.assertIsNotNone(message_list)
        connection = FakeConnection(child, message_list)
        results = LinuxKernelMessages.parse_failures(connection)
        # traces as far as da227214a82491bf occur before Freeing init memory:
        self.assertEqual(len(list(results)), 9)
        message_list = LinuxKernelMessages.get_init_prompts()
        connection.prompt_str = message_list
        results = LinuxKernelMessages.parse_failures(connection)
        # 5 more traces appear during init
        self.assertEqual(len(list(results)), 5)
