from django.db import models

from linaro_django_xmlrpc.models import ExposedAPI


class Message(models.Model):

    text = models.TextField()


class DemoAPI(ExposedAPI):

    def demoMethod(self):
        """
        This is a demo method.
        """
        return 42
