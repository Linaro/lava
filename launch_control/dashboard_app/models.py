"""
Database models of the Dashboard application
"""

from django.db import models
from django.utils.translation import ugettext as _
from django.utils.translation import ungettext


def _help_max_length(max_length):
    return ungettext(
            u"Maximum length: {0} character",
            u"Maximum length: {0} characters",
            max_length).format(max_length)


class SoftwarePackage(models.Model):
    """
    Model for software packages.

    This class mirrors launch_control.models.SoftwarePackage.
    """
    name = models.CharField(
            max_length = 64,
            verbose_name = _(u"Package name"),
            help_text = _help_max_length(64))

    version = models.CharField(
            max_length = 32,
            verbose_name = _(u"Package version"),
            help_text = _help_max_length(32))

    def __unicode__(self):
        return _(u"{name} {version}").format(
                name = self.name,
                version = self.version)

    class Meta:
        unique_together = (('name', 'version'))
