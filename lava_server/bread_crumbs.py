# Copyright (C) 2010, 2011 Linaro Limited
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
#
# This file is part of LAVA Server.
#
# LAVA Server is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# LAVA Server is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with LAVA Server.  If not, see <http://www.gnu.org/licenses/>.

"""
lava_server.bread_crumbs
========================

Bread crumb management for LAVA server.

This system allows one to construct static trees of views or even site maps,
where each view has at most one parent. In this model any view could be
followed back through the parent link to create a bread crumb trail of named
URLs.

It is important to emphasize that this system is STATIC, that is, it is not
based on browsing history. Regardless on how the user got to a particular view
the bread crumb system will report the same set of pages. The idea is not to
let users go back (that's the what the browser allows them to do) but to put
the current page into context of where it "belongs".

To use this system apply the @BreadCrumb(name, parent=parent_view,
needs=['required', 'keywords']) decorator to your view function. To render
breadcrumbs you can use the default template that is a part of
"layouts/content-bootstrap.html" template. Your context must include the
bread_crumb_trail variable. To construct it call
BreadCrumbTrail.leading_to(your_view_name, ...) passing any of  the keyword
arguments specified in needs of your and any parent views (yes this is
annoying).

A mistake in pairing 'needs' to keywords passed to BreadCrumbTrail.leading_to()
will result in logged warnings (either a name of the URL being not
constructible). To fix that simply add the missing keyword argument and reload.
"""

from django.core.urlresolvers import reverse
import logging


class BreadCrumb(object):
    """
    A crumb of bread left in the forest of pages to let you go back to (no, not
    to where you came from) where the developer desired you to go.
    """

    def __init__(self, name, parent=None, needs=None):
        """
        Construct a bread crumb object.

        The name is the essential property creating the actual text visible on
        web pages. It may be a static string or a new-style python string
        template. Parent allows one to construct a static bread crumb tree where
        each crumb may have at most one parent. Needs, if specified, must be
        an array of strings that denote identifiers required to resolve the URL
        of this bread crumb. The identifiers are obtained from the call
        BreadCrumbTrail.leading_to().
        """
        self.name = name
        self.view = None
        self.parent = parent
        self.needs = needs or []

    def __repr__(self):
        return "<BreadCrumb name=%r view=%r parent=%r>" % (
            self.name, self.view, self.parent)

    def __call__(self, view):
        """
        Call method, used when decorating function-based views

        Id does not redefine the function (so is not a real decorator) but
        instead stores the bread crumb object in the _bread_crumb attribute of
        the function.
        """
        self.view = view
        view._bread_crumb = self
        return view

    def get_name(self, kwargs):
        """
        Get the name of this crumb.

        The name is formatted with the specified keyword arguments.
        """
        try:
            return self.name.format(**kwargs)
        except:
            logging.exception(
                "Unable to construct breadcrumb name for view %r", self.view)
            raise

    def get_absolute_url(self, kwargs):
        """
        Get the URL of this crumb.

        The URL is constructed with a call to Dajngo's reverse() function. It
        is supplemented with the same variables that were listed in needs array
        in the bread crumb constructor. The arguments are passed in order, from
        the kwargs dictionary.
        """
        try:
            return reverse(
                self.view,
                args=[kwargs[name] for name in self.needs])
        except:
            logging.exception(
                "Unable to construct breadcrumb URL for view %r", self.view)
            raise


class LiveBreadCrumb(object):
    """
    Bread crumb instance as observed by a particular request.

    It is a binding between the global view-specific bread crumb object and
    dynamic request-specific keyword arguments.

    For convenience it provides two bread crumb functions (get_name() and
    get_absolute_url()) that automatically provide the correct keyword
    arguments.
    """

    def __init__(self, bread_crumb, kwargs):
        self.bread_crumb = bread_crumb
        self.kwargs = kwargs

    def __unicode__(self):
        return self.get_name()

    def get_name(self):
        return self.bread_crumb.get_name(self.kwargs)

    def get_absolute_url(self):
        return self.bread_crumb.get_absolute_url(self.kwargs)


class BreadCrumbTrail(object):
    """
    A list of live bread crumbs that lead from a particular view, along the
    parent chain, all the way to the root view (that is without any parent
    view).
    """

    def __init__(self, bread_crumb_list, kwargs):
        self.bread_crumb_list = bread_crumb_list
        self.kwargs = kwargs

    def __iter__(self):
        for bread_crumb in self.bread_crumb_list:
            yield LiveBreadCrumb(bread_crumb, self.kwargs)

    @classmethod
    def leading_to(cls, view, **kwargs):
        """
        Create an instance of BreadCrumbTrail that starts at the specified
        view.

        Additional keyword arguments, if provided, will be available to
        get_name() and get_absolute_url() of each LiveBreadCrumb that makes up
        this trail. In practice they should contain a set of arguments that are
        needed by any parent bread crumb URL or name.

        TODO: could we check this statically somehow?
        """
        lst = []
        while view is not None:
            lst.append(view._bread_crumb)
            view = view._bread_crumb.parent
        lst.reverse()
        return cls(lst, kwargs or {})

    @classmethod
    def show_help(cls, view, **kwargs):
        """
        Create a context-sensitive help string from this crumb.

        The URL is constructed with a call to Dajngo's reverse() function. It
        is supplemented with the same variables that were listed in needs array
        in the bread crumb constructor. The arguments are passed in order, from
        the kwargs dictionary.
        """
        lst = []
        while view is not None:
            lst.append(view._bread_crumb)
            view = view._bread_crumb.parent
        lst.reverse()
        return cls(lst, kwargs or {})
