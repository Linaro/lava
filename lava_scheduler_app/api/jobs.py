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
import xmlrpclib

from linaro_django_xmlrpc.models import ExposedAPI
from lava_scheduler_app.api import SchedulerAPI
from lava_scheduler_app.models import TestJob


class SchedulerJobsAPI(ExposedAPI):

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
        """
        try:
            job = TestJob.get_by_job_number(job_id)
        except TestJob.DoesNotExist:
            raise xmlrpclib.Fault(
                404, "Job '%s' was not found." % job_id)

        if not job.can_view(self.user):
            raise xmlrpclib.Fault(
                403, "Job '%s' not available to user '%s'." %
                (job_id, self.user))

        if job.is_multinode:
            return xmlrpclib.Binary(job.multinode_definition)
        else:
            return xmlrpclib.Binary(job.original_definition)

    def list(self, limit=25):
        """
        Name
        ----
        `scheduler.jobs.list` (`limit=25`)

        Description
        -----------
        List the last jobs according to the criteria

        Arguments
        ---------
        `limit`: int
          Max number of jobs to return

        Return value
        ------------
        This function returns an array of jobs
        """
        ret = []
        for job in TestJob.objects.all().order_by('-id')[:limit]:
            device_type = None
            if job.requested_device_type is not None:
                device_type = job.requested_device_type.name
            ret.append({"id": job.display_id,
                        "description": job.description,
                        "device_type": device_type,
                        "status": job.get_status_display(),
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
            raise xmlrpclib.Fault(
                404, "Job '%s' was not found." % job_id)

        if not job.can_view(self.user):
            raise xmlrpclib.Fault(
                403, "Job '%s' not available to user '%s'." %
                (job_id, self.user))

        job_finished = job.status not in [TestJob.SUBMITTED, TestJob.RUNNING, TestJob.CANCELING]

        try:
            with open(os.path.join(job.output_dir, "output.yaml"), "r") as f_in:
                count = 0
                for _ in range(line):
                    count += len(f_in.next())
                f_in.seek(count)
                return (job_finished, xmlrpclib.Binary(f_in.read().encode("utf-8")))
        except (IOError, StopIteration):
            return (job_finished, xmlrpclib.Binary("[]".encode("utf-8")))

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
            raise xmlrpclib.Fault(
                404, "Job '%s' was not found." % job_id)

        if not job.can_view(self.user):
            raise xmlrpclib.Fault(
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
                "pipeline": job.is_pipeline,
                "status": job.get_status_display(),
                "submitter": job.submitter.username,
                "submit_time": job.submit_time,
                "start_time": job.start_time,
                "end_time": job.end_time,
                "tags": [t.name for t in job.tags.all()],
                "visibility": job.get_visibility_display(),
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
        """
        cls = SchedulerAPI(self._context)
        return cls.submit_job(definition)
