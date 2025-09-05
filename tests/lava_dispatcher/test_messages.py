# Copyright (C) 2016 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import os
import time
from shlex import quote as shlex_quote
from unittest.mock import MagicMock

from pexpect import EOF as pexpect_eof

from lava_common.exceptions import JobError
from lava_common.timeout import Timeout
from lava_dispatcher.action import Action
from lava_dispatcher.shell import ShellCommand, ShellSession
from lava_dispatcher.utils.messages import LinuxKernelMessages
from tests.lava_dispatcher.test_basic import LavaDispatcherTestCase


def create_shell_session_cat_file(
    file_to_cat: str, pexpect_patterns: list[str]
) -> ShellSession:
    shell_command = ShellCommand(
        f"cat {shlex_quote(file_to_cat)}",
        Timeout("test-cat-command", None),
        logger=MagicMock(),
    )

    shell_session = ShellSession(shell_command)
    pexpect_patterns.append(pexpect_eof)
    shell_session.prompt_str = pexpect_patterns

    return shell_session


class TestBootMessages(LavaDispatcherTestCase):
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
        message_list = LinuxKernelMessages.get_init_prompts()
        self.assertIsNotNone(message_list)
        connection = create_shell_session_cat_file(logfile, message_list)
        with self.assertRaises(JobError) as exc:
            LinuxKernelMessages.parse_failures(
                connection,
                action=Action(self.create_job_mock()),
                max_end_time=self.max_end_time,
                fail_msg="",
            )
        data = str(exc.exception).splitlines()
        assert len(data) == 28
        assert (
            data[0]
            == "[    4.946791] Kernel panic - not syncing: Attempted to kill init! exitcode=0x00000200"
        )
        assert (
            data[-1]
            == "[    5.123884] ---[ end Kernel panic - not syncing: Attempted to kill init! exitcode=0x00000200"
        )

    def test_kernel_1(self):
        logfile = os.path.join(os.path.dirname(__file__), "kernel-1.txt")
        self.assertTrue(os.path.exists(logfile))
        message_list = LinuxKernelMessages.get_init_prompts()
        connection = create_shell_session_cat_file(logfile, message_list)
        results = LinuxKernelMessages.parse_failures(
            connection,
            action=Action(self.create_job_mock()),
            max_end_time=self.max_end_time,
            fail_msg="",
        )
        self.assertEqual(results, [])

    def test_kernel_2(self):
        logfile = os.path.join(os.path.dirname(__file__), "kernel-2.txt")
        self.assertTrue(os.path.exists(logfile))
        message_list = LinuxKernelMessages.get_init_prompts()
        self.assertIsNotNone(message_list)
        connection = create_shell_session_cat_file(logfile, message_list)
        results = LinuxKernelMessages.parse_failures(
            connection,
            action=Action(self.create_job_mock()),
            max_end_time=self.max_end_time,
            fail_msg="",
        )

        self.assertEqual(len(results), 14)
        self.assertEqual(results[0]["kind"], "warning")
        self.assertTrue("cut here" in results[0]["message"])
        self.assertTrue("end trace" in results[0]["message"])
        self.assertEqual(results[1]["kind"], "warning")
        self.assertEqual(results[2]["kind"], "warning")
        self.assertEqual(results[3]["kind"], "warning")
        self.assertEqual(results[4]["kind"], "warning")
        self.assertEqual(results[5]["kind"], "warning")
        self.assertEqual(results[6]["kind"], "warning")
        self.assertEqual(results[7]["kind"], "warning")
        self.assertEqual(results[8]["kind"], "bug")
        self.assertEqual(results[9]["kind"], "warning")
        self.assertEqual(results[10]["kind"], "warning")
        self.assertEqual(results[11]["kind"], "warning")
        self.assertEqual(results[12]["kind"], "warning")
        self.assertEqual(results[13]["kind"], "warning")

    def test_kernel_2_with_fail_msg(self):
        logfile = os.path.join(os.path.dirname(__file__), "kernel-2.txt")
        self.assertTrue(os.path.exists(logfile))
        message_list = LinuxKernelMessages.get_init_prompts()
        self.assertIsNotNone(message_list)
        connection = create_shell_session_cat_file(logfile, message_list)
        results = LinuxKernelMessages.parse_failures(
            connection,
            action=Action(self.create_job_mock()),
            max_end_time=self.max_end_time,
            fail_msg="Nothing to match",
        )

        self.assertEqual(len(results), 14)
        self.assertEqual(results[0]["kind"], "warning")
        self.assertTrue("cut here" in results[0]["message"])
        self.assertTrue("end trace" in results[0]["message"])
        self.assertEqual(results[1]["kind"], "warning")
        self.assertEqual(results[2]["kind"], "warning")
        self.assertEqual(results[3]["kind"], "warning")
        self.assertEqual(results[4]["kind"], "warning")
        self.assertEqual(results[5]["kind"], "warning")
        self.assertEqual(results[6]["kind"], "warning")
        self.assertEqual(results[7]["kind"], "warning")
        self.assertEqual(results[8]["kind"], "bug")
        self.assertEqual(results[9]["kind"], "warning")
        self.assertEqual(results[10]["kind"], "warning")
        self.assertEqual(results[11]["kind"], "warning")
        self.assertEqual(results[12]["kind"], "warning")
        self.assertEqual(results[13]["kind"], "warning")

    def test_kernel_4(self):
        logfile = os.path.join(os.path.dirname(__file__), "kernel-4.txt")
        self.assertTrue(os.path.exists(logfile))
        message_list = LinuxKernelMessages.get_init_prompts()
        self.assertIsNotNone(message_list)
        connection = create_shell_session_cat_file(logfile, message_list)
        with self.assertRaises(JobError) as exc:
            LinuxKernelMessages.parse_failures(
                connection,
                action=Action(self.create_job_mock()),
                max_end_time=self.max_end_time,
                fail_msg="",
            )
        assert (
            str(exc.exception)
            == """[  145.750074] Kernel panic - not syncing: Attempted to kill init! exitcode=0x00000200\r
[  145.750074]\r
[  145.759694] ---[ end Kernel panic - not syncing: Attempted to kill init! exitcode=0x00000200"""
        )

    def test_kernel_5(self):
        logfile = os.path.join(os.path.dirname(__file__), "kernel-5.txt")
        self.assertTrue(os.path.exists(logfile))
        message_list = LinuxKernelMessages.get_init_prompts()
        self.assertIsNotNone(message_list)
        connection = create_shell_session_cat_file(logfile, message_list)
        results = LinuxKernelMessages.parse_failures(
            connection,
            action=Action(self.create_job_mock()),
            max_end_time=self.max_end_time,
            fail_msg="",
        )
        assert results == []

    def test_kernel_kasan(self):
        logfile = os.path.join(os.path.dirname(__file__), "kernel-kasan.txt")
        self.assertTrue(os.path.exists(logfile))
        message_list = LinuxKernelMessages.get_init_prompts()
        self.assertIsNotNone(message_list)
        connection = create_shell_session_cat_file(logfile, message_list)
        results = LinuxKernelMessages.parse_failures(
            connection,
            action=Action(self.create_job_mock()),
            max_end_time=self.max_end_time,
            fail_msg="",
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["kind"], "kasan")
        self.assertTrue(
            results[0]["message"].startswith(
                "[   92.229826] BUG: KASAN: slab-out-of-bounds in kmalloc_oob_right+0x190/0x3b8"
            )
        )
        self.assertTrue(
            results[0]["message"].endswith(
                "=================================================================="
            )
        )

    def test_kernel_kfence(self):
        logfile = os.path.join(os.path.dirname(__file__), "kernel-kfence.txt")
        self.assertTrue(os.path.exists(logfile))
        message_list = LinuxKernelMessages.get_init_prompts()
        self.assertIsNotNone(message_list)
        connection = create_shell_session_cat_file(logfile, message_list)
        results = LinuxKernelMessages.parse_failures(
            connection,
            action=Action(self.create_job_mock()),
            max_end_time=self.max_end_time,
            fail_msg="",
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["kind"], "kfence")
        self.assertTrue(
            results[0]["message"].startswith(
                "[   39.998586] BUG: KFENCE: memory corruption in kfree+0x8c/0x174"
            )
        )
        self.assertTrue(
            results[0]["message"].endswith(
                "=================================================================="
            )
        )

    def test_kernel_bug(self):
        logfile = os.path.join(os.path.dirname(__file__), "kernel-bug.txt")
        self.assertTrue(os.path.exists(logfile))
        message_list = LinuxKernelMessages.get_init_prompts()
        self.assertIsNotNone(message_list)
        connection = create_shell_session_cat_file(logfile, message_list)
        results = LinuxKernelMessages.parse_failures(
            connection,
            action=Action(self.create_job_mock()),
            max_end_time=self.max_end_time,
            fail_msg="",
        )
        self.assertEqual(len(results), 6)
        for res in results:
            self.assertEqual(res["kind"], "bug")
            self.assertTrue(res["message"].startswith("[   "))

    def test_kernel_oops(self):
        logfile = os.path.join(os.path.dirname(__file__), "kernel-oops.txt")
        self.assertTrue(os.path.exists(logfile))
        message_list = LinuxKernelMessages.get_init_prompts()
        self.assertIsNotNone(message_list)
        connection = create_shell_session_cat_file(logfile, message_list)
        results = LinuxKernelMessages.parse_failures(
            connection,
            action=Action(self.create_job_mock()),
            max_end_time=self.max_end_time,
            fail_msg="",
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["kind"], "oops")
        self.assertTrue(
            results[0]["message"].startswith(
                "[   14.446502] ------------[ cut here ]------------"
            )
        )
        self.assertTrue(
            results[0]["message"].endswith(
                "[   36.213248] ---[ end trace 1bd963a5953b065c ]---"
            )
        )

    def test_kernel_many_errors(self):
        logfile = os.path.join(os.path.dirname(__file__), "kernel-many-errors.txt")
        self.assertTrue(os.path.exists(logfile))
        message_list = LinuxKernelMessages.get_init_prompts()
        self.assertIsNotNone(message_list)
        connection = create_shell_session_cat_file(logfile, message_list)
        results = LinuxKernelMessages.parse_failures(
            connection,
            action=Action(self.create_job_mock()),
            max_end_time=self.max_end_time,
            fail_msg="",
        )

        self.assertEqual(len(results), 4)
        self.assertEqual(results[0]["kind"], "oops")
        self.assertTrue(
            results[0]["message"].startswith(
                "[   14.446502] ------------[ cut here ]------------"
            )
        )
        self.assertTrue(
            results[0]["message"].endswith(
                "[   36.213248] ---[ end trace 1bd963a5953b065c ]---"
            )
        )
        self.assertEqual(results[1]["kind"], "bug")
        self.assertEqual(
            results[1]["message"],
            "[   39.006114] BUG: spinlock lockup suspected on CPU#4, swapper/4/0",
        )
        self.assertEqual(results[2]["kind"], "oops")
        self.assertEqual(
            results[2]["message"],
            "[   14.461360] Internal error: Oops - BUG: 0 [#1] PREEMPT SMP",
        )
        self.assertEqual(results[3]["kind"], "bug")
        self.assertEqual(
            results[3]["message"],
            "[   15.447835] BUG: spinlock lockup suspected on CPU#3, gdbus/2329",
        )

    def test_kernel_lkft(self):
        logfile = os.path.join(os.path.dirname(__file__), "kernel-lkft.txt")
        self.assertTrue(os.path.exists(logfile))
        message_list = LinuxKernelMessages.get_init_prompts()
        self.assertIsNotNone(message_list)
        connection = create_shell_session_cat_file(logfile, message_list)
        results = LinuxKernelMessages.parse_failures(
            connection,
            action=Action(self.create_job_mock()),
            max_end_time=self.max_end_time,
            fail_msg="",
        )
        self.assertEqual(len(results), 134)

    def test_kernel_panic_and_reset_overlapped(self):
        logfile = os.path.join(
            os.path.dirname(__file__), "kernel-panic-and-reset-overlapped.txt"
        )
        self.assertTrue(os.path.exists(logfile))
        message_list = LinuxKernelMessages.get_init_prompts()
        self.assertIsNotNone(message_list)
        connection = create_shell_session_cat_file(logfile, message_list)
        custom_fail_msg = r"coreboot-.*bootblock starting"
        with self.assertRaises(JobError) as exc:
            LinuxKernelMessages.parse_failures(
                connection,
                action=Action(self.create_job_mock()),
                max_end_time=self.max_end_time,
                fail_msg=custom_fail_msg,
            )
        assert (
            str(exc.exception)
            == """[    5.867574] Kernel panic - not syncing: Fatal exception\r
[    5.873722] Kernel Offset: 0x3bc00000 from 0xffffffff81000000 (relocation range: 0xffffffff80000000-0xffffffffbfffffff)\r
[    5.886443] gsmi: Log Shutdown Reason 0x02\r
coreboot-v1.9308_26_0.0.22-18730-gcb819b1082 Tue May  4 00:08:52 UTC 2021 bootblock starting"""
        )

    def test_kernel_kasan_and_reset_overlapped(self):
        logfile = os.path.join(
            os.path.dirname(__file__), "kernel-kasan-and-reset-overlap.txt"
        )
        self.assertTrue(os.path.exists(logfile))
        message_list = LinuxKernelMessages.get_init_prompts()
        self.assertIsNotNone(message_list)
        connection = create_shell_session_cat_file(logfile, message_list)
        custom_fail_msg = r"coreboot-.*bootblock starting"
        with self.assertRaises(JobError) as exc:
            LinuxKernelMessages.parse_failures(
                connection,
                action=Action(self.create_job_mock()),
                max_end_time=self.max_end_time,
                fail_msg=custom_fail_msg,
            )
        assert (
            str(exc.exception)
            == "Matched job-specific failure message: 'coreboot-.*bootblock starting'"
        )
