#
# Copyright (C) 2017 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from django.contrib.auth.models import User
from django.test import TestCase

from lava_common.yaml import yaml_safe_dump
from lava_scheduler_app.models import Device, DeviceType, TestJob, Worker

minimal_valid_job = yaml_safe_dump(
    """
job_name: minimal valid job
visibility: public
timeouts:
  job:
    minutes: 10
  action:
    minutes: 5
actions: []
"""
)


class TestTestJobStateMachine(TestCase):
    def setUp(self):
        self.worker = Worker.objects.create(
            hostname="worker-01", state=Worker.STATE_ONLINE
        )
        self.device_type = DeviceType.objects.create(name="dt-01")
        self.device = Device.objects.create(
            hostname="device-01",
            device_type=self.device_type,
            worker_host=self.worker,
            health=Device.HEALTH_UNKNOWN,
        )
        self.user = User.objects.create(username="user-01")
        self.job = TestJob.objects.create(
            requested_device_type=self.device_type,
            submitter=self.user,
            definition=minimal_valid_job,
        )

    def check_device(self, state, health):
        self.device.refresh_from_db()
        self.assertEqual(self.device.state, state)
        self.assertEqual(self.device.health, health)

    def check_job(self, state, health):
        self.job.refresh_from_db()
        self.assertEqual(self.job.state, state)
        self.assertEqual(self.job.health, health)

    def test_job_go_state_scheduling(self):
        # Normal case
        self.device.state = Device.STATE_IDLE
        self.device.save()
        self.job.state = TestJob.STATE_SUBMITTED
        self.job.save()
        self.job.go_state_scheduling(self.device)
        self.job.save()
        self.check_device(Device.STATE_RESERVED, Device.HEALTH_UNKNOWN)
        self.check_job(TestJob.STATE_SCHEDULING, TestJob.HEALTH_UNKNOWN)

        # Test errors
        # 1/ Device already reserved
        self.job.state = TestJob.STATE_SUBMITTED
        self.job.actual_device = None
        self.job.save()
        for state, _ in Device.STATE_CHOICES:
            if state == Device.STATE_IDLE:
                continue
            self.device.state = state
            self.device.save()
            self.job.state = TestJob.STATE_SUBMITTED
            self.job.save()
            self.assertRaises(Exception, self.job.go_state_scheduling, self.device)
            self.check_device(state, Device.HEALTH_UNKNOWN)
            self.check_job(TestJob.STATE_SUBMITTED, TestJob.HEALTH_UNKNOWN)

        # 2/ job state >= TestJob.STATE_SCHEDULING
        self.job.state = TestJob.STATE_SUBMITTED
        self.job.actual_device = None
        self.job.save()
        self.device.state = Device.STATE_IDLE
        self.device.save()
        for state, _ in TestJob.STATE_CHOICES:
            if state == TestJob.STATE_SUBMITTED:
                continue
            self.job.state = state
            self.job.save()
            self.job.go_state_scheduling(self.device)
            self.job.save()
            self.check_device(Device.STATE_IDLE, Device.HEALTH_UNKNOWN)
            self.check_job(state, TestJob.HEALTH_UNKNOWN)
            self.assertEqual(self.job.actual_device, None)

    def test_job_go_state_scheduled(self):
        # Normal case
        # 1/ STATE_SUBMITTED => STATE_SCHEDULED
        self.device.state = Device.STATE_IDLE
        self.device.save()
        self.job.state = TestJob.STATE_SUBMITTED
        self.job.save()
        self.job.go_state_scheduled(self.device)
        self.job.save()
        self.check_device(Device.STATE_RESERVED, Device.HEALTH_UNKNOWN)
        self.check_job(TestJob.STATE_SCHEDULED, TestJob.HEALTH_UNKNOWN)

        # 2/ STATE_SCHEDULING => STATE_SCHEDULED
        self.device.state = Device.STATE_RESERVED
        self.device.save()
        self.job.state = TestJob.STATE_SCHEDULING
        self.job.actual_device = self.device
        self.job.save()
        self.job.go_state_scheduled()
        self.job.save()
        self.check_device(Device.STATE_RESERVED, Device.HEALTH_UNKNOWN)
        self.check_job(TestJob.STATE_SCHEDULED, TestJob.HEALTH_UNKNOWN)

        # Test errors
        # 1/ Device already reserved
        self.job.state = TestJob.STATE_SUBMITTED
        self.job.actual_device = None
        self.job.save()
        for state, _ in Device.STATE_CHOICES:
            if state == Device.STATE_IDLE:
                continue
            self.device.state = state
            self.device.save()
            self.job.state = TestJob.STATE_SUBMITTED
            self.job.save()
            self.assertRaises(Exception, self.job.go_state_scheduled, self.device)
            self.check_device(state, Device.HEALTH_UNKNOWN)
            self.check_job(TestJob.STATE_SUBMITTED, TestJob.HEALTH_UNKNOWN)

        # 2/ job state >= TestJob.STATE_SCHEDULED
        self.job.state = TestJob.STATE_SUBMITTED
        self.job.actual_device = None
        self.job.save()
        self.device.state = Device.STATE_IDLE
        self.device.save()
        for state, _ in TestJob.STATE_CHOICES:
            if state in [TestJob.STATE_SUBMITTED, TestJob.STATE_SCHEDULING]:
                continue
            self.job.state = state
            self.job.save()
            self.job.go_state_scheduled(self.device)
            self.job.save()
            self.check_device(Device.STATE_IDLE, Device.HEALTH_UNKNOWN)
            self.check_job(state, TestJob.HEALTH_UNKNOWN)
            self.assertEqual(self.job.actual_device, None)

    def test_job_go_state_running(self):
        # Normal case
        self.device.state = Device.STATE_RESERVED
        self.device.save()
        self.job.state = TestJob.STATE_SCHEDULED
        self.job.actual_device = self.device
        self.job.save()
        self.job.go_state_running()
        self.job.save()
        self.check_device(Device.STATE_RUNNING, Device.HEALTH_UNKNOWN)
        self.check_job(TestJob.STATE_RUNNING, TestJob.HEALTH_UNKNOWN)

        # Test errors
        # job state >= TestJob.STATE_RUNNING
        self.device.state = Device.STATE_RESERVED
        self.device.save()
        self.job.state = TestJob.STATE_SUBMITTED
        self.job.actual_device = self.device
        self.job.save()
        for state, _ in TestJob.STATE_CHOICES:
            if state in [
                TestJob.STATE_SUBMITTED,
                TestJob.STATE_SCHEDULING,
                TestJob.STATE_SCHEDULED,
            ]:
                continue
            self.job.state = state
            self.job.save()
            self.job.go_state_running()
            self.job.save()
            self.check_device(Device.STATE_RESERVED, Device.HEALTH_UNKNOWN)
            self.check_job(state, TestJob.HEALTH_UNKNOWN)
            self.assertEqual(self.job.actual_device, self.device)

    def test_job_go_state_canceling(self):
        # Normal case
        self.device.state = Device.STATE_RUNNING
        self.device.save()
        self.job.state = TestJob.STATE_RUNNING
        self.job.actual_device = self.device
        self.job.save()
        self.job.go_state_canceling()
        self.job.save()
        self.check_device(Device.STATE_RUNNING, Device.HEALTH_UNKNOWN)
        self.check_job(TestJob.STATE_CANCELING, TestJob.HEALTH_UNKNOWN)

        # Test errors
        # job state >= TestJob.STATE_CANCELING
        self.device.state = Device.STATE_RUNNING
        self.device.save()
        self.job.state = TestJob.STATE_RUNNING
        self.job.actual_device = self.device
        self.job.save()
        for state in [TestJob.STATE_CANCELING, TestJob.STATE_FINISHED]:
            self.job.state = state
            self.job.save()
            self.job.go_state_canceling()
            self.job.save()
            self.check_device(Device.STATE_RUNNING, Device.HEALTH_UNKNOWN)
            self.check_job(state, TestJob.HEALTH_UNKNOWN)
            self.assertEqual(self.job.actual_device, self.device)

    def test_job_go_state_canceling_health_check(self):
        # Normal case
        self.device.state = Device.STATE_RUNNING
        self.device.save()
        self.job.health_check = True
        self.job.state = TestJob.STATE_RUNNING
        self.job.actual_device = self.device
        self.job.save()
        self.job.go_state_canceling()
        self.job.save()
        self.check_device(Device.STATE_RUNNING, Device.HEALTH_UNKNOWN)
        self.check_job(TestJob.STATE_CANCELING, TestJob.HEALTH_UNKNOWN)

        # Test errors
        # job state >= TestJob.STATE_CANCELING
        self.device.state = Device.STATE_RUNNING
        self.device.save()
        self.job.state = TestJob.STATE_RUNNING
        self.job.actual_device = self.device
        self.job.save()
        for state in [TestJob.STATE_CANCELING, TestJob.STATE_FINISHED]:
            self.job.state = state
            self.job.save()
            self.job.go_state_canceling()
            self.job.save()
            self.check_device(Device.STATE_RUNNING, Device.HEALTH_UNKNOWN)
            self.check_job(state, TestJob.HEALTH_UNKNOWN)
            self.assertEqual(self.job.actual_device, self.device)

    def test_job_state_canceling_multinode(self):
        self.device2 = Device.objects.create(
            hostname="device-02", device_type=self.device_type, worker_host=self.worker
        )
        self.device3 = Device.objects.create(
            hostname="device-03", device_type=self.device_type, worker_host=self.worker
        )

        self.job.definition = yaml_safe_dump(
            {"protocols": {"lava-multinode": {"role": "master", "essential": True}}}
        )
        self.job.target_group = "target_group"
        self.job.save()
        self.sub_job1 = TestJob.objects.create(
            requested_device_type=self.device_type,
            submitter=self.user,
            target_group="target_group",
        )
        self.sub_job1.definition = yaml_safe_dump(
            {"protocols": {"lava-multinode": {"role": "worker", "essential": False}}}
        )
        self.sub_job1.actual_device = self.device2
        self.sub_job1.save()
        self.sub_job2 = TestJob.objects.create(
            requested_device_type=self.device_type,
            submitter=self.user,
            target_group="target_group",
        )
        self.sub_job2.definition = yaml_safe_dump(
            {"protocols": {"lava-multinode": {"role": "worker", "essential": False}}}
        )
        self.sub_job2.actual_device = self.device3
        self.sub_job2.save()

        # 1/ Essential role
        self.job.state = TestJob.STATE_RUNNING
        self.job.actual_device = self.device
        self.job.actual_device.state = Device.STATE_RUNNING
        self.job.actual_device.save()
        self.job.health = TestJob.HEALTH_UNKNOWN
        self.job.save()

        self.sub_job1.state = TestJob.STATE_RUNNING
        self.sub_job1.actual_device.state = Device.STATE_RUNNING
        self.sub_job1.save()
        self.sub_job1.health = TestJob.HEALTH_UNKNOWN
        self.sub_job1.save()

        self.sub_job2.state = TestJob.STATE_RUNNING
        self.sub_job2.actual_device.state = Device.STATE_RUNNING
        self.sub_job2.save()
        self.sub_job2.health = TestJob.HEALTH_UNKNOWN
        self.sub_job2.save()

        self.assertTrue(self.job.is_multinode)
        self.assertTrue(self.job.essential_role)
        self.assertTrue(self.sub_job1.is_multinode)
        self.assertFalse(self.sub_job1.essential_role)
        self.assertTrue(self.sub_job2.is_multinode)
        self.assertFalse(self.sub_job2.essential_role)

        self.job.go_state_canceling()
        self.assertEqual(self.job.state, TestJob.STATE_CANCELING)
        self.sub_job1.refresh_from_db()
        self.assertEqual(self.sub_job1.state, TestJob.STATE_CANCELING)
        self.sub_job2.refresh_from_db()
        self.assertEqual(self.sub_job2.state, TestJob.STATE_CANCELING)

        # 2/ Non-essential role
        self.job.definition = yaml_safe_dump(
            {"protocols": {"lava-multinode": {"role": "master", "essential": False}}}
        )
        self.job.state = TestJob.STATE_RUNNING
        self.job.actual_device = self.device
        self.job.actual_device.state = Device.STATE_RUNNING
        self.job.actual_device.save()
        self.job.health = TestJob.HEALTH_UNKNOWN
        self.job.save()

        self.sub_job1.state = TestJob.STATE_RUNNING
        self.sub_job1.actual_device.state = Device.STATE_RUNNING
        self.sub_job1.save()
        self.sub_job1.health = TestJob.HEALTH_UNKNOWN
        self.sub_job1.save()

        self.sub_job2.state = TestJob.STATE_RUNNING
        self.sub_job2.actual_device.state = Device.STATE_RUNNING
        self.sub_job2.save()
        self.sub_job2.health = TestJob.HEALTH_UNKNOWN
        self.sub_job2.save()

        self.assertTrue(self.job.is_multinode)
        self.assertFalse(self.job.essential_role)
        self.assertTrue(self.sub_job1.is_multinode)
        self.assertFalse(self.sub_job1.essential_role)
        self.assertTrue(self.sub_job2.is_multinode)
        self.assertFalse(self.sub_job2.essential_role)

        self.job.go_state_canceling()
        self.assertEqual(self.job.state, TestJob.STATE_CANCELING)
        self.sub_job1.refresh_from_db()
        self.assertEqual(self.sub_job1.state, TestJob.STATE_RUNNING)
        self.sub_job2.refresh_from_db()
        self.assertEqual(self.sub_job2.state, TestJob.STATE_RUNNING)

    def test_job_go_state_finished(self):
        # Normal case
        # 1/ STATE_RUNNING => STATE_FINISHED
        # 1.1/ Success
        self.device.state = Device.STATE_RUNNING
        self.device.save()
        self.job.state = TestJob.STATE_RUNNING
        self.job.actual_device = self.device
        self.job.save()
        self.job.go_state_finished(TestJob.HEALTH_COMPLETE)
        self.job.save()
        self.check_device(Device.STATE_IDLE, Device.HEALTH_UNKNOWN)
        self.check_job(TestJob.STATE_FINISHED, TestJob.HEALTH_COMPLETE)

        # 1.2/ Failure
        self.device.state = Device.STATE_RUNNING
        self.device.health = Device.HEALTH_GOOD
        self.device.save()
        self.job.state = TestJob.STATE_RUNNING
        self.job.actual_device = self.device
        self.job.save()
        self.job.go_state_finished(TestJob.HEALTH_INCOMPLETE)
        self.job.save()
        self.check_device(Device.STATE_IDLE, Device.HEALTH_GOOD)
        self.check_job(TestJob.STATE_FINISHED, TestJob.HEALTH_INCOMPLETE)

        # 1.3/ Infrastructure error
        self.device.state = Device.STATE_RUNNING
        self.device.health = Device.HEALTH_GOOD
        self.device.save()
        self.job.state = TestJob.STATE_RUNNING
        self.job.actual_device = self.device
        self.job.save()
        self.job.go_state_finished(TestJob.HEALTH_COMPLETE, True)
        self.job.save()
        self.check_device(Device.STATE_IDLE, Device.HEALTH_UNKNOWN)
        self.check_job(TestJob.STATE_FINISHED, TestJob.HEALTH_COMPLETE)

        self.device.state = Device.STATE_RUNNING
        self.device.health = Device.HEALTH_GOOD
        self.device.save()
        self.job.state = TestJob.STATE_RUNNING
        self.job.actual_device = self.device
        self.job.save()
        self.job.go_state_finished(TestJob.HEALTH_INCOMPLETE, True)
        self.job.save()
        self.check_device(Device.STATE_IDLE, Device.HEALTH_UNKNOWN)
        self.check_job(TestJob.STATE_FINISHED, TestJob.HEALTH_INCOMPLETE)

        # For health check, an Infrastructure error will not change the device health
        self.device.state = Device.STATE_RUNNING
        self.device.health = Device.HEALTH_GOOD
        self.device.save()
        self.job.state = TestJob.STATE_RUNNING
        self.job.actual_device = self.device
        self.job.health_check = True
        self.job.save()
        self.job.go_state_finished(TestJob.HEALTH_INCOMPLETE, True)
        self.job.save()
        self.check_device(Device.STATE_IDLE, Device.HEALTH_BAD)
        self.check_job(TestJob.STATE_FINISHED, TestJob.HEALTH_INCOMPLETE)
        self.job.health_check = False
        self.job.save()

        # 2/ STATE_CANCELING => STATE_FINISHED
        # 2.1/ Success
        self.device.state = Device.STATE_RUNNING
        self.device.health = Device.HEALTH_UNKNOWN
        self.device.save()
        self.job.state = TestJob.STATE_CANCELING
        self.job.actual_device = self.device
        self.job.save()
        self.job.go_state_finished(TestJob.HEALTH_COMPLETE)
        self.job.save()
        self.check_device(Device.STATE_IDLE, Device.HEALTH_UNKNOWN)
        self.check_job(TestJob.STATE_FINISHED, TestJob.HEALTH_CANCELED)

        # 2.2/ Failure
        self.device.state = Device.STATE_RUNNING
        self.device.save()
        self.job.state = TestJob.STATE_CANCELING
        self.job.actual_device = self.device
        self.job.save()
        self.job.go_state_finished(TestJob.HEALTH_INCOMPLETE)
        self.job.save()
        self.check_device(Device.STATE_IDLE, Device.HEALTH_UNKNOWN)
        self.check_job(TestJob.STATE_FINISHED, TestJob.HEALTH_CANCELED)

        # 2.3/ Success of an health-check
        self.device.state = Device.STATE_RUNNING
        self.device.health = Device.HEALTH_UNKNOWN
        self.device.save()
        self.job.health_check = True
        self.job.state = TestJob.STATE_CANCELING
        self.job.actual_device = self.device
        self.job.save()
        self.job.go_state_finished(TestJob.HEALTH_COMPLETE)
        self.job.save()
        self.check_device(Device.STATE_IDLE, Device.HEALTH_BAD)
        self.check_job(TestJob.STATE_FINISHED, TestJob.HEALTH_CANCELED)

        # 2.2/ Failure
        self.device.state = Device.STATE_RUNNING
        self.device.health = Device.HEALTH_UNKNOWN
        self.device.save()
        self.job.health_check = True
        self.job.state = TestJob.STATE_CANCELING
        self.job.actual_device = self.device
        self.job.save()
        self.job.go_state_finished(TestJob.HEALTH_INCOMPLETE)
        self.job.save()
        self.check_device(Device.STATE_IDLE, Device.HEALTH_BAD)
        self.check_job(TestJob.STATE_FINISHED, TestJob.HEALTH_CANCELED)

        # Test errors
        # 1/ already finished
        self.device.state = Device.STATE_IDLE
        self.device.health = Device.HEALTH_UNKNOWN
        self.device.save()
        self.job.health_check = False
        self.job.state = TestJob.STATE_FINISHED
        self.job.health = TestJob.HEALTH_UNKNOWN
        self.job.actual_device = self.device
        self.job.save()
        self.job.go_state_finished(TestJob.HEALTH_INCOMPLETE)
        self.job.save()
        self.check_device(Device.STATE_IDLE, Device.HEALTH_UNKNOWN)
        self.check_job(TestJob.STATE_FINISHED, TestJob.HEALTH_UNKNOWN)

        # 2/ Passing HEALTH_UNKNOWN
        self.device.state = Device.STATE_RUNNING
        self.device.save()
        self.job.state = TestJob.STATE_RUNNING
        self.job.health = TestJob.HEALTH_UNKNOWN
        self.job.actual_device = self.device
        self.job.save()
        self.assertRaises(Exception, self.job.go_state_finished, TestJob.HEALTH_UNKNOWN)
        self.job.save()
        self.check_device(Device.STATE_RUNNING, Device.HEALTH_UNKNOWN)
        self.check_job(TestJob.STATE_RUNNING, TestJob.HEALTH_UNKNOWN)

        # 3/ start_time is None
        self.device.state = Device.STATE_RESERVED
        self.device.save()
        self.job.state = TestJob.STATE_SCHEDULED
        self.job.start_time = self.job.end_time = None
        self.job.actual_device = self.device
        self.job.save()
        self.job.go_state_finished(TestJob.HEALTH_INCOMPLETE)
        self.job.save()
        self.check_device(Device.STATE_IDLE, Device.HEALTH_UNKNOWN)
        self.check_job(TestJob.STATE_FINISHED, TestJob.HEALTH_INCOMPLETE)
        self.assertIsNotNone(self.job.start_time)
        self.assertEqual(self.job.start_time, self.job.end_time)

    def test_job_go_state_finished_health_check(self):
        # Normal case
        # 1/ STATE_RUNNING => STATE_FINISHED
        # 1.1/ Success
        self.device.state = Device.STATE_RUNNING
        self.device.health = Device.HEALTH_UNKNOWN
        self.device.save()
        self.job.state = TestJob.STATE_RUNNING
        self.job.actual_device = self.device
        self.job.health_check = True
        self.job.save()
        self.job.go_state_finished(TestJob.HEALTH_COMPLETE)
        self.job.save()
        self.check_device(Device.STATE_IDLE, Device.HEALTH_GOOD)
        self.check_job(TestJob.STATE_FINISHED, TestJob.HEALTH_COMPLETE)

        # 1.2/ Failure
        self.device.state = Device.STATE_RUNNING
        self.device.health = Device.HEALTH_GOOD
        self.device.save()
        self.job.state = TestJob.STATE_RUNNING
        self.job.actual_device = self.device
        self.job.health_check = True
        self.job.save()
        self.job.go_state_finished(TestJob.HEALTH_INCOMPLETE)
        self.job.save()
        self.check_device(Device.STATE_IDLE, Device.HEALTH_BAD)
        self.check_job(TestJob.STATE_FINISHED, TestJob.HEALTH_INCOMPLETE)

    def test_job_go_state_finished_health_check_looping(self):
        # Normal case
        # 1/ STATE_RUNNING => STATE_FINISHED
        # 1.1/ Success
        self.device.state = Device.STATE_RUNNING
        self.device.health = Device.HEALTH_LOOPING
        self.device.save()
        self.job.state = TestJob.STATE_RUNNING
        self.job.actual_device = self.device
        self.job.health_check = True
        self.job.save()
        self.job.go_state_finished(TestJob.HEALTH_COMPLETE)
        self.job.save()
        self.check_device(Device.STATE_IDLE, Device.HEALTH_LOOPING)
        self.check_job(TestJob.STATE_FINISHED, TestJob.HEALTH_COMPLETE)

        # 1.2/ Failure
        self.device.state = Device.STATE_RUNNING
        self.device.health = Device.HEALTH_LOOPING
        self.device.save()
        self.job.state = TestJob.STATE_RUNNING
        self.job.actual_device = self.device
        self.job.health_check = True
        self.job.save()
        self.job.go_state_finished(TestJob.HEALTH_INCOMPLETE)
        self.job.save()
        # looping is persistent
        self.check_device(Device.STATE_IDLE, Device.HEALTH_LOOPING)
        self.check_job(TestJob.STATE_FINISHED, TestJob.HEALTH_INCOMPLETE)

    def test_job_go_state_finished_multinode(self):
        # 1/ Essential role
        self.device2 = Device.objects.create(
            hostname="device-02", device_type=self.device_type
        )
        self.device3 = Device.objects.create(
            hostname="device-03", device_type=self.device_type
        )

        self.job.definition = yaml_safe_dump(
            {"protocols": {"lava-multinode": {"role": "master", "essential": True}}}
        )
        self.job.target_group = "target_group"
        self.job.save()
        self.sub_job1 = TestJob.objects.create(
            requested_device_type=self.device_type,
            submitter=self.user,
            target_group="target_group",
        )
        self.sub_job1.definition = yaml_safe_dump(
            {"protocols": {"lava-multinode": {"role": "worker", "essential": False}}}
        )
        self.sub_job1.actual_device = self.device2
        self.sub_job1.save()
        self.sub_job2 = TestJob.objects.create(
            requested_device_type=self.device_type,
            submitter=self.user,
            target_group="target_group",
        )
        self.sub_job2.definition = yaml_safe_dump(
            {"protocols": {"lava-multinode": {"role": "worker", "essential": False}}}
        )
        self.sub_job2.actual_device = self.device3
        self.sub_job2.save()

        # 1/ Essential role
        # 1.1/ Success
        self.job.state = TestJob.STATE_RUNNING
        self.job.actual_device = self.device
        self.job.actual_device.state = Device.STATE_RUNNING
        self.job.actual_device.save()
        self.job.health = TestJob.HEALTH_UNKNOWN
        self.job.save()

        self.sub_job1.state = TestJob.STATE_RUNNING
        self.sub_job1.actual_device.state = Device.STATE_RUNNING
        self.sub_job1.save()
        self.sub_job1.health = TestJob.HEALTH_UNKNOWN
        self.sub_job1.save()

        self.sub_job2.state = TestJob.STATE_RUNNING
        self.sub_job2.actual_device.state = Device.STATE_RUNNING
        self.sub_job2.save()
        self.sub_job2.health = TestJob.HEALTH_UNKNOWN
        self.sub_job2.save()

        self.assertTrue(self.job.is_multinode)
        self.assertTrue(self.job.essential_role)
        self.assertTrue(self.sub_job1.is_multinode)
        self.assertFalse(self.sub_job1.essential_role)
        self.assertTrue(self.sub_job2.is_multinode)
        self.assertFalse(self.sub_job2.essential_role)

        self.job.go_state_finished(TestJob.HEALTH_COMPLETE)
        self.assertEqual(self.job.state, TestJob.STATE_FINISHED)
        self.sub_job1.refresh_from_db()
        self.assertEqual(self.sub_job1.state, TestJob.STATE_RUNNING)
        self.sub_job2.refresh_from_db()
        self.assertEqual(self.sub_job2.state, TestJob.STATE_RUNNING)

        # 1.2/ Failure
        self.job.state = TestJob.STATE_RUNNING
        self.job.actual_device = self.device
        self.job.actual_device.state = Device.STATE_RUNNING
        self.job.actual_device.save()
        self.job.health = TestJob.HEALTH_UNKNOWN
        self.job.save()

        self.sub_job1.state = TestJob.STATE_RUNNING
        self.sub_job1.actual_device.state = Device.STATE_RUNNING
        self.sub_job1.save()
        self.sub_job1.health = TestJob.HEALTH_UNKNOWN
        self.sub_job1.save()

        self.sub_job2.state = TestJob.STATE_RUNNING
        self.sub_job2.actual_device.state = Device.STATE_RUNNING
        self.sub_job2.save()
        self.sub_job2.health = TestJob.HEALTH_UNKNOWN
        self.sub_job2.save()

        self.assertTrue(self.job.is_multinode)
        self.assertTrue(self.job.essential_role)
        self.assertTrue(self.sub_job1.is_multinode)
        self.assertFalse(self.sub_job1.essential_role)
        self.assertTrue(self.sub_job2.is_multinode)
        self.assertFalse(self.sub_job2.essential_role)

        self.job.go_state_finished(TestJob.HEALTH_INCOMPLETE)
        self.assertEqual(self.job.state, TestJob.STATE_FINISHED)
        self.sub_job1.refresh_from_db()
        self.assertEqual(self.sub_job1.state, TestJob.STATE_CANCELING)
        self.sub_job2.refresh_from_db()
        self.assertEqual(self.sub_job2.state, TestJob.STATE_CANCELING)

        # 2/ Non-essential role
        # 1.1/ Success
        self.job.definition = yaml_safe_dump(
            {"protocols": {"lava-multinode": {"role": "master", "essential": False}}}
        )
        self.job.state = TestJob.STATE_RUNNING
        self.job.actual_device = self.device
        self.job.actual_device.state = Device.STATE_RUNNING
        self.job.actual_device.save()
        self.job.health = TestJob.HEALTH_UNKNOWN
        self.job.save()

        self.sub_job1.state = TestJob.STATE_RUNNING
        self.sub_job1.actual_device.state = Device.STATE_RUNNING
        self.sub_job1.save()
        self.sub_job1.health = TestJob.HEALTH_UNKNOWN
        self.sub_job1.save()

        self.sub_job2.state = TestJob.STATE_RUNNING
        self.sub_job2.actual_device.state = Device.STATE_RUNNING
        self.sub_job2.save()
        self.sub_job2.health = TestJob.HEALTH_UNKNOWN
        self.sub_job2.save()

        self.assertTrue(self.job.is_multinode)
        self.assertFalse(self.job.essential_role)
        self.assertTrue(self.sub_job1.is_multinode)
        self.assertFalse(self.sub_job1.essential_role)
        self.assertTrue(self.sub_job2.is_multinode)
        self.assertFalse(self.sub_job2.essential_role)

        self.job.go_state_finished(TestJob.HEALTH_COMPLETE)
        self.assertEqual(self.job.state, TestJob.STATE_FINISHED)
        self.sub_job1.refresh_from_db()
        self.assertEqual(self.sub_job1.state, TestJob.STATE_RUNNING)
        self.sub_job2.refresh_from_db()
        self.assertEqual(self.sub_job2.state, TestJob.STATE_RUNNING)

        # 1.2/ Failure
        self.job.state = TestJob.STATE_RUNNING
        self.job.actual_device = self.device
        self.job.actual_device.state = Device.STATE_RUNNING
        self.job.actual_device.save()
        self.job.health = TestJob.HEALTH_UNKNOWN
        self.job.save()

        self.sub_job1.state = TestJob.STATE_RUNNING
        self.sub_job1.actual_device.state = Device.STATE_RUNNING
        self.sub_job1.save()
        self.sub_job1.health = TestJob.HEALTH_UNKNOWN
        self.sub_job1.save()

        self.sub_job2.state = TestJob.STATE_RUNNING
        self.sub_job2.actual_device.state = Device.STATE_RUNNING
        self.sub_job2.save()
        self.sub_job2.health = TestJob.HEALTH_UNKNOWN
        self.sub_job2.save()

        self.assertTrue(self.job.is_multinode)
        self.assertFalse(self.job.essential_role)
        self.assertTrue(self.sub_job1.is_multinode)
        self.assertFalse(self.sub_job1.essential_role)
        self.assertTrue(self.sub_job2.is_multinode)
        self.assertFalse(self.sub_job2.essential_role)

        self.job.go_state_finished(TestJob.HEALTH_INCOMPLETE)
        self.assertEqual(self.job.state, TestJob.STATE_FINISHED)
        self.sub_job1.refresh_from_db()
        self.assertEqual(self.sub_job1.state, TestJob.STATE_RUNNING)
        self.sub_job2.refresh_from_db()
        self.assertEqual(self.sub_job2.state, TestJob.STATE_RUNNING)

    def test_job_remove_job(self):
        self.device.state = Device.STATE_RUNNING
        self.device.save()
        self.job.state = TestJob.STATE_RUNNING
        self.job.actual_device = self.device
        self.job.save()
        self.assertEqual(self.device.hostname, self.job.actual_device.hostname)
        self.assertEqual(self.job.id, self.device.current_job().id)
        self.device.refresh_from_db()
        self.assertEqual(self.job.id, self.device.current_job().id)
        self.job.delete()
        self.check_device(Device.STATE_IDLE, Device.HEALTH_UNKNOWN)
        self.assertIsNone(self.device.current_job())


