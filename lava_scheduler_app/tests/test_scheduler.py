# -*- coding: utf-8 -*-
#
# Copyright (C) 2017 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
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
# along with this program; if not, see <http://www.gnu.org/licenses>.

from __future__ import unicode_literals

from datetime import timedelta
import yaml

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from lava_dispatcher.test.utils import DummyLogger
from lava_scheduler_app.models import (
    Device,
    DeviceType,
    TestJob,
    Worker,
)
from lava_scheduler_app.scheduler import (
    schedule,
    schedule_health_checks
)


def _minimal_valid_job(self):
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
        self.worker01 = Worker.objects.create(hostname="worker-01", state=Worker.STATE_ONLINE)
        self.worker02 = Worker.objects.create(hostname="worker-02", state=Worker.STATE_OFFLINE)
        self.worker03 = Worker.objects.create(hostname="worker-03", state=Worker.STATE_ONLINE)

        self.device_type01 = DeviceType.objects.create(name="dt-01")

        self.device01 = Device.objects.create(hostname="device-01", device_type=self.device_type01,
                                              worker_host=self.worker01, is_public=True)
        # This device should never be considered (his worker is OFFLINE)
        self.device02 = Device.objects.create(hostname="device-02", device_type=self.device_type01,
                                              worker_host=self.worker02, is_public=True)
        self.device03 = Device.objects.create(hostname="device-03", device_type=self.device_type01,
                                              worker_host=self.worker03, is_public=True)
        self.user = User.objects.create(username="user-01")
        self.last_hc03 = TestJob.objects.create(health_check=True, actual_device=self.device03,
                                                user=self.user, submitter=self.user,
                                                start_time=timezone.now(), is_public=True,
                                                state=TestJob.STATE_FINISHED, health=TestJob.HEALTH_COMPLETE)
        self.device03.last_health_report_job = self.last_hc03
        self.device03.save()

        self.original_health_check = Device.get_health_check

    def tearDown(self):
        Device.get_health_check = self.original_health_check

    def _check_hc_scheduled(self, device):
        device.refresh_from_db()
        self.assertEqual(device.state, Device.STATE_RESERVED)
        job = device.current_job()
        self.assertNotEqual(job, None)
        self.assertEqual(job.state, TestJob.STATE_SCHEDULED)
        self.assertEqual(job.health, TestJob.HEALTH_UNKNOWN)
        self.assertEqual(job.actual_device, device)

    def _check_hc_not_scheduled(self, device):
        device.refresh_from_db()
        self.assertEqual(device.state, Device.STATE_IDLE)
        self.assertEqual(device.current_job(), None)

    def test_without_health_checks(self):
        # Make sure that get_health_check does return None
        Device.get_health_check = lambda cls: None
        self.assertEqual(self.device01.get_health_check(), None)
        self.assertEqual(self.device02.get_health_check(), None)
        self.assertEqual(self.device03.get_health_check(), None)
        # Schedule without health check
        available_devices = schedule_health_checks(DummyLogger())[0]
        self.assertEquals(available_devices,
                          {"dt-01": ["device-01", "device-03"]})

    def test_disabled_hc(self):
        # Make sure that get_health_check does return something
        Device.get_health_check = _minimal_valid_job
        self.assertNotEqual(self.device01.get_health_check(), None)
        self.assertNotEqual(self.device02.get_health_check(), None)
        self.assertNotEqual(self.device03.get_health_check(), None)

        self.device_type01.disable_health_check = True
        self.device_type01.save()
        available_devices = schedule_health_checks(DummyLogger())[0]
        self.assertEquals(available_devices,
                          {"dt-01": ["device-01", "device-03"]})

    def test_without_previous_hc_device_health_unknown(self):
        # Make sure that get_health_check does return something
        Device.get_health_check = _minimal_valid_job
        self.assertNotEqual(self.device01.get_health_check(), None)
        self.assertNotEqual(self.device02.get_health_check(), None)
        self.assertNotEqual(self.device03.get_health_check(), None)

        available_devices = schedule_health_checks(DummyLogger())[0]
        self.assertEquals(available_devices, {"dt-01": []})
        self._check_hc_scheduled(self.device01)
        self._check_hc_not_scheduled(self.device02)
        self._check_hc_scheduled(self.device03)

    def test_device_health_good(self):
        # Make sure that get_health_check does return something
        Device.get_health_check = _minimal_valid_job
        self.assertNotEqual(self.device01.get_health_check(), None)
        self.assertNotEqual(self.device02.get_health_check(), None)
        self.assertNotEqual(self.device03.get_health_check(), None)

        self.device01.health = Device.HEALTH_GOOD
        self.device01.save()
        self.device02.health = Device.HEALTH_GOOD
        self.device02.save()
        self.device03.health = Device.HEALTH_GOOD
        self.device03.save()
        available_devices = schedule_health_checks(DummyLogger())[0]
        self.assertEquals(available_devices, {"dt-01": ["device-03"]})
        self._check_hc_scheduled(self.device01)
        self._check_hc_not_scheduled(self.device02)
        self._check_hc_not_scheduled(self.device03)

    def test_device_health_looping(self):
        # Make sure that get_health_check does return something
        Device.get_health_check = _minimal_valid_job
        self.assertNotEqual(self.device01.get_health_check(), None)
        self.assertNotEqual(self.device02.get_health_check(), None)
        self.assertNotEqual(self.device03.get_health_check(), None)

        self.device01.health = Device.HEALTH_LOOPING
        self.device01.save()
        self.device02.health = Device.HEALTH_LOOPING
        self.device02.save()
        self.device03.health = Device.HEALTH_LOOPING
        self.device03.save()
        available_devices = schedule_health_checks(DummyLogger())[0]
        self.assertEquals(available_devices, {"dt-01": []})
        self._check_hc_scheduled(self.device01)
        self._check_hc_not_scheduled(self.device02)
        self._check_hc_scheduled(self.device03)

    def test_device_health_wrong(self):
        # Make sure that get_health_check does return something
        Device.get_health_check = _minimal_valid_job
        self.assertNotEqual(self.device01.get_health_check(), None)
        self.assertNotEqual(self.device02.get_health_check(), None)
        self.assertNotEqual(self.device03.get_health_check(), None)

        # HEALTH_(BAD|MAINTENANCE|RETIRED)
        for health in [Device.HEALTH_BAD, Device.HEALTH_MAINTENANCE, Device.HEALTH_RETIRED]:
            self.device01.health = health
            self.device01.save()
            self.device02.health = health
            self.device02.save()
            self.device03.health = health
            self.device03.save()
            available_devices = schedule_health_checks(DummyLogger())[0]
            self.assertEquals(available_devices, {"dt-01": []})
            self._check_hc_not_scheduled(self.device01)
            self._check_hc_not_scheduled(self.device02)
            self._check_hc_not_scheduled(self.device03)

    def test_health_frequency_hours(self):
        self.device_type01.health_denominator = DeviceType.HEALTH_PER_HOUR
        self.device_type01.health_frequency = 24
        self.device_type01.save()
        Device.get_health_check = _minimal_valid_job
        self.assertNotEqual(self.device01.get_health_check(), None)
        self.assertNotEqual(self.device02.get_health_check(), None)
        self.assertNotEqual(self.device03.get_health_check(), None)
        # Only device03 is available now
        self.device01.health = Device.HEALTH_BAD
        self.device01.save()
        self.device03.health = Device.HEALTH_GOOD
        self.device03.save()

        # Create a job that should be scheduled now
        j = TestJob.objects.create(requested_device_type=self.device_type01,
                                   user=self.user, submitter=self.user, is_public=True,
                                   definition=_minimal_valid_job(None))
        schedule(DummyLogger())
        self.device01.refresh_from_db()
        j.refresh_from_db()
        self.assertEqual(j.state, TestJob.STATE_SCHEDULED)
        self.assertEqual(j.actual_device, self.device03)
        j.go_state_finished(TestJob.HEALTH_COMPLETE)
        j.save()

        # Create a job that should be scheduled after the health check
        j = TestJob.objects.create(requested_device_type=self.device_type01,
                                   user=self.user, submitter=self.user, is_public=True,
                                   definition=_minimal_valid_job(None))
        self.device03.refresh_from_db()
        self.last_hc03.submit_time = timezone.now() - timedelta(hours=25)
        self.last_hc03.save()

        schedule(DummyLogger())
        self.device03.refresh_from_db()
        j.refresh_from_db()
        self.assertEqual(j.state, TestJob.STATE_SUBMITTED)
        current_hc = self.device03.current_job()
        self.assertTrue(current_hc.health_check)
        self.assertEqual(current_hc.state, TestJob.STATE_SCHEDULED)

    def test_health_frequency_jobs(self):
        self.device_type01.health_denominator = DeviceType.HEALTH_PER_JOB
        self.device_type01.health_frequency = 2
        self.device_type01.save()
        self.last_hc03.submit_time = timezone.now() - timedelta(hours=2)
        self.last_hc03.save()
        Device.get_health_check = _minimal_valid_job
        self.assertNotEqual(self.device01.get_health_check(), None)
        self.assertNotEqual(self.device02.get_health_check(), None)
        self.assertNotEqual(self.device03.get_health_check(), None)
        # Only device03 is available now
        self.device01.health = Device.HEALTH_BAD
        self.device01.save()
        self.device03.health = Device.HEALTH_GOOD
        self.device03.save()

        # Create a job that should be scheduled now
        j01 = TestJob.objects.create(requested_device_type=self.device_type01,
                                     user=self.user, submitter=self.user, is_public=True,
                                     definition=_minimal_valid_job(None))
        j02 = TestJob.objects.create(requested_device_type=self.device_type01,
                                     user=self.user, submitter=self.user, is_public=True,
                                     definition=_minimal_valid_job(None))
        j03 = TestJob.objects.create(requested_device_type=self.device_type01,
                                     user=self.user, submitter=self.user, is_public=True,
                                     definition=_minimal_valid_job(None))

        schedule(DummyLogger())
        self.device03.refresh_from_db()
        j01.refresh_from_db()
        self.assertEqual(j01.state, TestJob.STATE_SCHEDULED)
        self.assertEqual(j01.actual_device, self.device03)
        j01.go_state_finished(TestJob.HEALTH_COMPLETE)
        j01.start_time = timezone.now() - timedelta(hours=1)
        j01.save()

        schedule(DummyLogger())
        self.device03.refresh_from_db()
        j02.refresh_from_db()
        self.assertEqual(j02.state, TestJob.STATE_SCHEDULED)
        self.assertEqual(j02.actual_device, self.device03)
        j02.go_state_finished(TestJob.HEALTH_COMPLETE)
        j02.start_time = timezone.now() - timedelta(hours=1)
        j02.save()

        schedule(DummyLogger())
        self.device03.refresh_from_db()
        j03.refresh_from_db()
        self.assertEqual(j03.state, TestJob.STATE_SUBMITTED)
        current_hc = self.device03.current_job()
        self.assertTrue(current_hc.health_check)
        self.assertEqual(current_hc.state, TestJob.STATE_SCHEDULED)


