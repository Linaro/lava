# Copyright (C) 2017-2018 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#         Senthil Kumaran <senthil.kumaran@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import os
import xmlrpc.client
from functools import wraps

import yaml
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count

from lava_common.yaml import yaml_safe_dump, yaml_safe_load
from lava_results_app.models import TestCase
from lava_scheduler_app.dbutils import (
    active_device_types,
    device_type_summary,
    testjob_submission,
)
from lava_scheduler_app.models import (
    Device,
    DevicesUnavailableException,
    DeviceType,
    TestJob,
)
from lava_scheduler_app.schema import (
    SubmissionException,
    validate_device,
    validate_submission,
)
from linaro_django_xmlrpc.models import ExposedV2API

# functions need to be members to be exposed in the API


# to make a function visible in the API, it must be a member of SchedulerAPI


def check_perm(perm):
    """decorator to check that the caller has the given permission"""

    def decorator(f):
        @wraps(f)
        def wrapper(self, *args, **kwargs):
            self._authenticate()
            if not self.user.has_perm(perm):
                raise xmlrpc.client.Fault(
                    403,
                    "User '%s' is missing permission %s." % (self.user.username, perm),
                )
            return f(self, *args, **kwargs)

        return wrapper

    return decorator


def build_device_status_display(state, health):
    if state == Device.STATE_IDLE:
        if health in [Device.HEALTH_GOOD, Device.HEALTH_UNKNOWN]:
            return "idle"
        elif health == Device.HEALTH_RETIRED:
            return "retired"
        else:
            return "offline"
    elif state == Device.STATE_RESERVED:
        return "reserved"
    else:
        return "running"


