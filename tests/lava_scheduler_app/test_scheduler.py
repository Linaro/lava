#
# Copyright (C) 2017-2019 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import time
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from lava_scheduler_app.models import Device, DeviceType, Tag, TestJob, Worker
from lava_scheduler_app.scheduler import (
    device_in_multinode_pool,
    distinct_on_target_group,
    pool_tags,
    schedule,
    schedule_health_checks,
    worker_summary,
)


def _minimal_valid_job(self) -> str:
    return """
job_name: minimal valid job
visibility: public
timeouts:
  job:
    minutes: 10
  action:
    minutes: 5
actions: []
"""


class TestHealthCheckScheduling(TestCase):
    def setUp(self):
        self.worker01 = Worker.objects.create(
            hostname="worker-01", state=Worker.STATE_ONLINE
        )
        self.worker02 = Worker.objects.create(
            hostname="worker-02", state=Worker.STATE_OFFLINE
        )
        self.worker03 = Worker.objects.create(
            hostname="worker-03", state=Worker.STATE_ONLINE
        )

        self.device_type01 = DeviceType.objects.create(name="panda")

        # ignored by other tests, used to check device.is_valid handling
        self.device_type02 = DeviceType.objects.create(name="unknown")
        self.device_type02.display = False
        self.device_type02.save()

        self.device01 = Device.objects.create(
            hostname="panda01",
            device_type=self.device_type01,
            worker_host=self.worker01,
            health=Device.HEALTH_UNKNOWN,
        )
        # This device should never be considered (his worker is OFFLINE)
        self.device02 = Device.objects.create(
            hostname="panda02",
            device_type=self.device_type01,
            worker_host=self.worker02,
            health=Device.HEALTH_UNKNOWN,
        )
        self.device03 = Device.objects.create(
            hostname="panda03",
            device_type=self.device_type01,
            worker_host=self.worker03,
            health=Device.HEALTH_UNKNOWN,
        )
        # ignored by other tests, used to check device.is_valid handling
        self.device04 = Device.objects.create(
            hostname="unknown-01",
            device_type=self.device_type02,
            worker_host=self.worker01,
            health=Device.HEALTH_RETIRED,
        )

        self.user = User.objects.create(username="user-01")
        self.last_hc03 = TestJob.objects.create(
            health_check=True,
            actual_device=self.device03,
            submitter=self.user,
            start_time=timezone.now(),
            state=TestJob.STATE_FINISHED,
            health=TestJob.HEALTH_COMPLETE,
        )
        self.device03.last_health_report_job = self.last_hc03
        self.device03.save()

    def _check_hc_scheduled(self, device):
        device.refresh_from_db()
        self.assertEqual(device.state, Device.STATE_RESERVED)
        job = device.current_job()
        self.assertIsNotNone(job)
        self.assertEqual(job.state, TestJob.STATE_SCHEDULED)
        self.assertEqual(job.health, TestJob.HEALTH_UNKNOWN)
        self.assertEqual(job.actual_device, device)

    def _check_hc_not_scheduled(self, device):
        device.refresh_from_db()
        self.assertEqual(device.state, Device.STATE_IDLE)
        self.assertIsNone(device.current_job())

    @patch.object(Device, "get_health_check", lambda _: None)
    def test_without_health_checks(self):
        self.assertIsNone(self.device01.get_health_check())
        self.assertIsNone(self.device02.get_health_check())
        self.assertIsNone(self.device03.get_health_check())
        # Schedule without health check
        workers_limit = worker_summary(
            Worker.objects.filter(hostname__in=["worker-01", "worker-03"])
        )
        available_devices = schedule_health_checks(workers_limit)
        self.assertEqual(available_devices, {"panda": ["panda01", "panda03"]})

    @patch.object(Device, "get_health_check", _minimal_valid_job)
    def test_disabled_hc(self):
        self.assertNotEqual(self.device01.get_health_check(), None)
        self.assertNotEqual(self.device02.get_health_check(), None)
        self.assertNotEqual(self.device03.get_health_check(), None)

        self.device_type01.disable_health_check = True
        self.device_type01.save()
        workers_limit = worker_summary(
            Worker.objects.filter(hostname__in=["worker-01", "worker-03"])
        )
        available_devices = schedule_health_checks(workers_limit)
        self.assertEqual(available_devices, {"panda": ["panda01", "panda03"]})

    @patch.object(Device, "get_health_check", _minimal_valid_job)
    def test_no_devicedict(self):
        self.device_type02.disable_health_check = False
        self.device_type02.display = True
        self.device_type02.save()

        self.device04.state = Device.STATE_IDLE
        self.device04.health = Device.HEALTH_UNKNOWN
        self.device04.save()

        workers_limit = worker_summary(
            Worker.objects.filter(hostname__in=["worker-01", "worker-03"])
        )
        schedule_health_checks(workers_limit)

        self.device04.refresh_from_db()
        self.assertFalse(self.device04.is_valid())
        self.assertEqual(self.device04.health, Device.HEALTH_BAD)
        self.assertIsNone(self.device04.current_job())

    @patch.object(Device, "get_health_check", _minimal_valid_job)
    def test_without_previous_hc_device_health_unknown(self):
        self.assertIsNotNone(self.device01.get_health_check())
        self.assertIsNotNone(self.device02.get_health_check())
        self.assertIsNotNone(self.device03.get_health_check())

        workers_limit = worker_summary(
            Worker.objects.filter(hostname__in=["worker-01", "worker-03"])
        )
        available_devices = schedule_health_checks(workers_limit)
        self.assertEqual(available_devices, {"panda": []})
        self._check_hc_scheduled(self.device01)
        self._check_hc_not_scheduled(self.device02)
        self._check_hc_scheduled(self.device03)

    @patch.object(Device, "get_health_check", _minimal_valid_job)
    def test_device_health_good(self):
        self.assertIsNotNone(self.device01.get_health_check())
        self.assertIsNotNone(self.device02.get_health_check())
        self.assertIsNotNone(self.device03.get_health_check())

        self.device01.health = Device.HEALTH_GOOD
        self.device01.save()
        self.device02.health = Device.HEALTH_GOOD
        self.device02.save()
        self.device03.health = Device.HEALTH_GOOD
        self.device03.save()
        workers_limit = worker_summary(
            Worker.objects.filter(hostname__in=["worker-01", "worker-03"])
        )
        available_devices = schedule_health_checks(workers_limit)
        self.assertEqual(available_devices, {"panda": ["panda03"]})
        self._check_hc_scheduled(self.device01)
        self._check_hc_not_scheduled(self.device02)
        self._check_hc_not_scheduled(self.device03)

    @patch.object(Device, "get_health_check", _minimal_valid_job)
    def test_device_health_good_worker_maintenance(self):
        self.assertIsNotNone(self.device01.get_health_check())
        self.assertIsNotNone(self.device02.get_health_check())
        self.assertIsNotNone(self.device03.get_health_check())

        self.worker01.health = Worker.HEALTH_MAINTENANCE
        self.worker01.save()
        self.device01.health = Device.HEALTH_GOOD
        self.device01.save()
        self.device02.health = Device.HEALTH_GOOD
        self.device02.save()
        self.device03.health = Device.HEALTH_GOOD
        self.device03.save()
        workers_limit = worker_summary(
            Worker.objects.filter(hostname__in=["worker-03"])
        )
        available_devices = schedule_health_checks(workers_limit)
        self.assertEqual(available_devices, {"panda": ["panda03"]})
        self._check_hc_not_scheduled(self.device01)
        self._check_hc_not_scheduled(self.device02)
        self._check_hc_not_scheduled(self.device03)

    @patch.object(Device, "get_health_check", _minimal_valid_job)
    def test_device_health_looping(self):
        self.assertIsNotNone(self.device01.get_health_check())
        self.assertIsNotNone(self.device02.get_health_check())
        self.assertIsNotNone(self.device03.get_health_check())

        self.device01.health = Device.HEALTH_LOOPING
        self.device01.save()
        self.device02.health = Device.HEALTH_LOOPING
        self.device02.save()
        self.device03.health = Device.HEALTH_LOOPING
        self.device03.save()
        workers_limit = worker_summary(
            Worker.objects.filter(hostname__in=["worker-01", "worker-03"])
        )
        available_devices = schedule_health_checks(workers_limit)
        self.assertEqual(available_devices, {"panda": []})
        self._check_hc_scheduled(self.device01)
        self._check_hc_not_scheduled(self.device02)
        self._check_hc_scheduled(self.device03)

    @patch.object(Device, "get_health_check", _minimal_valid_job)
    def test_device_health_wrong(self):
        self.assertIsNotNone(self.device01.get_health_check())
        self.assertIsNotNone(self.device02.get_health_check())
        self.assertIsNotNone(self.device03.get_health_check())

        # HEALTH_(BAD|MAINTENANCE|RETIRED)
        for health in [
            Device.HEALTH_BAD,
            Device.HEALTH_MAINTENANCE,
            Device.HEALTH_RETIRED,
        ]:
            self.device01.health = health
            self.device01.save()
            self.device02.health = health
            self.device02.save()
            self.device03.health = health
            self.device03.save()
            workers_limit = worker_summary(
                Worker.objects.filter(hostname__in=["worker-01", "worker-03"])
            )
            available_devices = schedule_health_checks(workers_limit)
            self.assertEqual(available_devices, {"panda": []})
            self._check_hc_not_scheduled(self.device01)
            self._check_hc_not_scheduled(self.device02)
            self._check_hc_not_scheduled(self.device03)

    @patch.object(Device, "get_health_check", _minimal_valid_job)
    def test_health_frequency_hours(self):
        self.device_type01.health_denominator = DeviceType.HEALTH_PER_HOUR
        self.device_type01.health_frequency = 24
        self.device_type01.save()

        self.assertIsNotNone(self.device01.get_health_check())
        self.assertIsNotNone(self.device02.get_health_check())
        self.assertIsNotNone(self.device03.get_health_check())
        # Only device03 is available now
        self.device01.health = Device.HEALTH_BAD
        self.device01.save()
        self.assertTrue(self.device01.is_valid())
        self.device03.health = Device.HEALTH_GOOD
        self.device03.save()
        self.assertTrue(self.device03.is_valid())

        # Create a job that should be scheduled now
        j = TestJob.objects.create(
            requested_device_type=self.device_type01,
            submitter=self.user,
            definition=_minimal_valid_job(None),
        )
        schedule(["worker-01", "worker-03"])
        self.device01.refresh_from_db()
        j.refresh_from_db()
        self.assertEqual(j.state, TestJob.STATE_SCHEDULED)
        self.assertEqual(j.actual_device, self.device03)
        j.go_state_finished(TestJob.HEALTH_COMPLETE)
        j.save()

        # Create a job that should be scheduled after the health check
        j = TestJob.objects.create(
            requested_device_type=self.device_type01,
            submitter=self.user,
            definition=_minimal_valid_job(None),
        )
        self.device03.refresh_from_db()
        self.last_hc03.submit_time = timezone.now() - timedelta(hours=25)
        self.last_hc03.save()

        schedule(["worker-01", "worker-03"])
        self.device03.refresh_from_db()
        j.refresh_from_db()
        self.assertEqual(j.state, TestJob.STATE_SUBMITTED)
        current_hc = self.device03.current_job()
        self.assertTrue(current_hc.health_check)
        self.assertEqual(current_hc.state, TestJob.STATE_SCHEDULED)

    @patch.object(Device, "get_health_check", _minimal_valid_job)
    def test_health_frequency_jobs(self):
        self.device_type01.health_denominator = DeviceType.HEALTH_PER_JOB
        self.device_type01.health_frequency = 2
        self.device_type01.save()
        self.last_hc03.submit_time = timezone.now() - timedelta(hours=2)
        self.last_hc03.save()

        self.assertIsNotNone(self.device01.get_health_check())
        self.assertIsNotNone(self.device02.get_health_check())
        self.assertIsNotNone(self.device03.get_health_check())
        # Only device03 is available now
        self.device01.health = Device.HEALTH_BAD
        self.device01.save()
        self.device03.health = Device.HEALTH_GOOD
        self.device03.save()

        # Create three jobs that should be scheduled with a healthcheck preceding the
        # last one
        for _ in range(0, 3):
            TestJob.objects.create(
                requested_device_type=self.device_type01,
                submitter=self.user,
                definition=_minimal_valid_job(None),
            )

        schedule(["worker-01", "worker-03"])
        self.device03.refresh_from_db()
        jobs = TestJob.objects.filter(state=TestJob.STATE_SCHEDULED)
        self.assertEqual(jobs.count(), 1)
        j = jobs[0]
        self.assertEqual(j.actual_device, self.device03)
        j.go_state_finished(TestJob.HEALTH_COMPLETE)
        j.start_time = timezone.now() - timedelta(hours=1)
        j.save()

        schedule(["worker-01", "worker-03"])
        self.device03.refresh_from_db()
        jobs = TestJob.objects.filter(state=TestJob.STATE_SCHEDULED)
        self.assertEqual(jobs.count(), 1)
        j = jobs[0]
        self.assertEqual(j.actual_device, self.device03)
        j.go_state_finished(TestJob.HEALTH_COMPLETE)
        j.start_time = timezone.now() - timedelta(hours=1)
        j.save()

        schedule(["worker-01", "worker-03"])
        self.device03.refresh_from_db()
        jobs = TestJob.objects.filter(state=TestJob.STATE_SUBMITTED)
        self.assertEqual(jobs.count(), 1)
        current_hc = self.device03.current_job()
        self.assertTrue(current_hc.health_check)
        self.assertEqual(current_hc.state, TestJob.STATE_SCHEDULED)


