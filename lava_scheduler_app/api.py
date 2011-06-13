import xmlrpclib

from linaro_django_xmlrpc.models import ExposedAPI

from lava_scheduler_app.models import TestJob


class SchedulerAPI(ExposedAPI):

    def submit_job(self, job_data):
        if not self.user:
            raise xmlrpclib.Fault(401, "Authentication required.")
        if not self.user.has_perm('lava_scheduler_app.add_testjob'):
            raise xmlrpclib.Fault(403, "Permission denied.")
        return TestJob.from_json_and_user(job_data, self.user).id
