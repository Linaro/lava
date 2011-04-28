# Copyright (C) 2011 Linaro Limited
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

import abc
import logging
import os

from django.conf import settings


class RepositoryItemMeta(abc.ABCMeta):
    """
    Meta class for RepositoryItem

    Adds magic to set repository._item_cls to the non-meta
    class object that use this meta-class.
    """

    def __new__(mcls, name, bases, namespace):
        cls = super(RepositoryItemMeta, mcls).__new__(mcls, name, bases, namespace)
        if "repository" in namespace:
            repo = cls.repository
            repo.item_cls = cls
        return cls


class RepositoryItem(object):

    __metaclass__ = RepositoryItemMeta 

    class DoesNotExist(Exception):
        pass

    class MultipleValuesReturned(Exception):
        pass


class RepositoryQuerySet(object):

    def __iter__(self):
        return iter(self._items)

    def __len__(self):
        return len(self._items)

    def __nonzero__(self):
        return len(self._items) != 0

    def __getitem__(self, slice_or_index):
        return self._items.__getitem__(slice_or_index)

# Django QuerySet like API:

    def count(self):
        return len(self)

    def all(self):
        return self
    
    def get(self, **kwargs):
        query = self.filter(**kwargs)
        if len(query) == 1:
            return query[0]
        if not query: 
            raise self.model.DoesNotExist()
        else:
            raise self.model.MultipleValuesReturned()

    def filter(self, **kwargs):
        return self._sub_query([
            item for item in self._items
            if all(
                (getattr(item, attr) == value)
                for attr, value in kwargs.iteritems())])

# Internal API

    def __init__(self, model, items):
        self.model = model
        self._items = items

    def _sub_query(self, items):
        return self.__class__(self.model, items)


class Repository(object):

    __metaclass__ = abc.ABCMeta

    def __init__(self):
        self.item_cls = None # later patched by RepositoryItemMeta
        self._items = []

    def _queryset(self):
        # In development mode always reload repository items
        if getattr(settings, "DEBUG", False) is True:
            self._items = []
            self._load_default()
        return RepositoryQuerySet(self.item_cls, self._items)

    def all(self):
        return self._queryset().all()

    def filter(self, **kwargs):
        return self._queryset().filter(**kwargs)

    def get(self, **kwargs):
        return self._queryset().get(**kwargs)

    def load_from_directory(self, directory):
        for name in os.listdir(directory):
            pathname = os.path.join(directory, name)
            if os.path.isfile(pathname) and pathname.endswith(".xml"):
                self.load_from_file(pathname)

    @abc.abstractmethod
    def load_from_xml_string(self, text):
        """
        Load an IRepositoryItem from specified XML text
        """

    def load_from_file(self, pathname):
        try:
            with open(pathname, "rt") as stream:
                text = stream.read()
            item = self.load_from_xml_string(text)
            self._items.append(item)
        except Exception as exc:
            logging.exception("Unable to load object into repository %s: %s", pathname, exc)

    @abc.abstractproperty
    def settings_variable(self):
        """
        VARIABLE to look for in django settings. It should
        contain a list of directories to look for .xml
        files.
        """

    def _load_default(self):
        from django.conf import settings
        for dirname in getattr(settings, self.settings_variable, []):
            self.load_from_directory(dirname)
