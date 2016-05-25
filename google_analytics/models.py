from django.contrib.sites.models import Site
from django.db import models


class Analytic(models.Model):
    site = models.OneToOneField(Site)
    analytics_code = models.CharField(blank=True, max_length=100)
