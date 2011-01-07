# Copyright (C) 2010 Linaro Limited
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
#
# This file is part of Launch Control.
#
# Launch Control is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# Launch Control is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Launch Control.  If not, see <http://www.gnu.org/licenses/>.

from django.contrib.auth.models import (User, Group)
from django.db import models
from django.db.models import Q
from django_restricted_resource.managers import RestrictedResourceManager


class BundleStreamManager(RestrictedResourceManager):
    """
    Model manager for BundleStream that has additional methods
    """

    def allowed_for_user(self, user):
        """
        Return a QuerySet of BundleStream instances that can be accessed
        by specified user. The user may be None, AnonymousUser() or a
        User() instance.
        """
        return super(BundleStreamManager, self).accessible_by_principal(user)

    def allowed_for_anyone(self):
        """
        Return a QuerySet of BundleStream instances that can be accessed
        by anyone.
        """
        return super(BundleStreamManager, self).accessible_by_anyone()