class SchedulerAPI(ExposedV2API):
    def submit_job(self, job_data):
        """
        Name
        ----
        `submit_job` (`job_data`)

        Description
        -----------
        Submit the given job data which is in LAVA job JSON or YAML format as a
        new job to LAVA scheduler.

        Arguments
        ---------
        `job_data`: string
            Job JSON or YAML string.

        Return value
        ------------
        This function returns an XML-RPC integer which is the newly created
        job's id, provided the user is authenticated with an username and token.
        If the job is a multinode job, this function returns the list of created
        job IDs.
        """
        self._authenticate()
        try:
            job = testjob_submission(job_data, self.user)
        except SubmissionException as exc:
            raise xmlrpc.client.Fault(400, "Problem with submitted job data: %s" % exc)
        except ValueError as exc:
            raise xmlrpc.client.Fault(400, "Decoding job submission failed: %s." % exc)
        except yaml.YAMLError as exc:
            raise xmlrpc.client.Fault(400, "Invalid job definition: %s." % exc)
        except (Device.DoesNotExist, DeviceType.DoesNotExist):
            raise xmlrpc.client.Fault(404, "Specified device or device type not found.")
        except DevicesUnavailableException as exc:
            raise xmlrpc.client.Fault(400, "Device unavailable: %s" % str(exc))
        if isinstance(job, list):
            return [j.sub_id for j in job]
        else:
            return job.id

    def resubmit_job(self, job_id):
        """
        Name
        ----
        `resubmit_job` (`job_id`)

        Description
        -----------
        Resubmit the given job referred by its id.

        Arguments
        ---------
        `job_id`: string
            The job's id which should be re-submitted.

        Return value
        ------------
        This function returns an XML-RPC integer which is the newly created
        job's id,  provided the user is authenticated with an username and
        token.
        """
        self._authenticate()
        try:
            job = TestJob.get_by_job_number(job_id)
        except TestJob.DoesNotExist:
            raise xmlrpc.client.Fault(404, "Job '%s' was not found." % job_id)

        if not job.can_view(self.user):
            raise xmlrpc.client.Fault(
                403, "Job '%s' not available to user '%s'." % (job_id, self.user)
            )

        if job.is_multinode:
            return self.submit_job(job.multinode_definition)
        else:
            return self.submit_job(job.definition)

    def cancel_job(self, job_id):
        """
        Name
        ----
        `cancel_job` (`job_id`)

        Description
        -----------
        Cancel the given job referred by its id.

        Arguments
        ---------
        `job_id`: string
            Job id which should be canceled.

        Return value
        ------------
        None. The user should be authenticated with an username and token.
        """
        self._authenticate()
        if not job_id:
            raise xmlrpc.client.Fault(400, "Bad request: TestJob id was not specified.")

        with transaction.atomic():
            try:
                job = TestJob.get_by_job_number(job_id)
            except TestJob.DoesNotExist:
                raise xmlrpc.client.Fault(404, "Job '%s' was not found." % job_id)

            if not job.can_view(self.user):
                raise xmlrpc.client.Fault(
                    403, "Job '%s' not available to user '%s'." % (job_id, self.user)
                )

            try:
                job.cancel(self.user)
            except PermissionDenied:
                raise xmlrpc.client.Fault(403, "Permission denied.")
        return True

    def validate_yaml(self, yaml_string):
        """
        Name
        ----
        validate_yaml (yaml_job_data)

        Description
        -----------
        Validate the supplied pipeline YAML against the submission schema.

        Note: this does not validate the job itself, just the YAML against the
        submission schema. A job which validates against the schema can still be
        an invalid job for the dispatcher and such jobs will be accepted as Submitted,
        scheduled and then marked as Incomplete with a failure comment. Full validation
        only happens after a device has been assigned to the Submitted job.

        Arguments
        ---------
        'yaml_job_data': string

        Return value
        ------------
        Raises an Exception if the yaml_job_data is invalid.
        """
        try:
            # YAML can parse JSON as YAML, JSON cannot parse YAML at all
            yaml_data = yaml_safe_load(yaml_string)
        except yaml.YAMLError as exc:
            raise xmlrpc.client.Fault(400, "Decoding job submission failed: %s." % exc)
        try:
            # validate against the submission schema.
            validate_submission(yaml_data)  # raises SubmissionException if invalid.
        except SubmissionException as exc:
            raise xmlrpc.client.Fault(400, "Invalid YAML submission: %s" % exc)

    def job_output(self, job_id, offset=0):
        """
        Name
        ----
        `job_output` (`job_id`, `offset=0`)

        Description
        -----------
        Get the output of given job id.

        Arguments
        ---------
        `job_id`: string
            Job id for which the output is required.
        `offset`: integer
            Offset from which to start reading the output file specified in bytes.
            It defaults to 0.

        Return value
        ------------
        This function returns an XML-RPC binary data of output file, provided
        the user is authenticated with an username and token.
        """
        try:
            job = TestJob.get_by_job_number(job_id)
        except TestJob.DoesNotExist:
            raise xmlrpc.client.Fault(404, "Job '%s' was not found." % job_id)

        if not job.can_view(self.user):
            raise xmlrpc.client.Fault(
                403, "Job '%s' not available to user '%s'." % (job_id, self.user)
            )

        # Open the logs
        output_path = os.path.join(job.output_dir, "output.yaml")
        try:
            with open(output_path, encoding="utf-8", errors="replace") as f_logs:
                if f_logs:
                    f_logs.seek(offset)
                return xmlrpc.client.Binary(f_logs.read().encode("UTF-8"))
        except OSError:
            raise xmlrpc.client.Fault(404, "Job output not found.")

    def all_devices(self):
        """
        Name
        ----
        `all_devices` ()

        Description
        -----------
        Get all the available devices with their state and type information.

        Arguments
        ---------
        None

        Return value
        ------------
        This function returns an XML-RPC array in which each item is a list of
        device hostname, device type, device state, current running job id and
        if device is pipeline. For example:

        [
            ['panda01', 'panda', 'running', 'good', 164, False],
            ['qemu01', 'qemu', 'idle', 'unknwon', None, True],
        ]
        """

        devices_list = Device.objects.visible_by_user(self.user).exclude(
            health=Device.HEALTH_RETIRED
        )

        def job_pk(device):
            job = device.current_job()
            return job.pk if job else None

        return [
            [
                dev.hostname,
                dev.device_type.name,
                build_device_status_display(dev.state, dev.health),
                job_pk(dev),
                True,
            ]
            for dev in devices_list
        ]

    def all_device_types(self):
        """
        Name
        ----
        `all_device_types` ()

        Description
        -----------
        Get all the available device types with their state and count
        information.

        Arguments
        ---------
        None

        Return value
        ------------
        This function returns an XML-RPC array in which each item is a dict
        which contains name (device type), idle, busy, offline counts.
        For example:

        [{'idle': 1, 'busy': 0, 'name': 'panda', 'offline': 0},
        {'idle': 1, 'busy': 0, 'name': 'qemu', 'offline': 0}]
        """

        all_device_types = []
        keys = ["busy", "idle", "offline"]

        device_types = device_type_summary(self.user)

        for dev_type in device_types:
            device_type = {"name": dev_type["device_type"]}
            for key in keys:
                device_type[key] = dev_type[key]
            all_device_types.append(device_type)

        return all_device_types

    def get_recent_jobs_for_device_type(
        self, device_type, count=1, restrict_to_user=False
    ):
        """
        Name
        ----

        `get_recent_jobs_for_device_type` (
            `device_type`,
            `count=1`,
            `restrict_to_user=False`,
        )

        Description
        -----------
        Get details of recently finished jobs for a given device_type. Limits the list
        to test jobs submitted by the user making the query if restrict_to_user is set
        to True. Get only the most recent job by default, but count can be set higher to
        get for example the last 10 jobs.

        Arguments
        ---------
        `device_type`: string
            Name of the device_type for which you want the jobs
        `count`: integer (Optional, default=1)
            Number of last jobs you want
        `restrict_to_user`: boolean (Optional, default=False)
            Fetch only the jobs submitted by the user making the query if set to True

        Return value
        ------------
        This function returns a list of dictionaries, which correspond to the
        list of recently finished jobs information (Complete or Incomplete)
        for this device, ordered from youngest to oldest.

        [
            {
                'description': 'ramdisk health check',
                'id': 359828,
                'status': 'Complete',
                'device': 'black01'
            },
            {
                'description': 'standard ARMMP NFS',
                'id': 359827
                'status': 'Incomplete',
                'device': 'black02'
            }
        ]
        """
        if not device_type:
            raise xmlrpc.client.Fault(
                400, "Bad request: device_type was not specified."
            )
        if count < 0:
            raise xmlrpc.client.Fault(400, "Bad request: count must not be negative.")
        try:
            dt = DeviceType.objects.get(name=device_type, display=True)
        except Device.DoesNotExist:
            raise xmlrpc.client.Fault(
                404, "DeviceType '%s' was not found." % device_type
            )

        job_qs = (
            TestJob.objects.filter(state=TestJob.STATE_FINISHED)
            .filter(requested_device_type=dt)
            .visible_by_user(self.user)
            .order_by("-id")
        )
        if restrict_to_user:
            job_qs = job_qs.filter(submitter=self.user)
        job_list = []
        for job in job_qs.all()[:count]:
            hostname = ""
            if job.actual_device:
                hostname = job.actual_device.hostname
            job_dict = {
                "id": job.id,
                "description": job.description,
                "status": job.get_legacy_status_display(),
                "device": hostname,
            }
            job_list.append(job_dict)
        return job_list

    def get_recent_jobs_for_device(self, device, count=1, restrict_to_user=False):
        """
        Name
        ----

        `get_recent_jobs_for_device` (`device`, `count=1`, `restrict_to_user=False`)

        Description
        -----------
        Get details of recently finished jobs for a given device. Limits the list
        to test jobs submitted by the user making the query if restrict_to_user is set
        to True. Get only the most recent job by default, but count can be set higher to
        get for example the last 10 jobs.

        Arguments
        ---------
        `device`: string
            Name of the device for which you want the jobs
        `count`: integer (Optional, default=1)
            Number of last jobs you want
        `restrict_to_user`: boolean (Optional, default=False)
            Fetch only the jobs submitted by the user making the query if set to True

        Return value
        ------------
        This function returns a list of dictionaries, which correspond to the
        list of recently finished jobs information (Complete or Incomplete)
        for this device, ordered from youngest to oldest.

        [
            {
                'description': 'mainline--armada-370-db--multi_v7_defconfig--network',
                'id': 359828,
                'status': 'Complete'
            },
            {
                'description': 'mainline--armada-370-db--multi_v7_defconfig--sata',
                'id': 359827
                'status': 'Incomplete'
            }
        ]
        """
        if not device:
            raise xmlrpc.client.Fault(400, "Bad request: device was not specified.")
        if count < 0:
            raise xmlrpc.client.Fault(400, "Bad request: count must not be negative.")
        try:
            device_obj = Device.objects.get(hostname=device)
        except Device.DoesNotExist:
            raise xmlrpc.client.Fault(404, "Device '%s' was not found." % device)

        if not device_obj.can_view(self.user):
            raise xmlrpc.client.Fault(
                403, "Device '%s' not available to user '%s'." % (device, self.user)
            )
        job_qs = (
            TestJob.objects.filter(state=TestJob.STATE_FINISHED)
            .filter(actual_device=device_obj)
            .visible_by_user(self.user)
            .order_by("-id")
        )
        if restrict_to_user:
            job_qs = job_qs.filter(submitter=self.user)
        job_list = []
        for job in job_qs.all()[:count]:
            job_dict = {
                "id": job.id,
                "description": job.description,
                "status": job.get_legacy_status_display(),
            }
            job_list.append(job_dict)
        return job_list

    def get_device_type_by_alias(self, alias):
        """
        Name
        ----

        `get_device_type_by_alias` (`alias`)

        Description
        -----------
        Get the matching device-type(s) for the specified alias. It is
        possible that more than one device-type can be returned, depending
        on local admin configuration. An alias can be used to provide the
        link between the device-type name and the Device Tree name.
        It is possible for multiple device-types to have the same alias
        (to assist in transitions and migrations).
        The specified alias string can be a partial match, returning all
        device-types which have an alias name containing the requested
        string.

        Arguments
        ---------
        `alias`: string
            Name of the alias to lookup

        Return value
        ------------
        This function returns a dictionary containing the alias as the key
        and a list of device-types which use that alias as the value. If the
        specified alias does not match any device-type, the dictionary contains
        an empty list for the alias key.

        {'apq8016-sbc': ['dragonboard410c']}
        {'ompa4-panda': ['panda', 'panda-es']}
        """

        aliases = DeviceType.objects.filter(
            aliases__name__contains=alias
        ).visible_by_user(self.user)
        return {alias: [device_type.name for device_type in aliases]}

    def get_device_status(self, hostname):
        """
        Name
        ----
        `get_device_status` (`hostname`)

        Description
        -----------
        Get status, running job, date from which it is offline of the given
        device and the user who put it offline.

        Arguments
        ---------
        `hostname`: string
            Name of the device for which the status is asked.

        Return value
        ------------
        This function returns an XML-RPC dictionary which contains hostname,
        status, date from which the device is offline if the device is offline,
        the user who put the device offline if the device is offline and the
        job id of the running job.
        The device has to be visible to the user who requested device's status.

        Note that offline_since and offline_by can be empty strings if the device
        status is manually changed by an administrator in the database or from
        the admin site of LAVA even if device's status is offline.
        """

        if not hostname:
            raise xmlrpc.client.Fault(400, "Bad request: Hostname was not specified.")
        try:
            device = Device.objects.get(hostname=hostname)
        except Device.DoesNotExist:
            raise xmlrpc.client.Fault(404, "Device '%s' was not found." % hostname)

        device_dict = {}
        if device.can_view(self.user):
            device_dict["hostname"] = device.hostname
            device_dict["status"] = build_device_status_display(
                device.state, device.health
            )
            device_dict["job"] = None
            device_dict["offline_since"] = None
            device_dict["offline_by"] = None
            device_dict["is_pipeline"] = True

            current_job = device.current_job()
            if current_job is not None:
                device_dict["job"] = current_job.pk
        else:
            raise xmlrpc.client.Fault(
                403, "Permission denied for user to access %s information." % hostname
            )
        return device_dict

    def put_into_maintenance_mode(self, hostname, reason, notify=None):
        """
        Name
        ----
        `put_into_maintenance_mode` (`hostname`, `reason`, `notify`)

        Description
        -----------
        Put the given device in maintenance mode with the given reason and optionally
        notify the given mail address when the job has finished.

        Arguments
        ---------
        `hostname`: string
            Name of the device to put into maintenance mode.
        `reason`: string
            The reason given to justify putting the device into maintenance mode.
        `notify`: string
            Email address of the user to notify when the job has finished. Can be
            omitted.

        Return value
        ------------
        None. The user should be authenticated with a username and token and has
        sufficient permission.
        """

        self._authenticate()
        if not hostname:
            raise xmlrpc.client.Fault(400, "Bad request: Hostname was not specified.")
        if not reason:
            raise xmlrpc.client.Fault(400, "Bad request: Reason was not specified.")
        with transaction.atomic():
            try:
                device = Device.objects.select_for_update().get(hostname=hostname)
            except Device.DoesNotExist:
                raise xmlrpc.client.Fault(404, "Device '%s' was not found." % hostname)
            if device.can_change(self.user):
                device.health = Device.HEALTH_MAINTENANCE
                device.save()
            else:
                raise xmlrpc.client.Fault(
                    403,
                    "Permission denied for user to put %s into maintenance mode."
                    % hostname,
                )

    def put_into_online_mode(self, hostname, reason, skip_health_check=False):
        """
        Name
        ----
        `put_into_online_mode` (`hostname`, `reason`, `skip_health_check`)

        Description
        -----------
        Put the given device into online mode with the given reason and skip health
        check if asked.

        Arguments
        ---------
        `hostname`: string
            Name of the device to put into online mode.
        `reason`: string
            The reason given to justify putting the device into online mode.
        `skip_health_check`: boolean
            Skip health check when putting the board into online mode. If
            omitted, health check is not skipped by default.

        Return value
        ------------
        None. The user should be authenticated with a username and token and has
        sufficient permission.
        """

        self._authenticate()
        if not hostname:
            raise xmlrpc.client.Fault(400, "Bad request: Hostname was not specified.")
        if not reason:
            raise xmlrpc.client.Fault(400, "Bad request: Reason was not specified.")
        with transaction.atomic():
            try:
                device = Device.objects.select_for_update().get(hostname=hostname)
            except Device.DoesNotExist:
                raise xmlrpc.client.Fault(404, "Device '%s' was not found." % hostname)
            if device.can_change(self.user):
                device.health = Device.HEALTH_UNKNOWN
                device.save()
            else:
                raise xmlrpc.client.Fault(
                    403,
                    "Permission denied for user to put %s into online mode." % hostname,
                )

    def pending_jobs_by_device_type(self, all=False):
        """
        Name
        ----
        `pending_jobs_by_device_type` ()

        Description
        -----------
        Get number of pending jobs in each device type.
        Private test jobs and hidden device types are
        excluded, except for authenticated superusers.

        Arguments
        ---------
        `all`: boolean - include retired devices and undisplayed device-types in the
                         listing.

        Return value
        ------------
        This function returns a dict where the key is the device type and
        the value is the number of jobs pending in that device type.
        For example:

        {'qemu': 0, 'panda': 3}
        """

        pending_jobs_by_device = {}

        jobs_res = TestJob.objects.filter(
            state=TestJob.STATE_SUBMITTED
        ).visible_by_user(self.user)
        jobs_res = jobs_res.exclude(requested_device_type_id__isnull=True)
        jobs_res = jobs_res.values_list("requested_device_type_id")
        jobs_res = jobs_res.annotate(pending_jobs=(Count("id")))

        jobs = {}
        jobs_hash = dict(jobs_res)
        for job in jobs_hash:
            jobs[job] = jobs_hash[job]
        pending_jobs_by_device.update(jobs)

        # Get rest of the devices and put number of pending jobs as 0.
        if all:
            device_types = DeviceType.objects.all()
        else:
            device_types = active_device_types()

        device_types = device_types.visible_by_user(self.user)
        for device_type in device_types.values_list("name", flat=True):
            if device_type not in pending_jobs_by_device:
                pending_jobs_by_device[device_type] = 0

        return pending_jobs_by_device

    def job_details(self, job_id):
        """
        Name
        ----
        `job_details` (`job_id`)

        Description
        -----------
        Get the details of given job id.

        Arguments
        ---------
        `job_id`: string
            Job id for which the output is required.

        Return value
        ------------
        This function returns an XML-RPC structures of job details, provided
        the user is authenticated with an username and token.

        The elements available in XML-RPC structure include:
        _state, submitter_id, is_pipeline, id, failure_comment,
        multinode_definition, priority, _actual_device_cache,
        original_definition, status, health_check, description,
        start_time, target_group, pipeline_compatibility, submit_time,
        is_public, _old_status, actual_device_id, definition, sub_id,
        requested_device_type_id, end_time, absolute_url, submitter_username
        """
        try:
            job = TestJob.get_by_job_number(job_id)
        except TestJob.DoesNotExist:
            raise xmlrpc.client.Fault(404, "Job '%s' was not found." % job_id)

        if not job.can_view(self.user):
            raise xmlrpc.client.Fault(
                403, "Job '%s' not available to user '%s'." % (job_id, self.user)
            )

        metadata = None
        try:
            job_case = TestCase.objects.get(
                suite__job=job, suite__name="lava", name="job"
            )
        except TestCase.DoesNotExist:
            job_case = None
        if job_case:
            metadata = job_case.action_metadata
        if not metadata:
            # if job_case exists but metadata is still None due to job error
            metadata = {}

        job.error_msg = metadata.get("error_msg")
        job.error_type = metadata.get("error_type")
        job.status = job.get_legacy_status_display()
        job.state = job.get_state_display()
        job.health = job.get_health_display()
        job.submitter_username = job.submitter.username
        job.absolute_url = job.get_absolute_url()
        job.is_pipeline = True

        return job

    def job_health(self, job_id):
        """
        Name
        ----
        `job_health` (`job_id`)

        Description
        -----------
        Get the health of given job id.

        Arguments
        ---------
        `job_id`: string
            Job id for which the output is required.

        Return value
        ------------
        This function returns an XML-RPC structures of job health with the
        following fields.
        The user is authenticated with an username and token.

        `job_health`: string
        ['Unknown'|'Complete'|'Incomplete'|'Canceled']
        """
        try:
            job = TestJob.get_by_job_number(job_id)
        except TestJob.DoesNotExist:
            raise xmlrpc.client.Fault(404, "Job '%s' was not found." % job_id)

        if not job.can_view(self.user):
            raise xmlrpc.client.Fault(
                403, "Job '%s' not available to user '%s'." % (job_id, self.user)
            )

        job_health = {"job_id": job.id, "job_health": job.get_health_display()}

        if job.is_multinode:
            job_health.update({"sub_id": job.sub_id})

        return job_health

    def job_state(self, job_id):
        """
        Name
        ----
        `job_state` (`job_id`)

        Description
        -----------
        Get the state of given job id.

        Arguments
        ---------
        `job_id`: string
            Job id for which the output is required.

        Return value
        ------------
        This function returns an XML-RPC structures of job state with the
        following fields.
        The user is authenticated with an username and token.

        `job_state`: string
        ['Submitted'|'Scheduling'|'Scheduled'|'Running'|'Canceling'|'Finished']
        """
        try:
            job = TestJob.get_by_job_number(job_id)
        except TestJob.DoesNotExist:
            raise xmlrpc.client.Fault(404, "Job '%s' was not found." % job_id)

        if not job.can_view(self.user):
            raise xmlrpc.client.Fault(
                403, "Job '%s' not available to user '%s'." % (job_id, self.user)
            )

        job_state = {"job_id": job.id, "job_state": job.get_state_display()}

        if job.is_multinode:
            job_state.update({"sub_id": job.sub_id})

        return job_state

    def all_jobs(self):
        """
        Name
        ----
        `all_jobs` ()

        Description
        -----------
        Get submitted or running jobs.

        Arguments
        ---------
        None

        Return value
        ------------
        This function returns a XML-RPC array of submitted and running jobs with their
        status and actual device for running jobs and requested device or device type
        for submitted jobs and job sub_id for multinode jobs.
        For example:

        [[73, 'multinode-job', 'submitted', None, 'kvm', '72.1'],
        [72, 'multinode-job', 'submitted', None, 'kvm', '72.0'],
        [71, 'test-job', 'running', 'kvm01', None, None]]
        """

        jobs = (
            TestJob.objects.exclude(state=TestJob.STATE_FINISHED)
            .visible_by_user(self.user)
            .order_by("-id")
        )
        jobs_list = [
            [
                job.id,
                job.description,
                job.get_legacy_status_display().lower(),
                job.actual_device,
                job.requested_device_type,
                job.sub_id,
            ]
            for job in jobs
        ]

        return jobs_list

    def get_device_config(self, device_hostname, context=None):
        """
        New in api_version 2 - see system.api_version()

        Name
        ----
        `get_device_config` (`device_hostname`, context=None)

        Description
        -----------
        Get the device configuration for given device hostname.

        Arguments
        ---------
        `device_hostname`: string
            Device hostname for which the configuration is required.

        Some device templates need a context specified when processing the
        device-type template. This can be specified as a YAML string:

        `get_device_config` `('qemu01', '{arch: amd64}')`

        Return value
        ------------
        This function returns an XML-RPC binary data of output file.
        """
        if not device_hostname:
            raise xmlrpc.client.Fault(
                400, "Bad request: Device hostname was not specified."
            )

        job_ctx = None
        if context is not None:
            try:
                job_ctx = yaml_safe_load(context)
            except yaml.YAMLError as exc:
                raise xmlrpc.client.Fault(
                    400, "Job context '%s' is not valid. %s" % (context, exc)
                )
        try:
            device = Device.objects.get(hostname=device_hostname)
        except Device.DoesNotExist:
            raise xmlrpc.client.Fault(404, "Specified device was not found.")

        if not device.can_view(self.user):
            raise xmlrpc.client.Fault(
                401, "Permission denied for user to device %s" % device.hostname
            )

        config = device.load_configuration(job_ctx=job_ctx, output_format="yaml")

        # validate against the device schema
        validate_device(yaml_safe_load(config))

        return xmlrpc.client.Binary(config.encode("UTF-8"))

    def import_device_dictionary(self, hostname, jinja_str):
        """
        Name
        ----
        `import_device_dictionary` (`device_hostname`, `jinja_string`)

        Description
        -----------
        [user with change_device permission only]
        Import or update the device dictionary key value store for a
        pipeline device.

        Arguments
        ---------
        `device_hostname`: string
            Device hostname to update.
        `jinja_str`: string
            Device configuration as Jinja2

        Return value
        ------------
        This function returns an XML-RPC binary data of output file.
        """
        self._authenticate()
        try:
            device = Device.objects.get(hostname=hostname)
        except DeviceType.DoesNotExist:
            raise xmlrpc.client.Fault(404, "Device '%s' was not found." % hostname)
        if device.can_change(self.user):
            if not device.save_configuration(jinja_str):
                raise xmlrpc.client.Fault(
                    400, "Unable to store the configuration for %s on disk" % hostname
                )
        else:
            raise xmlrpc.client.Fault(
                403,
                "Permission denied for user to store the configuration for %s on disk."
                % hostname,
            )

        return "Device dictionary updated for %s" % hostname

    def export_device_dictionary(self, hostname):
        """
        Name
        ----
        `export_device_dictionary` (`device_hostname`)

        Description
        -----------
        [user with admin permission only]
        Export the device dictionary key value store for a
        pipeline device.

        See also get_pipeline_device_config

        Arguments
        ---------
        `device_hostname`: string
            Device hostname to update.

        Return value
        ------------
        This function returns an XML-RPC binary data of output file.
        """
        self._authenticate()
        try:
            device = Device.objects.get(hostname=hostname)
        except DeviceType.DoesNotExist:
            raise xmlrpc.client.Fault(404, "Device '%s' was not found." % hostname)
        if device.can_change(self.user):
            device_dict = device.load_configuration(output_format="raw")
            if not device_dict:
                raise xmlrpc.client.Fault(
                    404, "Device '%s' does not have a device dictionary" % hostname
                )
        else:
            raise xmlrpc.client.Fault(
                403,
                "Permission denied for user to retrieve device dictionary for '%s'."
                % hostname,
            )

        return xmlrpc.client.Binary(device_dict.encode("UTF-8"))

    def validate_pipeline_devices(self, name=None):
        """
        Name
        ----
        `validate_pipeline_device` [`name`]

        Description
        -----------
        Validate that the device dictionary and device-type template
        together create a valid YAML file which matches the pipeline
        device schema.
        Retired devices are ignored.

        See also get_pipeline_device_config

        Arguments
        ---------
        `name`: string
            Can be device hostname or device type name.
        If name is specified, method will search for either a matching device
        hostname or matching device type name in which case it will only
        validate that(those) device(s).
        If not specified, this method will validate all non-retired devices
        in the system.

        Return value
        ------------
        This function returns an XML-RPC structure of results with the
        following fields.

        `device_hostname`: {'Valid': null}
        or
        `device_hostname`: {'Invalid': message}
        `

        """
        if not name:
            devices = Device.objects.exclude(health=Device.HEALTH_RETIRED)
        else:
            devices = Device.objects.exclude(health=Device.HEALTH_RETIRED).filter(
                device_type__name=name
            )
            if not devices:
                devices = Device.objects.exclude(health=Device.HEALTH_RETIRED).filter(
                    hostname=name
                )

        devices = devices.visible_by_user(self.user)

        if not devices and name:
            raise xmlrpc.client.Fault(
                404,
                (
                    "No devices found with hostname or device type name %s, "
                    "visible by the user"
                )
                % name,
            )
        if not devices and not name:
            raise xmlrpc.client.Fault(
                404, "No pipeline devices visible by user were found on this instance."
            )
        results = {}
        for device in devices:
            key = str(device.hostname)
            config = device.load_configuration(output_format="yaml")
            if config is None:
                results[key] = {"Invalid": "Missing device dictionary"}
                continue
            try:
                # validate against the device schema
                validate_device(yaml_safe_load(config))
            except SubmissionException as exc:
                results[key] = {"Invalid": exc}
                continue
            results[key] = {"Valid": None}
        return xmlrpc.client.Binary(yaml_safe_dump(results).encode("UTF-8"))

    def get_publisher_event_socket(self):
        """
        Name
        ----
        `get_publisher_event_socket`

        Return value
        ------------
        This function exposes the EVENT_SOCKET from the settings file which is
        used for the lava-publisher daemon.
        """
        return settings.EVENT_SOCKET
