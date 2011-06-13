import xmlrpclib

from linaro_django_xmlrpc.models import ExposedAPI

class SchedulerAPI(ExposedAPI):

    def submit_job(self, job_data):
        if not self.user:
            raise xmlrpclib.Fault(1, "")