@patch.object(Device, "get_health_check", _minimal_valid_job)
class TestTagsScheduling(TestCase):
    def setUp(self) -> None:
        self.worker01 = Worker.objects.create(
            hostname="worker-01", state=Worker.STATE_ONLINE
        )
        self.worker03 = Worker.objects.create(
            hostname="worker-03", state=Worker.STATE_ONLINE
        )
        self.user = User.objects.create(username="user-01")
        self.device_type01 = DeviceType.objects.create(
            name="qemu", disable_health_check=True
        )
        self.device01 = Device.objects.create(
            hostname="qemu01",
            device_type=self.device_type01,
            worker_host=self.worker01,
            health=Device.HEALTH_GOOD,
        )
        self.device03 = Device.objects.create(
            hostname="qemu03",
            device_type=self.device_type01,
            worker_host=self.worker01,
            health=Device.HEALTH_GOOD,
        )
        self.device04 = Device.objects.create(
            hostname="qemu04",
            device_type=self.device_type01,
            worker_host=self.worker03,
            health=Device.HEALTH_GOOD,
        )

    def create_job_with_tags(self, *tags: Tag) -> TestJob:
        job = TestJob.objects.create(
            requested_device_type=self.device_type01,
            submitter=self.user,
            definition=_minimal_valid_job(None),
        )
        job.tags.add(*tags)
        return job

    def test_tags_none(self) -> None:
        test_tag = Tag.objects.create(name="test-01")

        job = self.create_job_with_tags(test_tag)

        schedule(["worker-01"])
        job.refresh_from_db()

        self.assertIsNone(job.actual_device_id)

    def test_specific_device_schedules_only_on_requested_device(self) -> None:
        job = TestJob.objects.create(
            requested_device_type=self.device_type01,
            requested_device=self.device03,
            submitter=self.user,
            definition=_minimal_valid_job(None),
        )

        schedule(["worker-01"])
        job.refresh_from_db()

        self.assertEqual(job.actual_device_id, self.device03.pk)

    def test_specific_device_does_not_fall_back_to_other_device(self) -> None:
        self.device03.state = Device.STATE_RUNNING
        self.device03.save(update_fields=["state"])
        job = TestJob.objects.create(
            requested_device_type=self.device_type01,
            requested_device=self.device03,
            submitter=self.user,
            definition=_minimal_valid_job(None),
        )

        schedule(["worker-01"])
        job.refresh_from_db()

        self.assertIsNone(job.actual_device_id)

    def test_specific_worker_schedules_only_on_requested_worker(self) -> None:
        job = TestJob.objects.create(
            requested_device_type=self.device_type01,
            requested_worker=self.worker03,
            submitter=self.user,
            definition=_minimal_valid_job(None),
        )

        schedule(["worker-01", "worker-03"])
        job.refresh_from_db()

        self.assertEqual(job.actual_device_id, self.device04.pk)

    def test_specific_worker_does_not_fall_back_to_other_worker(self) -> None:
        self.device04.state = Device.STATE_RUNNING
        self.device04.save(update_fields=["state"])
        job = TestJob.objects.create(
            requested_device_type=self.device_type01,
            requested_worker=self.worker03,
            submitter=self.user,
            definition=_minimal_valid_job(None),
        )

        schedule(["worker-01", "worker-03"])
        job.refresh_from_db()

        self.assertIsNone(job.actual_device_id)

    def test_tags_equal(self) -> None:
        test_tag = Tag.objects.create(name="test-01")
        self.device03.tags.add(test_tag)

        job = self.create_job_with_tags(test_tag)

        schedule(["worker-01"])
        job.refresh_from_db()

        self.assertEqual(job.actual_device_id, self.device03.pk)

    def test_tags_equal_multiple(self) -> None:
        test_tag_1 = Tag.objects.create(name="test-01")
        test_tag_2 = Tag.objects.create(name="test-02")
        self.device03.tags.add(test_tag_1)
        self.device01.tags.add(test_tag_1)
        self.device01.tags.add(test_tag_2)

        job = self.create_job_with_tags(test_tag_1, test_tag_2)

        schedule(["worker-01"])
        job.refresh_from_db()

        self.assertEqual(job.actual_device_id, self.device01.pk)

    def test_tags_subset(self) -> None:
        test_tag_1 = Tag.objects.create(name="test-01")
        test_tag_2 = Tag.objects.create(name="test-02")
        self.device03.tags.add(test_tag_1)
        self.device03.tags.add(test_tag_2)
        self.device01.tags.add(test_tag_1)

        job = self.create_job_with_tags(test_tag_2)

        schedule(["worker-01"])
        job.refresh_from_db()

        self.assertEqual(job.actual_device_id, self.device03.pk)

    def test_tags_superset(self) -> None:
        test_tag_1 = Tag.objects.create(name="test-01")
        test_tag_2 = Tag.objects.create(name="test-02")
        self.device03.tags.add(test_tag_2)
        self.device01.tags.add(test_tag_1)

        job = self.create_job_with_tags(test_tag_1, test_tag_2)

        schedule(["worker-01"])
        job.refresh_from_db()

        self.assertIsNone(job.actual_device_id)


