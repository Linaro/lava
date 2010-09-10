from django.contrib.auth.models import (User, Group)
from django.db import models
from django.db.models import Q


class BundleStreamManager(models.Manager):
    """
    Model manager for BundleStream that has additional methods
    """

    def allowed_for_user(self, user):
        """
        Return a QuerySet of BundleStream instances that can be accessed
        by specified user. The user may be None, AnonymousUser() or a
        User() instance.
        """
        if user is None or not user.is_authenticated() or not user.is_active:
            return self.allowed_for_anyone()
        else:
            return self.filter(
                Q(user__isnull = True, group__isnull = True) |
                Q(user = user) |
                Q(group__in = user.groups.all()))

    def allowed_for_anyone(self):
        """
        Return a QuerySet of BundleStream instances that can be accessed
        by anyone.
        """
        return self.filter(user__isnull = True, group__isnull = True)