class TestHealthCheckCanceling(TestCase):

    def setUp(self):
        self.worker01 = Worker.objects.create(hostname="worker-01", state=Worker.STATE_ONLINE)
        self.device_type01 = DeviceType.objects.create(name="dt-01")

        self.device01 = Device.objects.create(hostname="device-01", device_type=self.device_type01,
                                              worker_host=self.worker01, is_public=True)
        self.user = User.objects.create(username="user-01")

        self.original_health_check = Device.get_health_check

    def tearDown(self):
        Device.get_health_check = self.original_health_check

    def test_hc_cancel(self):
        # LAVA-1349 - cancel health check -> BAD
        Device.get_health_check = _minimal_valid_job
        self.assertNotEqual(self.device01.get_health_check(), None)
        self.assertEqual(self.device01.state, Device.STATE_IDLE)
        self.assertEqual(list(TestJob.objects.all()), [])

        schedule(DummyLogger())

        self.device01.refresh_from_db()
        j01 = TestJob.objects.all()[0]
        self.assertEqual(TestJob.objects.all().count(), 1)
        self.assertEqual(j01.state, TestJob.STATE_SCHEDULED)
        self.assertEqual(j01.actual_device, self.device01)
        j01.start_time = timezone.now() - timedelta(hours=1)
        j01.save()

        schedule(DummyLogger())

        self.device01.refresh_from_db()
        self.assertEqual(self.device01.state, Device.STATE_RESERVED)
        self.assertEqual(j01.state, TestJob.STATE_SCHEDULED)
        self.assertEqual(self.device01.health, Device.HEALTH_UNKNOWN)
        self.assertEqual(j01.health, TestJob.HEALTH_UNKNOWN)

        schedule(DummyLogger())

        j01.go_state_canceling()
        # go_state_canceling isn't atomic, so ensure there is a save.
        j01.save()
        # device state *has* been saved.
        self.device01.refresh_from_db()
        j01.refresh_from_db()
        self.assertEqual(self.device01.health, Device.HEALTH_BAD)
        self.assertEqual(self.device01.state, Device.STATE_RESERVED)
        self.assertEqual(j01.state, TestJob.STATE_CANCELING)
        self.assertEqual(j01.health, TestJob.HEALTH_UNKNOWN)

        j01.go_state_finished(TestJob.HEALTH_CANCELED)
        j01.save()
        self.device01.refresh_from_db()
        j01.refresh_from_db()
        self.assertEqual(self.device01.health, Device.HEALTH_BAD)
        self.assertEqual(j01.health, TestJob.HEALTH_CANCELED)
        self.assertEqual(self.device01.state, Device.STATE_IDLE)
        self.assertEqual(j01.state, TestJob.STATE_FINISHED)