class TestVisibility(TestCase):
    def setUp(self):
        self.worker01 = Worker.objects.create(
            hostname="worker-01", state=Worker.STATE_ONLINE
        )
        self.worker02 = Worker.objects.create(
            hostname="worker-02", state=Worker.STATE_OFFLINE
        )
        self.worker03 = Worker.objects.create(
            hostname="worker-03", state=Worker.STATE_ONLINE
        )

        self.device_type01 = DeviceType.objects.create(name="panda")

        self.device01 = Device.objects.create(
            hostname="panda01",
            device_type=self.device_type01,
            worker_host=self.worker01,
            health=Device.HEALTH_UNKNOWN,
        )
        # This device should never be considered (his worker is OFFLINE)
        self.device02 = Device.objects.create(
            hostname="panda02",
            device_type=self.device_type01,
            worker_host=self.worker02,
            health=Device.HEALTH_UNKNOWN,
        )
        self.device03 = Device.objects.create(
            hostname="panda03",
            device_type=self.device_type01,
            worker_host=self.worker03,
            health=Device.HEALTH_UNKNOWN,
        )
        self.user = User.objects.create(username="user-01")
        self.device03.save()

    def _check_hc_scheduled(self, device):
        device.refresh_from_db()
        self.assertEqual(device.state, Device.STATE_RESERVED)
        job = device.current_job()
        self.assertIsNotNone(job)
        self.assertEqual(job.state, TestJob.STATE_SCHEDULED)
        self.assertEqual(job.health, TestJob.HEALTH_UNKNOWN)
        self.assertEqual(job.actual_device, device)

    def _check_hc_not_scheduled(self, device):
        device.refresh_from_db()
        self.assertEqual(device.state, Device.STATE_IDLE)
        self.assertEqual(device.current_job(), None)

    def _check_initial_state(self):
        self.assertIsNotNone(self.device01.get_health_check())
        self.assertIsNotNone(self.device02.get_health_check())
        self.assertIsNotNone(self.device03.get_health_check())
        self.assertEqual(self.device01.health, Device.HEALTH_UNKNOWN)
        self.assertEqual(self.device02.health, Device.HEALTH_UNKNOWN)
        self.assertEqual(self.device03.health, Device.HEALTH_UNKNOWN)

    @patch.object(Device, "get_health_check", _minimal_valid_job)
    def test_health_visibility(self):
        self._check_initial_state()

        self.device_type01.disable_health_check = False
        self.device_type01.save()

        workers_limit = worker_summary(
            Worker.objects.filter(hostname__in=["worker-01", "worker-03"])
        )
        schedule_health_checks(workers_limit)

        self._check_hc_scheduled(self.device01)
        self._check_hc_not_scheduled(self.device02)
        self._check_hc_scheduled(self.device03)

    @patch.object(Device, "get_health_check", _minimal_valid_job)
    def test_health_visibility_some_restricted(self):
        self._check_initial_state()

        self.device_type01.disable_health_check = False
        self.device_type01.save()

        workers_limit = worker_summary(
            Worker.objects.filter(hostname__in=["worker-01", "worker-03"])
        )
        schedule_health_checks(workers_limit)

        self._check_hc_scheduled(self.device01)
        self._check_hc_not_scheduled(self.device02)
        # device03 is restricted in setUp
        self._check_hc_scheduled(self.device03)

    @patch.object(Device, "get_health_check", _minimal_valid_job)
    def test_health_visibility_all_restricted(self):
        self._check_initial_state()

        self.device_type01.disable_health_check = False
        self.device_type01.save()

        workers_limit = worker_summary(
            Worker.objects.filter(hostname__in=["worker-01", "worker-03"])
        )
        schedule_health_checks(workers_limit)

        self._check_hc_scheduled(self.device01)
        self._check_hc_not_scheduled(self.device02)
        self._check_hc_scheduled(self.device03)


