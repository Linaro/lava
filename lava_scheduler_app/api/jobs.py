# Copyright (C) 2017-2018 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import os
import xmlrpc.client
from datetime import timedelta

import voluptuous
from django.conf import settings
from django.utils import timezone

from lava_common import schemas
from lava_common.yaml import yaml_safe_load
from lava_results_app.models import TestCase
from lava_scheduler_app.api import SchedulerAPI
from lava_scheduler_app.logutils import logs_instance
from lava_scheduler_app.models import TestJob
from linaro_django_xmlrpc.models import ExposedV2API


def load_optional_file(filename):
    try:
        with open(filename) as f_in:
            return f_in.read().encode("utf-8")
    except OSError:
        return None


class SchedulerJobsAPI(ExposedV2API):
    def cancel(self, job_id):
        """
        Name
        ----
        `scheduler.jobs.cancel` (`job_id`)

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
        cls = SchedulerAPI(self._context)
        return cls.cancel_job(job_id)

    def configuration(self, job_id):
        """
        Name
        ----
        `scheduler.jobs.configuration` (`job_id`)

        Description
        -----------
        Return the full job configuration

        Arguments
        ---------
        `job_id`: string
            Job id

        Return value
        ------------
        Return an array with [job, device, dispatcher, env, env-dut] config.
        Any of these values might be None if the corresponding file hasn't
        been used by the job.
        If the job hasn't started yet, a 404 error will be returned.
        """
        try:
            job = TestJob.get_by_job_number(job_id)
        except TestJob.DoesNotExist:
            raise xmlrpc.client.Fault(404, "Job '%s' was not found." % job_id)

        if not job.can_view(self.user):
            raise xmlrpc.client.Fault(
                403, "Job '%s' not available to user '%s'." % (job_id, self.user)
            )

        if job.state not in [
            TestJob.STATE_RUNNING,
            TestJob.STATE_CANCELING,
            TestJob.STATE_FINISHED,
        ]:
            raise xmlrpc.client.Fault(404, "Job '%s' has not started yet" % job_id)

        output_dir = job.output_dir
        definition = load_optional_file(os.path.join(output_dir, "job.yaml"))
        device = load_optional_file(os.path.join(output_dir, "device.yaml"))
        dispatcher = load_optional_file(os.path.join(output_dir, "dispatcher.yaml"))
        env = load_optional_file(os.path.join(output_dir, "env.yaml"))
        env_dut = load_optional_file(os.path.join(output_dir, "env-dut.yaml"))
        return [definition, device, dispatcher, env, env_dut]

    def definition(self, job_id):
        """
        Name
        ----
        `scheduler.jobs.definition` (`job_id`)

        Description
        -----------
        Return the job definition

        Arguments
        ---------
        `job_id`: string
            Job id

        Return value
        ------------
        The job definition or and error.

        Note: for MultiNode jobs, the original MultiNode definition
        is returned.
        """
        try:
            job = TestJob.get_by_job_number(job_id)
        except TestJob.DoesNotExist:
            raise xmlrpc.client.Fault(404, "Job '%s' was not found." % job_id)

        if not job.can_view(self.user):
            raise xmlrpc.client.Fault(
                403, "Job '%s' not available to user '%s'." % (job_id, self.user)
            )

        if job.is_multinode:
            return job.multinode_definition
        return job.original_definition

    def list(self, state=None, health=None, start=0, limit=25, since=0, verbose=False):
        """
        Name
        ----
        `scheduler.jobs.list` (
            `state=None`, `health=None`, `start=0`, `limit=25`,
            `since=None`, `verbose=False`
        )

        Description
        -----------
        List the last jobs, within the specified range, in descending order of
        job ID. Jobs can be filtered by `state` and `health` (if provided).

        Arguments
        ---------
        `state`: str
          Filter by state, None by default (no filtering).
          Values: [SUBMITTED, SCHEDULING, SCHEDULED, RUNNING, CANCELING, FINISHED]
        `health`: str
          Filter by health, None by default (no filtering).
          Values: [UNKNOWN, COMPLETE, INCOMPLETE, CANCELED]
        `start`: int
          Skip the first N job(s) in the list
        `limit`: int
          Max number of jobs to return.
          This value will be clamped to 100
        `since`: int (minutes)
          Filter by jobs which completed in the last N minutes.
        `verbose`: bool
          Add extra data including actual_device, start_time, end_time,
          error_msg and error_type.
          Note: error_msg can contain nested quotes and other escape
          characters, parse with care.

        Return value
        ------------
        This function returns an array of jobs with keys:
            "id", "description", "device_type", "health",
            "state", "submitter"
        If verbose is True, these keys are added:
            "actual_device", "start_time", "end_time",
            "error_msg", "error_type"
        """
        ret = []
        start = max(0, start)
        limit = min(limit, 100)
        jobs = TestJob.objects.visible_by_user(self.user).select_related(
            "requested_device_type", "submitter"
        )
        if state:
            try:
                jobs = jobs.filter(state=TestJob.STATE_REVERSE[state.capitalize()])
            except (AttributeError, KeyError):
                raise xmlrpc.client.Fault(400, "Invalid state '%s'" % state)
        if health:
            try:
                jobs = jobs.filter(health=TestJob.HEALTH_REVERSE[health.capitalize()])
            except (AttributeError, KeyError):
                raise xmlrpc.client.Fault(400, "Invalid health '%s'" % health)

        # since
        if since:
            end_time = timezone.now()
            # search back in time
            start_time = end_time - timedelta(minutes=since)
            jobs = jobs.filter(end_time__range=[start_time, end_time])

        for job in jobs.order_by("-id")[start : start + limit]:
            device_type = None
            if job.requested_device_type is not None:
                device_type = job.requested_device_type.name
            data = {
                "id": job.display_id,
                "description": job.description,
                "device_type": device_type,
                "health": job.get_health_display(),
                "state": job.get_state_display(),
                "submitter": job.submitter.username,
            }
            if verbose:
                actual_device = None
                # Neither dynamic connections
                # nor jobs cancelled in submitted state
                # will have an actual_device
                if job.actual_device:
                    actual_device = job.actual_device.hostname
                # cancelled jobs might not have start or end time
                end_time = str(job.end_time) if job.end_time else None
                start_time = str(job.start_time) if job.start_time else None
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
                data.update(
                    {
                        "actual_device": actual_device,
                        "start_time": start_time,
                        "end_time": end_time,
                        "error_msg": metadata.get("error_msg"),
                        "error_type": metadata.get("error_type"),
                    }
                )

            ret.append(data)

        return ret

    def queue(self, device_types=None, start=0, limit=25):
        """
        Name
        ----
        `scheduler.jobs.queue` (`device_types=None`, `start=0`, `limit=25`)

        Description
        -----------
        List the queued jobs (state.SUBMITTED), within the specified range,
        in descending order of job ID.
        Jobs can be filtered by `requested_device_type` (if provided).

        Arguments
        ---------
        `device_types`: Array of str
          If provided, list jobs whose requested_device_type match any of the
          provided device-types. None by default (no filtering).
        `start`: int
          Skip the first N job(s) in the list
        `limit`: int
          Max number of jobs to return.
          This value will be clamped to 100

        Return value
        ------------
        This function returns an array of jobs with keys:
            "id", "description", "requested_device_type", "submitter"

        If no queued test jobs exist to match the criteria, an empty array
        is returned.
        """
        ret = []
        start = max(0, start)
        limit = min(limit, 100)
        jobs = (
            TestJob.objects.filter(state=TestJob.STATE_SUBMITTED)
            .visible_by_user(self.user)
            .select_related("requested_device_type", "submitter")
        )
        if device_types is not None:
            jobs = jobs.filter(requested_device_type__name__in=device_types)

        for job in jobs.order_by("-id")[start : start + limit]:
            data = {
                "id": job.display_id,
                "description": job.description,
                "requested_device_type": job.requested_device_type.name,
                "submitter": job.submitter.username,
            }
            ret.append(data)

        return ret

    def logs(self, job_id, start=0, end=None):
        """
        Name
        ----
        `scheduler.jobs.logs` (`job_id`, `start=0`, `end=None`)

        Description
        -----------
        Return the logs for the given job

        Arguments
        ---------
        `job_id`: str
          Job id
        `start`: int
          Show only after the given line
        `end`: int
          Do not return after the fiven line

        Return value
        ------------
        This function returns a tuple made of (job_finished, data).
        job_finished is True if and only if the job is finished.
        """
        try:
            job = TestJob.get_by_job_number(job_id)
        except TestJob.DoesNotExist:
            raise xmlrpc.client.Fault(404, "Job '%s' was not found." % job_id)

        if not job.can_view(self.user):
            raise xmlrpc.client.Fault(
                403, "Job '%s' not available to user '%s'." % (job_id, self.user)
            )

        job_finished = job.state == TestJob.STATE_FINISHED

        try:
            data = logs_instance.read(job, start, end)
            return (job_finished, xmlrpc.client.Binary(data.encode("utf-8")))
        except OSError:
            return (job_finished, xmlrpc.client.Binary(b"[]"))

    def show(self, job_id):
        """
        Name
        ----
        `scheduler.jobs.show` (`job_id`)

        Description
        -----------
        Show job details

        Arguments
        ---------
        `job_id`: string
          Job id

        Return value
        ------------
        This function returns a dictionary of details abou the specified test job.
        """
        try:
            job = TestJob.get_by_job_number(job_id)
        except TestJob.DoesNotExist:
            raise xmlrpc.client.Fault(404, "Job '%s' was not found." % job_id)

        if not job.can_view(self.user):
            raise xmlrpc.client.Fault(
                403, "Job '%s' not available to user '%s'." % (job_id, self.user)
            )

        device_hostname = None
        if job.actual_device is not None:
            device_hostname = job.actual_device.hostname

        device_type = None
        if job.requested_device_type is not None:
            device_type = job.requested_device_type.name
        if job.is_public:
            visibility = "Public"
        elif job.viewing_groups.count() == 0:
            visibility = "Personal"
        else:
            visibility = "Group (%s)" % ", ".join(
                [g.name for g in job.viewing_groups.all()]
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

        return {
            "id": job.display_id,
            "description": job.description,
            "device": device_hostname,
            "device_type": device_type,
            "health_check": job.health_check,
            "pipeline": True,
            "health": job.get_health_display(),
            "state": job.get_state_display(),
            "submitter": job.submitter.username,
            "submit_time": job.submit_time,
            "start_time": job.start_time,
            "end_time": job.end_time,
            "tags": [t.name for t in job.tags.all()],
            "visibility": visibility,
            "failure_comment": job.failure_comment,
            "error_msg": metadata.get("error_msg"),
            "error_type": metadata.get("error_type"),
        }

    def resubmit(self, job_id):
        """
        Name
        ----
        `scheduler.jobs.resubmit` (`job_id`)

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
        job's id, provided the user is authenticated with an username and token.
        """
        cls = SchedulerAPI(self._context)
        return cls.resubmit_job(job_id)

    def submit(self, definition):
        """
        Name
        ----
        `scheduler.jobs.submit` (`definition`)

        Description
        -----------
        Submit the given job data which is in LAVA job JSON or YAML format as a
        new job to LAVA scheduler.

        Arguments
        ---------
        `definition`: string
            Job JSON or YAML string.

        Return value
        ------------
        This function returns an XML-RPC integer which is the newly created
        job's id, provided the user is authenticated with an username and token.
        If the job is a multinode job, this function returns the list of created
        job IDs.
        """
        cls = SchedulerAPI(self._context)
        return cls.submit_job(definition)

    def validate(self, definition, strict=False):
        """
        Name
        ----
        `scheduler.jobs.validate` (`definition`, `strict=False`)

        Description
        -----------
        Validate the given job definition against the schema validator.

        Arguments
        ---------
        `definition`: string
            Job YAML string.
        `strict`: boolean
            If set to True, the validator will reject any extra keys that are
            present in the job definition but not defined in the schema.

        Return value
        ------------
        This function returns None if the job definition is valid. Returns a
        dictionary in case of error with the key and msg.
        """
        data = yaml_safe_load(definition)
        try:
            schemas.validate(
                data,
                strict=strict,
                extra_context_variables=settings.EXTRA_CONTEXT_VARIABLES,
            )
            return {}
        except voluptuous.Invalid as exc:
            return {"path": str(exc.path), "msg": exc.msg}
