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


class TestManager(models.Manager):

    def get_or_create(self, **kwargs):
        """
        Override get_or_create to auto-generate default name if test_id
        is provided.
        """
        defaults = kwargs.get('defaults', {})
        if 'name' not in defaults and 'test_id' in kwargs:
            defaults['name'] = "Automatically created Test based on ID {0}".format(
                kwargs['test_id'])
        kwargs['defaults'] = defaults
        return super(TestManager, self).get_or_create(**kwargs)