class TestPriorities(TestCase):
    def setUp(self):
        self.worker01 = Worker.objects.create(
            hostname="worker-01", state=Worker.STATE_ONLINE
        )
        self.device_type01 = DeviceType.objects.create(name="panda")
        self.device01 = Device.objects.create(
            hostname="panda01",
            device_type=self.device_type01,
            worker_host=self.worker01,
            health=Device.HEALTH_GOOD,
        )
        self.user = User.objects.create(username="user-01")

    def _check_job(
        self, job, priorities, state=TestJob.STATE_SUBMITTED, actual_device=None
    ):
        job.refresh_from_db()
        self.assertIn(job.priority, priorities)
        self.assertEqual(job.state, state)
        self.assertEqual(job.actual_device, actual_device)

    def _check_scheduling(self, device, current_priority, remaining_priorities):
        schedule(["worker-01"])
        device.refresh_from_db()
        self.assertEqual(device.state, Device.STATE_RESERVED)

        scheduled = TestJob.objects.filter(state=TestJob.STATE_SCHEDULED)
        self.assertEqual(scheduled.count(), 1)

        current = TestJob.objects.get(id=scheduled[0].id)
        self._check_job(current, (current_priority,), TestJob.STATE_SCHEDULED, device)

        submitted = TestJob.objects.filter(state=TestJob.STATE_SUBMITTED)
        for j in submitted:
            self._check_job(j, remaining_priorities)

        current.go_state_finished(TestJob.HEALTH_COMPLETE)
        current.save()
        self._check_job(current, (current_priority,), TestJob.STATE_FINISHED, device)

    def test_low_medium_high_without_hc(self):
        for p in [
            TestJob.LOW,
            TestJob.MEDIUM,
            TestJob.HIGH,
            TestJob.MEDIUM,
            TestJob.LOW,
            40,
        ]:
            TestJob.objects.create(
                requested_device_type=self.device_type01,
                submitter=self.user,
                definition=_minimal_valid_job(None),
                priority=p,
            )

        # High priority job
        self._check_scheduling(
            self.device01, TestJob.HIGH, (TestJob.MEDIUM, TestJob.LOW, 40)
        )

        # Medium priority jobs
        self._check_scheduling(
            self.device01, TestJob.MEDIUM, (TestJob.MEDIUM, TestJob.LOW, 40)
        )
        self._check_scheduling(self.device01, TestJob.MEDIUM, (TestJob.LOW, 40))

        # Custom priority job
        self._check_scheduling(self.device01, 40, (TestJob.LOW,))

        # Low priority jobs
        self._check_scheduling(self.device01, TestJob.LOW, (TestJob.LOW,))
        self._check_scheduling(self.device01, TestJob.LOW, ())

    @patch.object(Device, "get_health_check", _minimal_valid_job)
    def test_low_medium_high_with_hc(self):
        # Enable health checks
        self.device_type01.health_denominator = DeviceType.HEALTH_PER_HOUR
        self.device_type01.health_frequency = 24
        self.device_type01.save()

        self.assertIsNotNone(self.device01.get_health_check())

        jobs = []
        for p in [
            TestJob.LOW,
            TestJob.MEDIUM,
            TestJob.HIGH,
            TestJob.MEDIUM,
            TestJob.LOW,
        ]:
            j = TestJob.objects.create(
                requested_device_type=self.device_type01,
                submitter=self.user,
                definition=_minimal_valid_job(None),
                priority=p,
            )
            jobs.append(j)

        # Check that an health check will be scheduled before any jobs
        schedule(["worker-01"])
        self.device01.refresh_from_db()
        self.assertEqual(self.device01.state, Device.STATE_RESERVED)
        submitted = TestJob.objects.filter(state=TestJob.STATE_SUBMITTED)
        self.assertEqual(submitted.count(), len(jobs))

        current_hc = self.device01.current_job()
        self.assertEqual(current_hc.state, TestJob.STATE_SCHEDULED)
        current_hc.go_state_finished(TestJob.HEALTH_COMPLETE)
        current_hc.save()

        # Check that the next job is the highest priority
        schedule(["worker-01"])
        self.device01.refresh_from_db()
        self.assertEqual(self.device01.state, Device.STATE_RESERVED)
        scheduled = TestJob.objects.filter(state=TestJob.STATE_SCHEDULED)
        self.assertEqual(scheduled.count(), 1)
        self._check_job(
            scheduled[0], (TestJob.HIGH,), TestJob.STATE_SCHEDULED, self.device01
        )


