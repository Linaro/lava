import xmlrpclib
from simplejson import JSONDecodeError
from linaro_django_xmlrpc.models import ExposedAPI
from django.shortcuts import get_object_or_404
from lava_scheduler_app.models import (
    Device,
    DeviceType,
    JSONDataError,
    TestJob,
    )


class SchedulerAPI(ExposedAPI):

    def submit_job(self, job_data):
        if not self.user:
            raise xmlrpclib.Fault(
                401, "Authentication with user and token required for this "
                "API.")
        if not self.user.has_perm('lava_scheduler_app.add_testjob'):
            raise xmlrpclib.Fault(
                403, "Permission denied.  User %r does not have the "
                "'lava_scheduler_app.add_testjob' permission.  Contact "
                "the administrators." % self.user.username)
        try:
            job = TestJob.from_json_and_user(job_data, self.user)
        except JSONDecodeError as e:
            raise xmlrpclib.Fault(400, "Decoding JSON failed: %s." % e)
        except (JSONDataError, ValueError) as e:
            raise xmlrpclib.Fault(400, str(e))
        except Device.DoesNotExist:
            raise xmlrpclib.Fault(404, "Specified device not found.")
        except DeviceType.DoesNotExist:
            raise xmlrpclib.Fault(404, "Specified device type not found.")
        return job.id

    def resubmit_job(self, job_id):
        try:
            job = TestJob.objects.accessible_by_principal(self.user).get(pk=job_id)
        except TestJob.DoesNotExist:
            raise xmlrpclib.Fault(404, "Specified job not found.")
        return self.submit_job(job.definition)

    def cancel_job(self, job_id):
        if not self.user:
            raise xmlrpclib.Fault(401, "Authentication required.")
        job = TestJob.objects.get(pk=job_id)
        if not job.can_cancel(self.user):
            raise xmlrpclib.Fault(403, "Permission denied.")
        job.cancel()
        return True

    def job_output(self, job_id):
        """
        Name
        ----
        `job_output` (`job_id`)

        Description
        -----------
        Get the output of given job id.

        Arguments
        ---------
        `job_id`: string
            Job id for which the output is required.

        Return value
        ------------
        This function returns an XML-RPC binary data of output file.
        """

        job = get_object_or_404(TestJob.objects, pk=job_id)
        return xmlrpclib.Binary(job.output_file().read())
