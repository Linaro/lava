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

from django.core.urlresolvers import reverse
import logging


class BreadCrumb(object):

    def __init__(self, name, parent=None, needs=None):
        self.name = name
        self.view = None
        self.parent = parent
        self.needs = needs or []

    def __repr__(self):
        return "<BreadCrumb name=%r view=%r parent=%r>" % (
            self.name, self.view, self.parent)

    def __call__(self, view):
        self.view = view
        view._bread_crumb = self
        return view

    def get_name(self, kwargs):
        try:
            return self.name.format(**kwargs)
        except:
            logging.exception("Unable to construct breadcrumb name for view %r", self.view)
            raise

    def get_absolute_url(self, kwargs):
        try:
            return reverse(self.view, args=[kwargs[name] for name in self.needs])
        except:
            logging.exception("Unable to construct breadcrumb URL for view %r", self.view)
            raise


class LiveBreadCrumb(object):

    def __init__(self, bread_crumb, kwargs):
        self.bread_crumb = bread_crumb
        self.kwargs = kwargs

    def get_name(self):
        return self.bread_crumb.get_name(self.kwargs)

    def get_absolute_url(self):
        return self.bread_crumb.get_absolute_url(self.kwargs)


class BreadCrumbTrail(object):

    def __init__(self, bread_crumb_list, kwargs):
        self.bread_crumb_list = bread_crumb_list
        self.kwargs = kwargs

    def __iter__(self):
        for bread_crumb in self.bread_crumb_list:
            yield LiveBreadCrumb(bread_crumb, self.kwargs)

    @classmethod
    def leading_to(cls, view, **kwargs):
        lst = []
        while view is not None:
            lst.append(view._bread_crumb)
            view = view._bread_crumb.parent
        lst.reverse()
        return cls(lst, kwargs or {})

