import datetime
from django.utils import timezone

from lava_scheduler_app.models import (
    Device,
    DeviceType,
    TestJob,
    Tag,
    DeviceDictionary,
    DevicesUnavailableException,
)

from lava_scheduler_daemon.dbjobsource import DatabaseJobSource, find_device_for_job
from lava_scheduler_daemon.tests.base import DatabaseJobSourceTestEngine
from lava_scheduler_app.views import job_cancel

# pylint: disable=attribute-defined-outside-init,superfluous-parens,too-many-ancestors,no-self-use,no-member
# pylint: disable=invalid-name,too-few-public-methods,too-many-statements,unbalanced-tuple-unpacking
# pylint: disable=protected-access,too-many-public-methods,unpacking-non-sequence


# noinspection PyAttributeOutsideInit
class DatabaseJobSourceTest(DatabaseJobSourceTestEngine):

    def restart(self, who):
        self.report_start(who)
        DeviceType.objects.all().delete()

        self.panda = self.factory.ensure_device_type(name='panda')
        self.beaglebone = self.factory.ensure_device_type(name='beaglebone')
        self.arndale = self.factory.ensure_device_type(name='arndale')

        # make sure the DB is in a clean state wrt devices and jobs
        Device.objects.all().delete()
        TestJob.objects.all().delete()
        Tag.objects.all().delete()

        panda = self.panda
        self.panda01 = self.factory.make_device(device_type=panda, hostname='panda01')
        self.panda02 = self.factory.make_device(device_type=panda, hostname='panda02')

        arndale = self.arndale
        self.arndale01 = self.factory.make_device(device_type=arndale, hostname='arndale01')
        self.arndale02 = self.factory.make_device(device_type=arndale, hostname='arndale02')

        self.common_tag = self.factory.ensure_tag('common')
        self.unique_tag = self.factory.ensure_tag('unique')
        self.exclusion_tag = self.factory.ensure_tag('exclude')

        self.black01 = self.factory.make_device(device_type=self.beaglebone, hostname='black01', tags=[self.common_tag])
        self.black02 = self.factory.make_device(device_type=self.beaglebone, hostname='black02', tags=[
            self.common_tag, self.unique_tag])
        self.black03 = self.factory.make_device(device_type=self.beaglebone, hostname='black03', tags=[
            self.exclusion_tag])

        self.user = self.factory.make_user()

        self.master = DatabaseJobSource(lambda: ['panda01', 'panda02'])

    def test_simple_single_node_scheduling(self):
        submitted = self.submit_job(device_type='panda')
        scheduled = self.scheduler_tick()

        self.assertEqual([submitted], scheduled)
        job = scheduled[0]
        self.assertTrue(job.actual_device)

    def test_simple_multi_node_scheduler(self):
        submitted_jobs = self.submit_job(
            device_group=[
                {"device_type": "panda", "count": 1, "role": "client"},
                {"device_type": "panda", "count": 1, "role": "server"},
            ]
        )

        scheduled_jobs = self.scheduler_tick()

        for job in submitted_jobs:
            self.assertTrue(job in scheduled_jobs)

    def test_single_node_and_multinode(self):
        singlenode_job1 = self.submit_job(device_type='panda')
        singlenode_job2 = self.submit_job(device_type='panda')

        self.scheduler_tick()  # should schedule single node jobs and start running them

        singlenode_job1 = TestJob.objects.get(pk=singlenode_job1.id)  # reload
        singlenode_job2 = TestJob.objects.get(pk=singlenode_job2.id)  # reload

        # multinode jobs submitted
        multinode_job1, multinode_job2 = self.submit_job(
            device_group=[
                {"device_type": "panda", "count": 1, "role": "client"},
                {"device_type": "panda", "count": 1, "role": "server"},
            ]
        )

        # job on first device finishes
        self.job_finished(singlenode_job1)
        singlenode_job1 = TestJob.objects.get(pk=singlenode_job1.id)  # reload
        self.assertEqual(singlenode_job1.status, TestJob.COMPLETE)

        self.scheduler_tick()  # should reserve a device for one of jobs in the multinode group

        # one (and only one) of the multinode jobs gets a device assigned
        multinode_job1 = TestJob.objects.get(pk=multinode_job1.id)  # reload
        multinode_job2 = TestJob.objects.get(pk=multinode_job2.id)  # reload
        self.assertTrue(any([job.actual_device is not None for job in [multinode_job1, multinode_job2]]))
        self.assertTrue(any([job.actual_device is None for job in [multinode_job1, multinode_job2]]))

        # job on second board finishes
        self.job_finished(singlenode_job2)
        singlenode_job2 = TestJob.objects.get(pk=singlenode_job2.id)  # reload
        self.assertEqual(singlenode_job2.status, TestJob.COMPLETE)

        self.scheduler_tick()  # should reserve a device for the other jon in the multinode job

        multinode_job1 = TestJob.objects.get(pk=multinode_job1.id)  # reload
        multinode_job2 = TestJob.objects.get(pk=multinode_job2.id)  # reload
        self.assertTrue(all([job.actual_device is not None for job in [multinode_job1, multinode_job2]]))

    def test_health_check(self):

        self.panda.health_check_job = self.factory.make_job_json(health_check='true')
        self.panda.save()

        jobs = self.scheduler_tick()

        panda_jobs = [j for j in jobs if j.actual_device.device_type == self.panda]

        self.assertTrue(len(panda_jobs) > 0)
        self.assertTrue(all([job.actual_device is not None for job in panda_jobs]))

    def test_one_worker_does_not_mess_with_jobs_from_the_others(self):
        # simulate a worker with no devices configured
        worker = DatabaseJobSource(lambda: [])

        self.submit_job(device_type='panda')

        scheduled_jobs = self.scheduler_tick(worker)

        self.assertEqual([], scheduled_jobs)
        self.assertTrue(all([job.status == TestJob.SUBMITTED for job in TestJob.objects.all()]))

    def test_multinode_job_across_different_workers(self):
        master = self.master
        # This is not a normal worker, it is just another database view
        worker = DatabaseJobSource(lambda: ['arndale01'])
        arndale01 = self.arndale01
        self.panda02.state_transition_to(Device.OFFLINE)
        panda01 = self.panda01

        self.submit_job(
            device_group=[
                {"device_type": "panda", "count": 1, "role": "client"},
                {"device_type": "arndale", "count": 1, "role": "server"},
            ]
        )

        master_jobs = self.scheduler_tick(master)
        worker_jobs = self.scheduler_tick(worker)

        self.assertEqual(1, len(master_jobs))
        self.assertEqual(master_jobs[0].actual_device, panda01)

        self.assertEqual(1, len(worker_jobs))
        self.assertEqual(worker_jobs[0].actual_device, arndale01)

    # noinspection PyShadowingNames
    def test_two_multinode_jobs_plus_two_singlenode_jobs(self):

        single1 = self.submit_job(device_type='panda')
        single2 = self.submit_job(device_type='panda')

        multi1a, multi1b = self.submit_job(
            device_group=[
                {"device_type": "panda", "count": 1, "role": "client"},
                {"device_type": "panda", "count": 1, "role": "server"},
            ]
        )

        multi2a, multi2b = self.submit_job(
            device_group=[
                {"device_type": "panda", "count": 1, "role": "client"},
                {"device_type": "panda", "count": 1, "role": "server"},
            ]
        )

        # make it confusing by making both multinode jobs have the exact same
        # submit time
        # also set the target_group string to make the outcome predictable
        now = timezone.now()
        for job in [multi1a, multi1b]:
            job.submit_time = now
            job.target_group = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
            job.save()
        for job in [multi2a, multi2b]:
            job.submit_time = now
            job.target_group = 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'
            job.save()

        scheduled = sorted(self.scheduler_tick(), key=lambda job: job.id)
        self.assertEqual([single1, single2], scheduled)
        single1, single2 = scheduled  # reload locals

        self.job_finished(single1)

        self.assertEqual([], self.scheduler_tick())

        self.job_finished(single2)

        scheduled = sorted(self.scheduler_tick(), key=lambda job: job.id)
        self.assertEqual([multi1a, multi1b], scheduled)

    def test_two_multinode_and_multiworker_jobs_waiting_in_the_queue(self):
        self.report_start(self.whoami())
        master = self.master
        worker = DatabaseJobSource(lambda: ['arndale01', 'arndale02'])

        self.submit_job(device_type='panda')
        self.submit_job(device_type='panda')
        self.submit_job(device_type='arndale')
        self.submit_job(device_type='arndale')

        p1, p2 = self.scheduler_tick(master)
        a1, a2 = self.scheduler_tick(worker)

        m1p, m1a = self.submit_job(
            device_group=[
                {"device_type": "panda", "count": 1, "role": "client"},
                {"device_type": "arndale", "count": 1, "role": "server"},
            ]
        )
        m1p.target_group = m1a.target_group = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
        m1p.save()
        m1a.save()
        m2p, m2a = self.submit_job(
            device_group=[
                {"device_type": "panda", "count": 1, "role": "client"},
                {"device_type": "arndale", "count": 1, "role": "server"},
            ]
        )
        m2p.target_group = m2a.target_group = 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'
        m2p.save()
        m2a.save()

        self.assertEqual([], self.scheduler_tick(master))
        self.assertEqual([], self.scheduler_tick(worker))

        self.job_finished(p1, master)
        self.job_finished(a1, worker)

        self.report_status('bug', self.whoami())
        self.assertEqual([m1p], self.scheduler_tick(master))
        self.assertEqual([m1a], self.scheduler_tick(worker))
        self.report_end(self.whoami())

    def test_looping_mode(self):

        self.panda.health_check_job = self.factory.make_job_json(health_check='true')
        self.panda.save()
        self.device_status('panda01', health_status=Device.HEALTH_LOOPING)
        self.device_status('panda02', status=Device.OFFLINE)

        jobs = self.scheduler_tick()
        self.assertEqual(1, len(jobs))
        health_check = jobs[0]
        self.assertTrue(health_check.health_check)
        self.assertEqual(health_check.actual_device.hostname, 'panda01')

        # no new health check while the original one is running
        self.assertEqual(0, len(self.scheduler_tick()))

        self.job_finished(health_check)
        jobs = self.scheduler_tick()
        self.assertEqual(1, len(jobs))
        new_health_check = jobs[0]
        self.assertTrue(new_health_check.health_check)
        self.assertEqual(new_health_check.actual_device.hostname, 'panda01')

        # again just to be sure
        self.job_finished(new_health_check)
        jobs = self.scheduler_tick()
        self.assertEqual(1, len(jobs))
        third_health_check = jobs[0]
        self.assertTrue(third_health_check.health_check)
        self.assertEqual(third_health_check.actual_device.hostname, 'panda01')

    def test_find_device_for_job(self):
        """
        tests that find_device_for_job gives preference to matching by requested
        _device_ over matching by requested device _type_.
        """
        job = self.submit_job(target='panda01', device_type='panda')
        devices = [self.panda02, self.panda01]
        chosen_device = find_device_for_job(job, devices)
        self.assertEqual(self.panda01, chosen_device)

    def test_find_nonexclusive_device(self):
        """
        test that exclusive devices are not assigned JSON jobs
        """
        self.assertFalse(self.panda01.is_exclusive)
        device_dict = DeviceDictionary.get(self.panda01.hostname)
        self.assertIsNone(device_dict)
        device_dict = DeviceDictionary(hostname=self.panda01.hostname)
        device_dict.parameters = {'exclusive': 'True'}
        device_dict.save()
        self.assertTrue(self.panda01.is_exclusive)
        self.assertRaises(
            DevicesUnavailableException,
            self.submit_job,
            target='panda01', device_type='panda')
        job = self.submit_job(device_type='panda')
        devices = [self.panda02, self.panda01]
        self.assertEqual(
            find_device_for_job(job, devices),
            self.panda02
        )
        device_dict.delete()
        self.assertFalse(self.panda01.is_exclusive)

    def test_offline_health_check(self):
        """
        tests whether we are able to submit health check jobs for devices that
        are OFFLINE.
        """
        self.panda.health_check_job = self.factory.make_job_json(health_check='true')
        self.panda.save()

        self.panda01.state_transition_to(Device.OFFLINE)
        self.panda02.state_transition_to(Device.OFFLINE)

        Device.initiate_health_check_job(self.panda01)
        Device.initiate_health_check_job(self.panda02)

        jobs = self.scheduler_tick()

        self.assertEqual(2, len(jobs))
        self.assertTrue(all([job.actual_device is not None for job in jobs]))
        self.assertEqual(self.panda01.status, Device.OFFLINE)
        self.assertEqual(self.panda02.status, Device.OFFLINE)

    def test_failed_health_check(self):
        """
        Incomplete health checks must take the device offline with a failed health status.
        """
        self.panda.health_check_job = self.factory.make_job_json(health_check='true')
        self.panda.save()
        self.panda01.state_transition_to(Device.OFFLINE)
        self.panda02.state_transition_to(Device.IDLE)
        self.assertEqual(self.panda01.status, Device.OFFLINE)
        self.assertEqual(self.panda02.status, Device.IDLE)
        self.assertEqual(self.panda01.health_status, Device.HEALTH_UNKNOWN)
        self.assertEqual(self.panda02.health_status, Device.HEALTH_UNKNOWN)

        jobs = self.scheduler_tick()
        for job in jobs:
            job_obj = TestJob.objects.get(pk=job.id)  # reload
            job_obj.status = TestJob.INCOMPLETE
            self.job_failed(job_obj)

        # Always go to the database to check the effects of job completion.
        self.panda01 = Device.objects.get(hostname="panda01")  # reload
        self.panda02 = Device.objects.get(hostname="panda02")  # reload
        self.assertEqual(self.panda01.status, Device.OFFLINE)
        self.assertEqual(self.panda02.status, Device.OFFLINE)
        self.assertEqual(self.panda01.health_status, Device.HEALTH_UNKNOWN)
        self.assertEqual(self.panda02.health_status, Device.HEALTH_FAIL)

    def test_find_device_for_job_with_tag(self):
        """
        test that tags are used to set which device is selected
        panda should be excluded by device_type
        black03 should be excluded as it does not have the common tag
        black02 would also match but is not included in the device check
        """
        job = self.submit_job(device_type='beaglebone', tags=[
            self.common_tag.name
        ])
        devices = [self.panda01, self.arndale02, self.black01, self.black03]
        chosen_device = find_device_for_job(job, devices)
        self.assertEqual(self.black01, chosen_device)

    def test_find_device_for_devices_without_tags(self):
        """
        ensure that tags do not interfere with finding devices of
        unrelated types
        """
        job = self.submit_job(device_type='arndale', tags=[])
        devices = [self.panda01, self.arndale02, self.black01, self.black03]
        chosen_device = find_device_for_job(job, devices)
        self.assertEqual(self.arndale02, chosen_device)
        try:
            self.submit_job(device_type='arndale', tags=[
                self.common_tag.name
            ])
        except DevicesUnavailableException:
            pass
        else:
            self.fail("Offered an arndale when no arndale support the requested tags")

    def test_find_device_for_job_with_multiple_tags(self):
        """
        test that tags are used to set which device is selected
        choose black02 and never black01 due to the presence
        of both the common tag and the unique tag only with black02.
        """

        job = self.submit_job(device_type='beaglebone', tags=[
            self.common_tag.name, self.unique_tag.name
        ])
        devices = [self.panda01, self.black01, self.black02, self.black03]
        chosen_device = find_device_for_job(job, devices)
        self.assertEqual(self.black02, chosen_device)
        try:
            job = self.submit_job(device_type='panda', tags=[
                self.common_tag.name, self.unique_tag.name
            ])
        except DevicesUnavailableException:
            pass
        else:
            self.fail("Offered a panda when no pandas support the requested tags")

        devices = [self.black01, self.black02, self.black03]
        chosen_device = find_device_for_job(job, devices)
        self.assertEqual(self.black02, chosen_device)

        devices = [self.arndale02, self.panda02, self.black02, self.black03]
        chosen_device = find_device_for_job(job, devices)
        self.assertEqual(self.black02, chosen_device)

    def test_find_device_with_single_job_tag(self):
        """
        tests handling of jobs with less tags than supported but still
        choosing one tag which only applies to one device in the set.
        """
        job = self.submit_job(device_type='beaglebone', tags=[
            self.unique_tag.name
        ])
        devices = [self.panda02, self.black02, self.black03]
        chosen_device = find_device_for_job(job, devices)
        self.assertEqual(self.black02, chosen_device)

        job = self.submit_job(device_type='beaglebone', tags=[
            self.exclusion_tag.name
        ])
        devices = [self.panda02, self.black02, self.black03]
        chosen_device = find_device_for_job(job, devices)
        self.assertEqual(self.black03, chosen_device)

    def _test_basic_vm_groups_scheduling(self):
        self.factory.ensure_device_type(name='kvm-arm')
        self.factory.ensure_device_type(name='dynamic-vm')
        self.submit_job(vm_group={
            "host": {
                "device_type": "arndale",
                "role": "host"
            },
            "vms": [
                {
                    "device_type": "kvm-arm",
                    "role": "server"
                },
                {
                    "device_type": "kvm-arm",
                    "role": "client"
                }
            ]
        })
        self.scheduler_tick()

    def test_handle_cancelling_jobs(self):
        """
        tests whether handle_cancelling_jobs does the right thing.
        """
        job = self.submit_job(device_type='panda')
        scheduled = self.scheduler_tick()
        self.assertEqual([job], scheduled)
        job = TestJob.objects.get(pk=job.id)  # reload
        self.assertEqual(job.status, TestJob.RUNNING)
        self.assertEqual(job.actual_device.status, Device.RUNNING)
        self.assertTrue(job.actual_device.current_job)
        job.status = TestJob.CANCELING
        job.save()
        self.assertEqual(job.status, TestJob.CANCELING)
        self.assertEqual(job.actual_device.status, Device.RUNNING)
        self.assertTrue(job.actual_device.current_job)
        self.scheduler_tick()
        job = TestJob.objects.get(pk=job.id)  # reload
        self.assertEqual(TestJob.STATUS_CHOICES[job.status], TestJob.STATUS_CHOICES[TestJob.CANCELED])
        self.assertEqual(job.actual_device.status, Device.IDLE)
        self.assertFalse(job.actual_device.current_job)

    class FakeRequest(object):

        def __init__(self, user):
            self.user = user

    def test_multinode_cancel(self):
        """
        Test cancel on a multinode group
        """
        self.restart(self.whoami())
        submitted_jobs = self.submit_job(
            device_group=[
                {"device_type": "panda", "count": 1, "role": "client"},
                {"device_type": "panda", "count": 1, "role": "server"},
            ]
        )

        scheduled_jobs = self.scheduler_tick()

        for job in submitted_jobs:
            self.assertTrue(job in scheduled_jobs)
        waiting_job = scheduled_jobs[0]
        failed_job = scheduled_jobs[1]
        waiting_job = TestJob.objects.get(pk=waiting_job.id)  # reload
        failed_job = TestJob.objects.get(pk=failed_job.id)  # reload
        fail_panda = failed_job.actual_device
        wait_panda = waiting_job.actual_device

        self.scheduler_tick()

        fail_panda = Device.objects.get(hostname=fail_panda.hostname)
        self.assertEqual(fail_panda.status, Device.RUNNING)
        self.assertEqual(waiting_job.target_group, failed_job.target_group)
        self.job_failed(failed_job)

        self.scheduler_tick()

        failed_job = TestJob.objects.get(pk=failed_job.id)  # reload
        fail_panda = Device.objects.get(hostname=fail_panda.hostname)
        self.assertTrue(failed_job.status, TestJob.INCOMPLETE)
        self.assertTrue(waiting_job.status, TestJob.RUNNING)
        self.assertEqual(fail_panda.status, Device.IDLE)

        self.scheduler_tick()

        self.report_status("second_job", self.whoami())
        self.submit_job(
            device_group=[
                {"device_type": "panda", "count": 1, "role": "client"},
                {"device_type": "arndale", "count": 1, "role": "server"},
            ]
        )

        scheduled_jobs = self.scheduler_tick()
        unconnected_group = [scheduled.target_group for scheduled in scheduled_jobs if scheduled.id != waiting_job.id]
        self.assertNotEqual(unconnected_group[0], waiting_job.target_group)

        self.report_status("cancel - first wait", self.whoami())
        self.scheduler_tick()

        fail_panda = Device.objects.get(hostname=fail_panda.hostname)
        self.assertEqual(Device.STATUS_CHOICES[fail_panda.status], Device.STATUS_CHOICES[Device.RUNNING])

        waiting_job = TestJob.objects.get(pk=waiting_job.id)  # reload
        failed_job = TestJob.objects.get(pk=failed_job.id)  # reload
        immutable_status = failed_job.status
        self.assertIsNone(waiting_job.failure_comment)
        self.assertIsNone(failed_job.failure_comment)
        # the bare cancel operation works, it is the API which wraps with the multinode check
        request = self.FakeRequest(user=self.user)
        job_cancel(request, waiting_job.id)

        self.submit_job(
            device_group=[
                {"device_type": "panda", "count": 1, "role": "client"},
                {"device_type": "panda", "count": 1, "role": "server"},
            ]
        )

        fail_panda = Device.objects.get(hostname=fail_panda.hostname)
        self.assertEqual(Device.STATUS_CHOICES[fail_panda.status], Device.STATUS_CHOICES[Device.RUNNING])
        waiting_job = TestJob.objects.get(pk=waiting_job.id)  # reload
        failed_job = TestJob.objects.get(pk=failed_job.id)  # reload

        # cancelling waiting_job must not change the status of a failed job in the same group
        # this could cause the handle_cancelling_jobs function to change the Device state
        # the waiting_job is the job which was cancelled, failed_job has already ended
        # the failure_comment is preserved for all jobs in the target_group
        self.assertEqual(TestJob.STATUS_CHOICES[failed_job.status], TestJob.STATUS_CHOICES[immutable_status])
        self.assertIsNotNone(waiting_job.failure_comment)
        self.assertIsNotNone(failed_job.failure_comment)
        self.assertIn('Canceled', waiting_job.failure_comment)
        self.assertIn(request.user.username, waiting_job.failure_comment)
        self.assertIn('Canceled', failed_job.failure_comment)
        self.assertIn(request.user.username, failed_job.failure_comment)
        fail_panda = Device.objects.get(hostname=fail_panda.hostname)
        wait_panda = Device.objects.get(hostname=wait_panda.hostname)
        self.assertIn(wait_panda.hostname, str(wait_panda.current_job))
        self.assertIn(fail_panda.hostname, str(fail_panda.current_job))

        self.scheduler_tick()

        self.report_status("cancel wait", self.whoami())

        waiting_job = TestJob.objects.get(pk=waiting_job.id)  # reload
        fail_panda = Device.objects.get(hostname=fail_panda.hostname)
        wait_panda = Device.objects.get(hostname=wait_panda.hostname)

        waiting_job = TestJob.objects.get(pk=waiting_job.id)  # reload
        self.assertIn(
            TestJob.STATUS_CHOICES[waiting_job.status],
            [
                TestJob.STATUS_CHOICES[TestJob.CANCELED],
                TestJob.STATUS_CHOICES[TestJob.CANCELING]
            ])

        self.scheduler_tick()

        fail_panda = Device.objects.get(hostname=fail_panda.hostname)
        wait_panda = Device.objects.get(hostname=wait_panda.hostname)
        self.assertIn(wait_panda.hostname, str(wait_panda.current_job))
        self.assertIn(fail_panda.hostname, str(fail_panda.current_job))

        self.assertEqual(Device.STATUS_CHOICES[fail_panda.status], Device.STATUS_CHOICES[Device.RUNNING])
        self.assertIn(
            Device.STATUS_CHOICES[wait_panda.status],
            [
                Device.STATUS_CHOICES[Device.IDLE],
                Device.STATUS_CHOICES[Device.RESERVED],
                Device.STATUS_CHOICES[Device.RUNNING],
            ])

        self.assertIn(
            TestJob.STATUS_CHOICES[waiting_job.status],
            [
                TestJob.STATUS_CHOICES[TestJob.CANCELED],
                TestJob.STATUS_CHOICES[TestJob.CANCELING]
            ])
        self.cleanup(self.whoami())

    def test_cleanup_state(self):
        """
        When reserving a device, if the current_job value for that Device is not None
        then handle this.
        """
        self.restart(self.whoami())

        for panda in Device.objects.filter(device_type=self.panda):
            self.assertIsNone(panda.current_job)

        self.submit_job(
            device_group=[
                {"device_type": "panda", "count": 1, "role": "client"},
                {"device_type": "panda", "count": 1, "role": "server"},
            ]
        )

        scheduled_jobs = self.scheduler_tick()

        for panda in Device.objects.filter(device_type=self.panda):
            self.assertIsNotNone(panda.current_job)

        self.submit_job(
            device_group=[
                {"device_type": "panda", "count": 1, "role": "client"},
                {"device_type": "panda", "count": 1, "role": "server"},
            ]
        )

        self.report_status('deliberately setting broken job data', self.whoami())
        incomplete_job = scheduled_jobs[0]
        complete_job = scheduled_jobs[1]
        good_panda = complete_job.actual_device
        incomplete_job = TestJob.objects.get(pk=incomplete_job.id)  # reload
        bad_panda = incomplete_job.actual_device
        bad_panda = Device.objects.get(hostname=bad_panda.hostname)
        bad_panda.current_job = incomplete_job
        bad_panda.status = Device.IDLE
        bad_panda.save()
        bad_panda = Device.objects.get(hostname=bad_panda.hostname)
        self.assertIsNotNone(bad_panda.current_job)
        self.assertEqual(bad_panda.current_job, incomplete_job)
        self.assertEqual(Device.STATUS_CHOICES[bad_panda.status], Device.STATUS_CHOICES[Device.IDLE])

        self.scheduler_tick()

        self.report_status("Should have seen refusal to reserve %s" % bad_panda, self.whoami())

        bad_panda = Device.objects.get(hostname=bad_panda.hostname)
        self.assertIsNotNone(bad_panda.current_job)
        self.assertEqual(bad_panda.current_job, incomplete_job)
        self.assertEqual(Device.STATUS_CHOICES[bad_panda.status], Device.STATUS_CHOICES[Device.IDLE])

        self.report_status('faking admin action to clear broken job', self.whoami())
        bad_panda.current_job = None
        bad_panda.save()

        self.scheduler_tick()

        self.report_status("Successful reserve for %s" % bad_panda, self.whoami())
        bad_panda = Device.objects.get(hostname=bad_panda.hostname)  # reload
        self.assertIsNotNone(bad_panda.current_job)
        self.assertEqual(Device.STATUS_CHOICES[bad_panda.status], Device.STATUS_CHOICES[Device.RESERVED])

        self.scheduler_tick()

        self.report_status('let the original multinode job finish to free up the other device', self.whoami())
        complete_job = TestJob.objects.get(id=complete_job.id)  # reload
        complete_job.status = TestJob.COMPLETE
        good_panda = Device.objects.get(hostname=good_panda.hostname)  # reload
        good_panda.status = Device.IDLE
        good_panda.current_job = None
        complete_job.save()
        good_panda.save()

        self.scheduler_tick()

        bad_panda = Device.objects.get(hostname=bad_panda.hostname)  # reload
        self.assertIsNotNone(bad_panda.current_job)
        self.assertIn(
            Device.STATUS_CHOICES[bad_panda.status], [
                Device.STATUS_CHOICES[Device.RUNNING],
                Device.STATUS_CHOICES[Device.RESERVED]]
        )

        self.scheduler_tick()

        self.cleanup(self.whoami())

    def test_find_multinode_offline(self):
        """
        Test that a multinode job where one device is offline does not become running
        """
        self.restart(self.whoami())
        # two pandas, two arndales, three blacks
        for panda in Device.objects.filter(device_type=self.panda):
            self.assertIsNone(panda.current_job)
        devices = [self.panda01, self.arndale02, self.black01, self.black03]
        for device in devices:
            device.status = Device.OFFLINING
            device.save(update_fields=['status'])
        # leaves only one of each online
        self.scheduler_tick()
        self.assertEqual(
            set([Device.STATUS_CHOICES[panda.status] for panda in Device.objects.filter(device_type=self.panda)]),
            {Device.STATUS_CHOICES[Device.OFFLINING], Device.STATUS_CHOICES[Device.IDLE]}
        )
        self.assertEqual(
            Device.objects.filter(device_type=self.panda, status=Device.OFFLINING).count(), 1
        )
        self.assertEqual(
            Device.objects.filter(device_type=self.panda, status=Device.IDLE).count(), 1
        )
        self.assertEqual(
            TestJob.objects.filter(status__in=[TestJob.SUBMITTED, TestJob.RUNNING]).count(), 0
        )
        self.submit_job(
            device_group=[
                {"device_type": "panda", "count": 1, "role": "client"},
                {"device_type": "panda", "count": 1, "role": "server"},
            ]
        )
        count = 0
        while count <= 10:
            self.scheduler_tick()
            self.assertEqual(
                Device.objects.filter(device_type=self.panda, status=Device.OFFLINING).count(), 1
            )
            self.assertEqual(
                Device.objects.filter(device_type=self.panda, status__in=[Device.RESERVED, Device.IDLE]).count(), 1
            )
            self.assertEqual(
                TestJob.objects.filter(status__in=[TestJob.RUNNING]).count(), 0
            )
            self.assertEqual(
                TestJob.objects.filter(status__in=[TestJob.SUBMITTED]).count(), 2
            )
            count += 1

        self.cleanup(self.whoami())

    def test_failed_reservation(self):
        """
        Test is_ready_to_start
        """
        self.restart(self.whoami())
        # two pandas, two arndales, three blacks
        for panda in Device.objects.filter(device_type=self.panda):
            self.assertIsNone(panda.current_job)
        self.assertEqual(TestJob.objects.all().count(), 0)
        job = self.submit_job(device_type='panda')
        self.scheduler_tick()
        job = TestJob.objects.get(id=job.id)  # reload
        self.assertIn(job.actual_device.hostname, [self.panda01.hostname, self.panda02.hostname])
        devices = [self.panda01]
        for device in devices:
            device.current_job = job
            device.save(update_fields=['current_job'])
        self.panda01 = Device.objects.get(hostname=self.panda01.hostname)  # reload
        self.assertIsNotNone(self.panda01.current_job)
        job.status = TestJob.INCOMPLETE
        job.save(update_fields=['status'])
        self.scheduler_tick()
        self.panda02.put_into_maintenance_mode(self.user, 'unit test', None)
        self.scheduler_tick()

        # scheduler tick can clear the current job. This test is for when it fails to do so.
        for device in devices:
            device.current_job = job
            device.save(update_fields=['current_job'])
        self.panda01 = Device.objects.get(hostname=self.panda01.hostname)  # reload
        self.assertIsNotNone(self.panda01.current_job)
        job = self.submit_job(device_type='panda')
        job = TestJob.objects.get(id=job.id)  # reload
        self.assertIsNone(job.actual_device)
        self.assertFalse(job.is_ready_to_start)
        self.scheduler_tick()
        job = TestJob.objects.get(id=job.id)  # reload
        self.assertIsNone(job.actual_device)
        self.assertFalse(job.is_ready_to_start)
        self.cleanup(self.whoami())

    def test_failed_reservation_multinode(self):
        self.restart(self.whoami())
        master = self.master
        worker = DatabaseJobSource(lambda: ['arndale01'])
        # two pandas, two arndales, three blacks
        for panda in Device.objects.filter(device_type=self.panda):
            self.assertIsNone(panda.current_job)
        self.assertEqual(TestJob.objects.all().count(), 0)
        self.panda02.put_into_maintenance_mode(self.user, 'unit test', None)
        job1, job2 = self.submit_job(
            device_group=[
                {"device_type": "panda", "count": 1, "role": "client"},
                {"device_type": "arndale", "count": 1, "role": "server"},
            ]
        )
        # create a queue
        job3, job4 = self.submit_job(
            device_group=[
                {"device_type": "panda", "count": 1, "role": "client"},
                {"device_type": "arndale", "count": 1, "role": "server"},
            ]
        )
        # master_jobs = self.scheduler_tick(master)
        worker_jobs = self.scheduler_tick(worker)
        # self.scheduler_tick()
        job1 = TestJob.objects.get(id=job1.id)  # reload
        job1.status = TestJob.INCOMPLETE
        job1.save(update_fields=['status'])
        self.panda01 = Device.objects.get(hostname=self.panda01.hostname)  # reload
        self.panda01.status = Device.OFFLINING
        self.panda01.current_job = job1
        self.panda01.save(update_fields=['status', 'current_job'])

        # master_jobs = self.scheduler_tick(master)
        worker_jobs = self.scheduler_tick(worker)
        # self.scheduler_tick()
        job2 = TestJob.objects.get(id=job2.id)  # reload
        job2.cancel(self.user)
        master_jobs = self.scheduler_tick(master)
        # worker_jobs = self.scheduler_tick(worker)
        # self.scheduler_tick()

        self.panda01 = Device.objects.get(hostname=self.panda01.hostname)  # reload
        job3 = TestJob.objects.get(id=job3.id)  # reload

        # FORCE the buggy status
        job3.actual_device = self.panda01
        job3.save(update_fields=['actual_device'])

        job3 = TestJob.objects.get(id=job3.id)  # reload
        self.assertFalse(job3.is_ready_to_start)
        self.assertEqual(job3.actual_device, self.panda01)
        self.assertNotEqual(job3.actual_device.current_job, job3)

        job4 = TestJob.objects.get(id=job4.id)  # reload
        if job4.actual_device:
            self.assertNotEqual(job4.actual_device, self.panda01)
        job3 = TestJob.objects.get(id=job3.id)  # reload
        self.assertFalse(job4.is_ready_to_start)

        master_jobs = self.scheduler_tick(master)
        worker_jobs = self.scheduler_tick(worker)
        # self.scheduler_tick()

        job3 = TestJob.objects.get(id=job3.id)  # reload
        # if job3.actual_device:
        #     self.assertNotEqual(job3.actual_device, self.panda01)
        self.assertFalse(job3.is_ready_to_start)

        job4 = TestJob.objects.get(id=job4.id)  # reload
        if job4.actual_device:
            self.assertNotEqual(job4.actual_device, self.panda01)
        self.assertFalse(job4.is_ready_to_start)

        self.cleanup(self.whoami())

    def test_large_queues(self):
        self.restart(self.whoami())
        data = {}
        for n in range(0, 20):
            job = self.submit_job(device_type='panda')
            data[n] = job
        self.scheduler_tick()
        self.assertEqual(
            Device.objects.filter(device_type=self.panda).count(),
            TestJob.objects.filter(status=TestJob.RUNNING).count()
        )
        for n in range(0, 4):
            for job in TestJob.objects.filter(status=TestJob.RUNNING):
                job.cancel(self.user)
            self.assertEqual(TestJob.objects.filter(status=TestJob.RUNNING).count(), 0)

            self.scheduler_tick()
            self.assertEqual(
                Device.objects.filter(device_type=self.panda).count(),
                TestJob.objects.filter(status=TestJob.RUNNING).count()
            )

        self.assertEqual(TestJob.objects.filter(status=TestJob.SUBMITTED).count(), 10)
        self.cleanup(self.whoami())