class TestPriorities(TestCase):

    def setUp(self):
        self.worker01 = Worker.objects.create(hostname="worker-01", state=Worker.STATE_ONLINE)
        self.device_type01 = DeviceType.objects.create(name="dt-01")
        self.device01 = Device.objects.create(hostname="device-01", device_type=self.device_type01,
                                              worker_host=self.worker01, health=Device.HEALTH_GOOD,
                                              is_public=True)
        self.user = User.objects.create(username="user-01")
        self.original_health_check = Device.get_health_check

    def tearDown(self):
        Device.get_health_check = self.original_health_check

    def _check_job(self, job, state, actual_device=None):
        job.refresh_from_db()
        self.assertEqual(job.state, state)
        self.assertEqual(job.actual_device, actual_device)

    def test_low_medium_high_without_hc(self):
        # Disable health checks
        Device.get_health_check = lambda cls: None
        jobs = []
        for p in [TestJob.LOW, TestJob.MEDIUM, TestJob.HIGH, TestJob.MEDIUM, TestJob.LOW, 40]:
            j = TestJob.objects.create(requested_device_type=self.device_type01,
                                       user=self.user, submitter=self.user, is_public=True,
                                       definition=_minimal_valid_job(None), priority=p)
            jobs.append(j)

        log = DummyLogger()
        schedule(log)
        self.device01.refresh_from_db()
        self.assertEqual(self.device01.state, Device.STATE_RESERVED)
        self._check_job(jobs[0], TestJob.STATE_SUBMITTED)
        self._check_job(jobs[1], TestJob.STATE_SUBMITTED)
        self._check_job(jobs[2], TestJob.STATE_SCHEDULED, self.device01)
        self._check_job(jobs[3], TestJob.STATE_SUBMITTED)
        self._check_job(jobs[4], TestJob.STATE_SUBMITTED)
        self._check_job(jobs[5], TestJob.STATE_SUBMITTED)

        jobs[2].go_state_finished(TestJob.HEALTH_COMPLETE)
        jobs[2].save()
        self._check_job(jobs[2], TestJob.STATE_FINISHED, self.device01)

        schedule(log)
        self.device01.refresh_from_db()
        self.assertEqual(self.device01.state, Device.STATE_RESERVED)
        self._check_job(jobs[0], TestJob.STATE_SUBMITTED)
        self._check_job(jobs[1], TestJob.STATE_SCHEDULED, self.device01)
        self._check_job(jobs[2], TestJob.STATE_FINISHED, self.device01)
        self._check_job(jobs[3], TestJob.STATE_SUBMITTED)
        self._check_job(jobs[4], TestJob.STATE_SUBMITTED)
        self._check_job(jobs[5], TestJob.STATE_SUBMITTED)

        jobs[1].go_state_finished(TestJob.HEALTH_COMPLETE)
        jobs[1].save()
        self._check_job(jobs[1], TestJob.STATE_FINISHED, self.device01)

        schedule(log)
        self.device01.refresh_from_db()
        self.assertEqual(self.device01.state, Device.STATE_RESERVED)
        self._check_job(jobs[0], TestJob.STATE_SUBMITTED)
        self._check_job(jobs[1], TestJob.STATE_FINISHED, self.device01)
        self._check_job(jobs[2], TestJob.STATE_FINISHED, self.device01)
        self._check_job(jobs[3], TestJob.STATE_SCHEDULED, self.device01)
        self._check_job(jobs[4], TestJob.STATE_SUBMITTED)
        self._check_job(jobs[5], TestJob.STATE_SUBMITTED)

        jobs[3].go_state_finished(TestJob.HEALTH_COMPLETE)
        jobs[3].save()
        self._check_job(jobs[3], TestJob.STATE_FINISHED, self.device01)

        schedule(log)
        self.device01.refresh_from_db()
        self.assertEqual(self.device01.state, Device.STATE_RESERVED)
        self._check_job(jobs[0], TestJob.STATE_SUBMITTED)
        self._check_job(jobs[1], TestJob.STATE_FINISHED, self.device01)
        self._check_job(jobs[2], TestJob.STATE_FINISHED, self.device01)
        self._check_job(jobs[3], TestJob.STATE_FINISHED, self.device01)
        self._check_job(jobs[4], TestJob.STATE_SUBMITTED)
        self._check_job(jobs[5], TestJob.STATE_SCHEDULED, self.device01)

        jobs[5].go_state_finished(TestJob.HEALTH_COMPLETE)
        jobs[5].save()
        self._check_job(jobs[5], TestJob.STATE_FINISHED, self.device01)

        schedule(log)
        self.device01.refresh_from_db()
        self.assertEqual(self.device01.state, Device.STATE_RESERVED)
        self._check_job(jobs[0], TestJob.STATE_SCHEDULED, self.device01)
        self._check_job(jobs[1], TestJob.STATE_FINISHED, self.device01)
        self._check_job(jobs[2], TestJob.STATE_FINISHED, self.device01)
        self._check_job(jobs[3], TestJob.STATE_FINISHED, self.device01)
        self._check_job(jobs[4], TestJob.STATE_SUBMITTED)
        self._check_job(jobs[5], TestJob.STATE_FINISHED, self.device01)

        jobs[0].go_state_finished(TestJob.HEALTH_COMPLETE)
        jobs[0].save()
        self._check_job(jobs[0], TestJob.STATE_FINISHED, self.device01)

        schedule(log)
        self.device01.refresh_from_db()
        self.assertEqual(self.device01.state, Device.STATE_RESERVED)
        self._check_job(jobs[0], TestJob.STATE_FINISHED, self.device01)
        self._check_job(jobs[1], TestJob.STATE_FINISHED, self.device01)
        self._check_job(jobs[2], TestJob.STATE_FINISHED, self.device01)
        self._check_job(jobs[3], TestJob.STATE_FINISHED, self.device01)
        self._check_job(jobs[4], TestJob.STATE_SCHEDULED, self.device01)
        self._check_job(jobs[5], TestJob.STATE_FINISHED, self.device01)

    def test_low_medium_high_with_hc(self):
        # Enable health checks
        self.device_type01.health_denominator = DeviceType.HEALTH_PER_HOUR
        self.device_type01.health_frequency = 24
        self.device_type01.save()
        Device.get_health_check = _minimal_valid_job
        self.assertNotEqual(self.device01.get_health_check(), None)

        jobs = []
        for p in [TestJob.LOW, TestJob.MEDIUM, TestJob.HIGH, TestJob.MEDIUM, TestJob.LOW]:
            j = TestJob.objects.create(requested_device_type=self.device_type01,
                                       user=self.user, submitter=self.user, is_public=True,
                                       definition=_minimal_valid_job(None), priority=p)
            jobs.append(j)

        # Check that an health check will be scheduled before any jobs
        log = DummyLogger()
        schedule(log)
        self.device01.refresh_from_db()
        self.assertEqual(self.device01.state, Device.STATE_RESERVED)
        self._check_job(jobs[0], TestJob.STATE_SUBMITTED)
        self._check_job(jobs[1], TestJob.STATE_SUBMITTED)
        self._check_job(jobs[2], TestJob.STATE_SUBMITTED)
        self._check_job(jobs[3], TestJob.STATE_SUBMITTED)
        self._check_job(jobs[4], TestJob.STATE_SUBMITTED)

        current_hc = self.device01.current_job()
        self.assertEqual(current_hc.state, TestJob.STATE_SCHEDULED)
        current_hc.go_state_finished(TestJob.HEALTH_COMPLETE)
        current_hc.save()

        # Check that the next job is the highest priority
        schedule(log)
        self.device01.refresh_from_db()
        self.assertEqual(self.device01.state, Device.STATE_RESERVED)
        self._check_job(jobs[0], TestJob.STATE_SUBMITTED)
        self._check_job(jobs[1], TestJob.STATE_SUBMITTED)
        self._check_job(jobs[2], TestJob.STATE_SCHEDULED, self.device01)
        self._check_job(jobs[3], TestJob.STATE_SUBMITTED)
        self._check_job(jobs[4], TestJob.STATE_SUBMITTED)