# test joblimit with HealthChecks with a joblimit of 1
class TestJobLimitHc1(TestCase):
    def setUp(self):
        self.worker01 = Worker.objects.create(
            hostname="worker-01", state=Worker.STATE_ONLINE, job_limit=1
        )
        self.device_type01 = DeviceType.objects.create(name="qemu")
        self.devices = []
        self.user = User.objects.create(username="user-01")

        self.device01 = Device.objects.create(
            hostname="qemu01",
            device_type=self.device_type01,
            worker_host=self.worker01,
            health=Device.HEALTH_GOOD,
        )
        self.device02 = Device.objects.create(
            hostname="qemu02",
            device_type=self.device_type01,
            worker_host=self.worker01,
            health=Device.HEALTH_GOOD,
        )
        self.device03 = Device.objects.create(
            hostname="qemu03",
            device_type=self.device_type01,
            worker_host=self.worker01,
            health=Device.HEALTH_GOOD,
        )
        self.device04 = Device.objects.create(
            hostname="qemu04",
            device_type=self.device_type01,
            worker_host=self.worker01,
            health=Device.HEALTH_GOOD,
        )
        self.devices.append(self.device01)
        self.devices.append(self.device02)
        self.devices.append(self.device03)
        self.devices.append(self.device04)
        self.device01.save()
        self.device02.save()
        self.device03.save()
        self.device04.save()

    @patch.object(Device, "get_health_check", _minimal_valid_job)
    def test_job_limit_hc(self):
        workers_limit = worker_summary(
            Worker.objects.filter(hostname__in=["worker-01"])
        )
        schedule_health_checks(workers_limit)

        devs = 0
        # check that only one device got healthcheck
        for device in self.devices:
            device.refresh_from_db()
            if device.state != Device.STATE_IDLE:
                devs = devs + 1
        self.assertEqual(devs, 1)
        for job in TestJob.objects.filter(
            state__in=[TestJob.STATE_SCHEDULING, TestJob.STATE_SCHEDULED]
        ):
            job.go_state_finished(TestJob.HEALTH_COMPLETE)
            job.actual_device.health = Device.HEALTH_GOOD
            job.actual_device.state = Device.STATE_IDLE
            job.actual_device.save()
            job.save()

        # STEP 2
        workers_limit = worker_summary(
            Worker.objects.filter(hostname__in=["worker-01"])
        )
        schedule_health_checks(workers_limit)

        devs = 0
        for device in self.devices:
            device.refresh_from_db()
            if device.state != Device.STATE_IDLE:
                devs = devs + 1
        self.assertEqual(devs, 1)


