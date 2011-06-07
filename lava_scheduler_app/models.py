from django.db import models

from linaro_django_xmlrpc.models import ExposedAPI

# Create your models here.

class SchedulerAPI(ExposedAPI):

    def submit_job(self, job_data):
        pass