class TestWorkerStateMachine(TestCase):
    def setUp(self):
        self.worker = Worker.objects.create(hostname="worker-01")
        self.device_type = DeviceType.objects.create(name="dt-01")
        self.device = Device.objects.create(
            hostname="device-01",
            device_type=self.device_type,
            worker_host=self.worker,
            health=Device.HEALTH_UNKNOWN,
        )
        self.user = User.objects.create(username="user-01")
        self.job = TestJob.objects.create(
            requested_device_type=self.device_type, submitter=self.user
        )

    def check_device(self, state, health):
        self.device.refresh_from_db()
        self.assertEqual(self.device.state, state)
        self.assertEqual(self.device.health, health)

    def test_worker_go_state_online(self):
        # going state online does not change the device state/health
        for state, _ in Device.STATE_CHOICES:
            self.device.state = state
            self.device.save()
            self.worker.state = Worker.STATE_OFFLINE
            self.worker.health = Worker.HEALTH_ACTIVE
            self.worker.save()
            self.worker.go_state_online()
            self.worker.save()

            self.assertEqual(self.worker.state, Worker.STATE_ONLINE)
            self.assertEqual(self.worker.health, Worker.HEALTH_ACTIVE)
            self.check_device(state, Device.HEALTH_UNKNOWN)

    def test_worker_go_state_offline(self):
        # going state offline does not change the device state/health
        for state, _ in Device.STATE_CHOICES:
            self.device.state = state
            self.device.save()
            self.worker.state = Worker.STATE_ONLINE
            self.worker.health = Worker.HEALTH_ACTIVE
            self.worker.save()
            self.worker.go_state_offline()
            self.worker.save()

            self.assertEqual(self.worker.state, Worker.STATE_OFFLINE)
            self.assertEqual(self.worker.health, Worker.HEALTH_ACTIVE)
            self.check_device(state, Device.HEALTH_UNKNOWN)

    def test_worker_go_health_active(self):
        # 1/ Normal transitions
        # 1.1/ from MAINTENANCE
        for health, _ in Device.HEALTH_CHOICES:
            self.worker.health = Worker.HEALTH_MAINTENANCE
            self.worker.save()
            self.device.health = health
            self.device.save()
            self.worker.go_health_active(self.user)
            if health == Device.HEALTH_GOOD:
                self.check_device(Device.STATE_IDLE, Device.HEALTH_UNKNOWN)
            else:
                self.check_device(Device.STATE_IDLE, health)

        # 1.2/ from RETIRED
        for health, _ in Device.HEALTH_CHOICES:
            self.worker.health = Worker.HEALTH_RETIRED
            self.worker.save()
            self.device.health = health
            self.device.save()
            self.worker.go_health_active(self.user)
            self.check_device(Device.STATE_IDLE, health)

    def test_worker_go_health_maintenance(self):
        # 1/ Normal transitions
        # 1.1/ from ACTIVE
        for health, _ in Device.HEALTH_CHOICES:
            self.worker.health = Worker.HEALTH_ACTIVE
            self.worker.save()
            self.device.health = health
            self.device.save()
            self.worker.go_health_maintenance(self.user)
            self.check_device(Device.STATE_IDLE, health)

        # 1.2/ from RETIRED
        for health, _ in Device.HEALTH_CHOICES:
            self.worker.health = Worker.HEALTH_RETIRED
            self.worker.save()
            self.device.health = health
            self.device.save()
            self.worker.go_health_maintenance(self.user)
            self.check_device(Device.STATE_IDLE, health)

    def test_worker_go_health_retired(self):
        # 1/ Normal transitions
        # 1.1/ from ACTIVE
        for health, _ in Device.HEALTH_CHOICES:
            self.worker.health = Worker.HEALTH_ACTIVE
            self.worker.save()
            self.device.health = health
            self.device.save()
            self.worker.go_health_retired(self.user)
            if health == Device.HEALTH_BAD:
                self.check_device(Device.STATE_IDLE, Device.HEALTH_BAD)
            else:
                self.check_device(Device.STATE_IDLE, Device.HEALTH_RETIRED)

        # 1.2/ from MAINTENANCE
        for health, _ in Device.HEALTH_CHOICES:
            self.worker.health = Worker.HEALTH_MAINTENANCE
            self.worker.save()
            self.device.health = health
            self.device.save()
            self.worker.go_health_retired(self.user)
            if health == Device.HEALTH_BAD:
                self.check_device(Device.STATE_IDLE, Device.HEALTH_BAD)
            else:
                self.check_device(Device.STATE_IDLE, Device.HEALTH_RETIRED)