# test joblimit with HealthChecks with a joblimit of 2
class TestJobLimitHc2(TestCase):
    def setUp(self):
        self.worker01 = Worker.objects.create(
            hostname="worker-01", state=Worker.STATE_ONLINE, job_limit=2
        )
        self.device_type01 = DeviceType.objects.create(name="qemu")
        self.devices = []
        self.user = User.objects.create(username="user-01")

        self.device01 = Device.objects.create(
            hostname="qemu01",
            device_type=self.device_type01,
            worker_host=self.worker01,
            health=Device.HEALTH_GOOD,
        )
        self.device02 = Device.objects.create(
            hostname="qemu02",
            device_type=self.device_type01,
            worker_host=self.worker01,
            health=Device.HEALTH_GOOD,
        )
        self.device03 = Device.objects.create(
            hostname="qemu03",
            device_type=self.device_type01,
            worker_host=self.worker01,
            health=Device.HEALTH_GOOD,
        )
        self.device04 = Device.objects.create(
            hostname="qemu04",
            device_type=self.device_type01,
            worker_host=self.worker01,
            health=Device.HEALTH_GOOD,
        )
        self.devices.append(self.device01)
        self.devices.append(self.device02)
        self.devices.append(self.device03)
        self.devices.append(self.device04)

    @patch.object(Device, "get_health_check", _minimal_valid_job)
    def test_job_limit_hc2(self):
        workers_limit = worker_summary(
            Worker.objects.filter(hostname__in=["worker-01"])
        )
        schedule_health_checks(workers_limit)

        devs = 0
        # check that only 2 devices got healthcheck
        for device in self.devices:
            device.refresh_from_db()
            if device.state != Device.STATE_IDLE:
                devs = devs + 1
        self.assertEqual(devs, 2)

        for job in TestJob.objects.filter(
            state__in=[TestJob.STATE_SCHEDULING, TestJob.STATE_SCHEDULED]
        ):
            job.go_state_finished(TestJob.HEALTH_COMPLETE)
            job.actual_device.health = Device.HEALTH_GOOD
            job.actual_device.state = Device.STATE_IDLE
            job.actual_device.save()
            job.save()

        # STEP 2
        workers_limit = worker_summary(
            Worker.objects.filter(hostname__in=["worker-01"])
        )
        schedule_health_checks(workers_limit)

        devs = 0
        # check that only 4 devices got healthcheck
        for device in self.devices:
            device.refresh_from_db()
            if device.state != Device.STATE_IDLE:
                devs = devs + 1
        self.assertEqual(devs, 2)


# test both healthcheck and normal testjobs with joblimit
class TestJobLimit(TestCase):
    def setUp(self):
        self.job_limit = 2

        self.worker01 = Worker.objects.create(
            hostname="worker-01", state=Worker.STATE_ONLINE, job_limit=self.job_limit
        )
        self.user = User.objects.create(username="user-01")
        self.device_type01 = DeviceType.objects.create(
            name="qemu", disable_health_check=True
        )
        self.devices = []
        for i in range(0, 6):
            dev = Device.objects.create(
                hostname=f"qemu0{i}",
                device_type=self.device_type01,
                worker_host=self.worker01,
                health=Device.HEALTH_GOOD,
            )
            self.devices.append(dev)

    def test_job_limit(self):
        for _ in range(0, 4):
            TestJob.objects.create(
                requested_device_type=self.device_type01,
                submitter=self.user,
                definition=_minimal_valid_job(None),
            )
        self.assertEqual(TestJob.objects.all().count(), 4)
        # Limit the number of jobs that can run
        schedule(["worker-01"])
        self.assertEqual(
            TestJob.objects.filter(state=TestJob.STATE_SCHEDULED).count(), 2
        )
        self.assertEqual(
            TestJob.objects.filter(state=TestJob.STATE_SUBMITTED).count(), 2
        )

    def test_job_limit_unlimited(self):
        for _ in range(0, 4):
            TestJob.objects.create(
                requested_device_type=self.device_type01,
                submitter=self.user,
                definition=_minimal_valid_job(None),
            )
        self.assertEqual(TestJob.objects.all().count(), 4)
        # Limit the number of jobs that can run
        self.worker01.job_limit = 0
        self.worker01.save()
        schedule(["worker-01"])
        self.assertEqual(
            TestJob.objects.filter(state=TestJob.STATE_SCHEDULED).count(), 4
        )
        self.assertEqual(
            TestJob.objects.filter(state=TestJob.STATE_SUBMITTED).count(), 0
        )


# test both healthcheck and normal testjobs with joblimit
class TestJobQueueTimeout(TestCase):
    def setUp(self):
        self.worker01 = Worker.objects.create(
            hostname="worker-01", state=Worker.STATE_ONLINE
        )
        self.user = User.objects.create(username="user-01")
        self.device_type01 = DeviceType.objects.create(
            name="qemu", disable_health_check=True
        )
        self.devices = []
        dev = Device.objects.create(
            hostname="qemu0",
            device_type=self.device_type01,
            worker_host=self.worker01,
            health=Device.HEALTH_BAD,
        )
        self.devices.append(dev)

    def test_job_limit(self):
        TestJob.objects.create(
            requested_device_type=self.device_type01,
            submitter=self.user,
            queue_timeout=int(timedelta(seconds=1).total_seconds()),
        )
        self.assertEqual(TestJob.objects.all().count(), 1)
        # Limit the number of jobs that can run
        schedule([])
        self.assertEqual(
            TestJob.objects.filter(state=TestJob.STATE_SUBMITTED).count(), 1
        )
        self.assertEqual(
            TestJob.objects.filter(state=TestJob.STATE_CANCELING).count(), 0
        )
        time.sleep(3)
        schedule([])
        self.assertEqual(
            TestJob.objects.filter(state=TestJob.STATE_SUBMITTED).count(), 0
        )
        canceling = TestJob.objects.filter(state=TestJob.STATE_CANCELING).count()
        canceled = TestJob.objects.filter(health=TestJob.HEALTH_CANCELED).count()
        if canceling == 0:
            self.assertEqual(canceled, 1)
        else:
            self.assertEqual(canceling, 1)
            self.assertEqual(canceled, 0)


def _job(job_id, target_group):
    return SimpleNamespace(id=job_id, target_group=target_group)


