# Copyright (C) 2015 Linaro Limited
#
# Author: Stevan Radakovic <stevan.radakovic@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later


from django.db import models


class MaterializedViewManager(models.Manager):
    """Custom Manager for materialized views.

    Inherits the django Manager class and prevents users from doing view
    create, update and delete calls.
    """

    def bulk_create(self, *args, **kwargs):
        raise NotImplementedError

    def create(self, *args, **kwargs):
        raise NotImplementedError

    def get_or_create(self, *args, **kwargs):
        raise NotImplementedError

    def delete(self, *args, **kwargs):
        raise NotImplementedError

    def update(self, *args, **kwargs):
        raise NotImplementedError


class MaterializedView(models.Model):
    """Materialized view model."""

    objects = MaterializedViewManager()

    class Meta:
        abstract = True
        managed = False

    def delete(self, *args, **kwargs):
        raise NotImplementedError

    def save(self, *args, **kwargs):
        raise NotImplementedError
