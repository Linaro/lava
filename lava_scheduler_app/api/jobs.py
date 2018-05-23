# Copyright (C) 2017 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# This file is part of Lava Server.
#
# Lava Server is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# Lava Server is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Lava Server.  If not, see <http://www.gnu.org/licenses/>.

import os
import xmlrpc.client
from linaro_django_xmlrpc.models import ExposedV2API
from lava_scheduler_app.api import SchedulerAPI
from lava_scheduler_app.models import TestJob


def load_optional_file(filename):
    try:
        with open(filename, "r") as f_in:
            return f_in.read().encode("utf-8")
    except IOError:
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
        Any of theses values might be None if the corresponding file hasn't
        been used by the job.
        If the job hasn't started yet, a 404 error will be returned.
        """
        try:
            job = TestJob.get_by_job_number(job_id)
        except TestJob.DoesNotExist:
            raise xmlrpc.client.Fault(
                404, "Job '%s' was not found." % job_id)

        if not job.can_view(self.user):
            raise xmlrpc.client.Fault(
                403, "Job '%s' not available to user '%s'." %
                (job_id, self.user))

        if job.state not in [TestJob.STATE_RUNNING, TestJob.STATE_CANCELING, TestJob.STATE_FINISHED]:
            raise xmlrpc.client.Fault(
                404, "Job '%s' has not started yet" % job_id)

        output_dir = job.output_dir
        definition = load_optional_file(os.path.join(output_dir, "job.yaml"))
        device = load_optional_file(os.path.join(output_dir, "device.yaml"))
        dispatcher = load_optional_file(os.path.join(output_dir,
                                                     "dispatcher.yaml"))
        env = load_optional_file(os.path.join(output_dir, "env.yaml"))
        env_dut = load_optional_file(os.path.join(output_dir, "env.dut.yaml"))
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
            raise xmlrpc.client.Fault(
                404, "Job '%s' was not found." % job_id)

        if not job.can_view(self.user):
            raise xmlrpc.client.Fault(
                403, "Job '%s' not available to user '%s'." %
                (job_id, self.user))

        if job.is_multinode:
            return job.multinode_definition
        else:
            return job.original_definition

    def list(self, state=None, health=None, start=0, limit=25):
        """
        Name
        ----
        `scheduler.jobs.list` (`state=None`, `health=None`, `start=0`, `limit=25`)

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
          Skip the first job in the list
        `limit`: int
          Max number of jobs to return.
          This value will be clamped to 100

        Return value
        ------------
        This function returns an array of jobs
        """
        ret = []
        start = max(0, start)
        limit = min(limit, 100)
        jobs = TestJob.objects.all()
        if state is not None:
            try:
                jobs = jobs.filter(state=TestJob.STATE_REVERSE[state.capitalize()])
            except KeyError:
                raise xmlrpc.client.Fault(400, "Invalid state '%s'" % state)
        if health is not None:
            try:
                jobs = jobs.filter(health=TestJob.HEALTH_REVERSE[health.capitalize()])
            except KeyError:
                raise xmlrpc.client.Fault(400, "Invalid health '%s'" % health)

        for job in jobs.order_by('-id')[start:start + limit]:
            device_type = None
            if job.requested_device_type is not None:
                device_type = job.requested_device_type.name
            ret.append({"id": job.display_id,
                        "description": job.description,
                        "device_type": device_type,
                        "health": job.get_health_display(),
                        "state": job.get_state_display(),
                        "submitter": job.submitter.username})

        return ret

    def logs(self, job_id, line=0):
        """
        Name
        ----
        `scheduler.jobs.logs` (`job_id`, `line=0`)

        Description
        -----------
        Return the logs for the given job

        Arguments
        ---------
        `job_id`: str
          Job id
        `line`: int
          Show only after the given line

        Return value
        ------------
        This function returns a tuple made of (job_finished, data).
        job_finished is True if and only if the job is finished.
        """
        try:
            job = TestJob.get_by_job_number(job_id)
        except TestJob.DoesNotExist:
            raise xmlrpc.client.Fault(
                404, "Job '%s' was not found." % job_id)

        if not job.can_view(self.user):
            raise xmlrpc.client.Fault(
                403, "Job '%s' not available to user '%s'." %
                (job_id, self.user))

        job_finished = (job.state == TestJob.STATE_FINISHED)

        try:
            with open(os.path.join(job.output_dir, "output.yaml"), "r") as f_in:
                count = 0
                for _ in range(line):
                    count += len(next(f_in))
                f_in.seek(count)
                return (job_finished, xmlrpc.client.Binary(f_in.read().encode("utf-8")))
        except (IOError, StopIteration):
            return (job_finished, xmlrpc.client.Binary("[]".encode("utf-8")))

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
            raise xmlrpc.client.Fault(
                404, "Job '%s' was not found." % job_id)

        if not job.can_view(self.user):
            raise xmlrpc.client.Fault(
                403, "Job '%s' not available to user '%s'." %
                (job_id, self.user))

        device_hostname = None
        if job.actual_device is not None:
            device_hostname = job.actual_device.hostname

        device_type = None
        if job.requested_device_type is not None:
            device_type = job.requested_device_type.name

        return {"id": job.display_id,
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
                "visibility": job.get_visibility_display(),
                "failure_comment": job.failure_comment,
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