class TestDistinctOnTargetGroup:
    def test_keeps_first_job_of_each_target_group(self):
        jobs = [
            _job(1, "group-a"),
            _job(2, "group-a"),
            _job(3, "group-b"),
            _job(4, "group-b"),
            _job(5, "group-c"),
        ]
        assert [job.id for job in distinct_on_target_group(jobs)] == [1, 3, 5]

    def test_collapses_jobs_without_a_target_group(self):
        jobs = [
            _job(1, None),
            _job(2, None),
            _job(3, "group-a"),
        ]
        assert [job.id for job in distinct_on_target_group(jobs)] == [1, 3]

    def test_no_jobs(self):
        assert not list(distinct_on_target_group([]))


def _multinode_job_definition(role, target_group, sub_id=0, group_size=2):
    return f"""
job_name: multinode job
visibility: public
timeouts:
  job:
    minutes: 10
protocols:
  lava-multinode:
    role: {role}
    target_group: {target_group}
    sub_id: {sub_id}
    group_size: {group_size}
actions: []
"""


class TestMultinodePoolPattern(TestCase):
    """
    A multinode job with a pool_pattern can only use devices sharing the same
    tag matching that pattern.
    """

    def setUp(self):
        self.worker01 = Worker.objects.create(
            hostname="worker-01", state=Worker.STATE_ONLINE
        )
        self.user = User.objects.create(username="user-01")
        self.device_type01 = DeviceType.objects.create(
            name="qemu", disable_health_check=True
        )
        self.pool_a = Tag.objects.create(name="pool-a")
        self.pool_b = Tag.objects.create(name="pool-b")

        self.devices = {}
        for hostname, tags in [
            ("qemu01", [self.pool_a]),
            ("qemu02", [self.pool_a]),
            ("qemu03", [self.pool_b]),
            ("qemu04", [self.pool_b]),
        ]:
            device = Device.objects.create(
                hostname=hostname,
                device_type=self.device_type01,
                worker_host=self.worker01,
                health=Device.HEALTH_GOOD,
            )
            device.tags.set(tags)
            self.devices[hostname] = device

    def _keep_one_device_per_pool(self):
        # Only qemu01 (pool-a) and qemu03 (pool-b) remain usable
        for hostname in ["qemu02", "qemu04"]:
            self.devices[hostname].health = Device.HEALTH_RETIRED
            self.devices[hostname].save()

    def _make_group(self, pool_pattern="pool-*", roles=("server", "client")):
        target_group = "target-group-01"
        jobs = []
        for index, role in enumerate(roles):
            job = TestJob.objects.create(
                requested_device_type=self.device_type01,
                submitter=self.user,
                definition=_multinode_job_definition(
                    role, target_group, sub_id=index, group_size=len(roles)
                ),
                target_group=target_group,
                pool_pattern=pool_pattern,
            )
            job.sub_id = "%d.%d" % (jobs[0].id if jobs else job.id, index)
            job.save(update_fields=["sub_id"])
            jobs.append(job)
        return jobs

    def _pools_in_use(self, jobs):
        pools = []
        for job in jobs:
            job.refresh_from_db()
            if job.actual_device is None:
                continue
            pools.extend(tag.name for tag in job.actual_device.tags.all())
        return pools

    def test_all_devices_are_from_the_same_pool(self):
        jobs = self._make_group()
        schedule(["worker-01"])

        pools = []
        for job in jobs:
            job.refresh_from_db()
            self.assertEqual(job.state, TestJob.STATE_SCHEDULED)
            self.assertIsNotNone(job.actual_device)
            pools.append({tag.name for tag in job.actual_device.tags.all()})

        # Both sub jobs are in the very same (single) pool
        self.assertEqual(pools[0], pools[1])
        self.assertIn(pools[0], [{"pool-a"}, {"pool-b"}])
        (pool,) = pools[0]

        # The two devices of that pool are reserved, one per sub job, while
        # the devices of the other pool are left untouched.
        in_pool = {"pool-a": ["qemu01", "qemu02"], "pool-b": ["qemu03", "qemu04"]}[pool]
        self.assertEqual(sorted(job.actual_device.hostname for job in jobs), in_pool)

        for hostname, device in self.devices.items():
            device.refresh_from_db()
            self.assertEqual(device.health, Device.HEALTH_GOOD)
            if hostname in in_pool:
                self.assertEqual(device.state, Device.STATE_RESERVED)
                self.assertIn(device.current_job(), jobs)
            else:
                self.assertEqual(device.state, Device.STATE_IDLE)
                self.assertIsNone(device.current_job())

    def test_group_is_not_split_between_two_pools(self):
        # One single device per pool: only the first sub job can be scheduled,
        # the second one has to wait for a device of the very same pool.
        self._keep_one_device_per_pool()
        jobs = self._make_group()
        schedule(["worker-01"])

        states = []
        for job in jobs:
            job.refresh_from_db()
            states.append(job.state)
        self.assertEqual(
            sorted(states), [TestJob.STATE_SUBMITTED, TestJob.STATE_SCHEDULING]
        )
        self.assertEqual(len(self._pools_in_use(jobs)), 1)

    def test_without_pool_pattern_the_group_can_be_split(self):
        # Remove the pool_pattern and force one device per tag
        # Scheduler should assign each job to a different tag
        self._keep_one_device_per_pool()
        jobs = self._make_group(pool_pattern=None)
        schedule(["worker-01"])

        for job in jobs:
            job.refresh_from_db()
            self.assertEqual(job.state, TestJob.STATE_SCHEDULED)

        self.assertEqual(sorted(self._pools_in_use(jobs)), ["pool-a", "pool-b"])

    def test_devices_without_a_matching_tag_are_skipped(self):
        # Try to schedule a multinode job with a poll_pattern that can't match
        jobs = self._make_group(pool_pattern="pool-c*")
        schedule(["worker-01"])

        for job in jobs:
            job.refresh_from_db()
            self.assertEqual(job.state, TestJob.STATE_SUBMITTED)
            self.assertIsNone(job.actual_device)

    def test_pattern_should_match_the_full_tag_name(self):
        # "pool-" is a prefix of "pool-a" but does not match the full tag name
        jobs = self._make_group(pool_pattern="pool-")
        schedule(["worker-01"])

        for job in jobs:
            job.refresh_from_db()
            self.assertEqual(job.state, TestJob.STATE_SUBMITTED)

    def test_larger_group_than_the_pool(self):
        # 3 sub jobs but only 2 devices per pool
        jobs = self._make_group(roles=("server", "client", "monitor"))
        schedule(["worker-01"])

        states = sorted(
            TestJob.objects.filter(pk__in=[j.pk for j in jobs]).values_list(
                "state", flat=True
            )
        )
        self.assertEqual(
            states,
            [
                TestJob.STATE_SUBMITTED,
                TestJob.STATE_SCHEDULING,
                TestJob.STATE_SCHEDULING,
            ],
        )
        pools = self._pools_in_use(jobs)
        self.assertEqual(len(pools), 2)
        self.assertEqual(len(set(pools)), 1)

    def test_pool_pattern_is_ignored_for_single_node_jobs(self):
        device = Device.objects.create(
            hostname="qemu05",
            device_type=self.device_type01,
            worker_host=self.worker01,
            health=Device.HEALTH_GOOD,
        )
        job = TestJob.objects.create(
            requested_device_type=self.device_type01,
            submitter=self.user,
            definition=_minimal_valid_job(None),
            pool_pattern="pool-*",
        )
        self.assertFalse(job.is_multinode)

        schedule(["worker-01"])
        job.refresh_from_db()
        self.assertEqual(job.state, TestJob.STATE_SCHEDULED)
        # Any device can be used, including one without any tag
        self.assertIn(
            job.actual_device.hostname,
            [device.hostname] + list(self.devices.keys()),
        )

    def test_pool_and_job_tags_are_both_enforced(self):
        # Each pool has one device with the "fastboot" tag
        fastboot = Tag.objects.create(name="fastboot")
        self.devices["qemu01"].tags.add(fastboot)
        self.devices["qemu03"].tags.add(fastboot)

        jobs = self._make_group()
        jobs[0].tags.add(fastboot)
        schedule(["worker-01"])

        for job in jobs:
            job.refresh_from_db()
            self.assertEqual(job.state, TestJob.STATE_SCHEDULED)

        # The first sub job requires "fastboot", the group stays in one pool
        self.assertIn(jobs[0].actual_device.hostname, ["qemu01", "qemu03"])
        pools = [p for p in self._pools_in_use(jobs) if p != "fastboot"]
        self.assertEqual(len(pools), 2)
        self.assertEqual(len(set(pools)), 1)


class TestDeviceInJobPool(TestCase):
    def setUp(self):
        self.worker01 = Worker.objects.create(
            hostname="worker-01", state=Worker.STATE_ONLINE
        )
        self.user = User.objects.create(username="user-01")
        self.device_type01 = DeviceType.objects.create(name="qemu")
        self.pool_a = Tag.objects.create(name="pool-a")
        self.pool_b = Tag.objects.create(name="pool-b")

        self.device01 = Device.objects.create(
            hostname="qemu01",
            device_type=self.device_type01,
            worker_host=self.worker01,
            health=Device.HEALTH_GOOD,
        )
        self.device01.tags.set([self.pool_a])
        self.device02 = Device.objects.create(
            hostname="qemu02",
            device_type=self.device_type01,
            worker_host=self.worker01,
            health=Device.HEALTH_GOOD,
        )
        self.device02.tags.set([self.pool_b])
        self.device03 = Device.objects.create(
            hostname="qemu03",
            device_type=self.device_type01,
            worker_host=self.worker01,
            health=Device.HEALTH_GOOD,
        )
        self.device03.tags.set([self.pool_a, self.pool_b])

        self.job01 = TestJob.objects.create(
            requested_device_type=self.device_type01,
            submitter=self.user,
            definition=_multinode_job_definition("server", "target-group-01"),
            target_group="target-group-01",
            pool_pattern="pool-*",
        )
        self.job02 = TestJob.objects.create(
            requested_device_type=self.device_type01,
            submitter=self.user,
            definition=_multinode_job_definition("client", "target-group-01", sub_id=1),
            target_group="target-group-01",
            pool_pattern="pool-*",
        )

    def test_pool_tags(self):
        self.assertEqual(pool_tags("pool-*", self.device01), {"pool-a"})
        self.assertEqual(pool_tags("pool-*", self.device03), {"pool-a", "pool-b"})
        self.assertEqual(pool_tags("pool-?", self.device03), {"pool-a", "pool-b"})
        self.assertEqual(pool_tags("pool-[b]", self.device03), {"pool-b"})
        self.assertEqual(pool_tags("nothing", self.device01), set())

    def test_no_device_reserved_yet(self):
        self.assertTrue(device_in_multinode_pool(self.job02, self.device01))
        self.assertTrue(device_in_multinode_pool(self.job02, self.device02))

    def test_same_pool_as_the_reserved_device(self):
        self.job01.actual_device = self.device01
        self.job01.save(update_fields=["actual_device"])
        self.assertTrue(device_in_multinode_pool(self.job02, self.device01))
        self.assertFalse(device_in_multinode_pool(self.job02, self.device02))
        # device03 is in both pools
        self.assertTrue(device_in_multinode_pool(self.job02, self.device03))

    def test_pool_is_narrowed_down_by_each_reservation(self):
        # device03 belongs to both pools, the group is not tied to one pool yet
        self.job01.actual_device = self.device03
        self.job01.save(update_fields=["actual_device"])
        self.assertTrue(device_in_multinode_pool(self.job02, self.device01))
        self.assertTrue(device_in_multinode_pool(self.job02, self.device02))

    def test_device_without_any_pool_tag(self):
        device = Device.objects.create(
            hostname="qemu04",
            device_type=self.device_type01,
            worker_host=self.worker01,
            health=Device.HEALTH_GOOD,
        )
        self.assertFalse(device_in_multinode_pool(self.job02, device))
