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

"""
DataViews: Encapsulated SQL query definitions.

Implementation of the following launchpad blueprint:
https://blueprints.launchpad.net/launch-control/+spec/other-linaro-n-data-views-for-launch-control
"""

from xml.sax import parseString
from xml.sax.handler import ContentHandler
import logging
import os
import re


class DataView(object):
    """
    Data view, a container for SQL query and optional arguments
    """
    
    def __init__(self, name, sql, arguments, documentation, summary):
        self.name = name
        self.sql = sql
        self.arguments = arguments
        self.documentation = documentation
        self.summary = summary

    @classmethod
    def load_from_xml(self, xml_string):
        """
        Load a data view instance from XML description

        This raises ValueError in several error situations.
        TODO: check what kind of exceptions this can raise
        """
        handler = _DataViewHandler()
        parseString(xml_string, handler)
        return handler.dataview


class DataViewArgument(object):
    """
    Data view argument for SQL prepared statements
    """

    def __init__(self, name, type, default, help):
        self.name = name
        self.type = type
        self.default = default
        self.help = help 



class _DataViewHandler(ContentHandler):
    """
    ContentHandler subclass for parsing DataView documents
    """

    class Object(object):
        """
        Simple container for named attributes
        """

    def startDocument(self):
        # Text can be None or a [] that accumulates all detected text
        self.text = None
        # Data view object
        self.obj = self.Object()
        self.obj.sql = {}
        self.obj.arguments = []

    def endDocument(self):
        self.dataview = DataView(self.obj.name,
            self.obj.sql, self.obj.arguments,
            self.obj.documentation, self.obj.summary)

    def startElement(self, name, attrs):
        if name == "data-view":
            self.obj.name = attrs["name"]
        elif name == "summary" or name == "documentation":
            self._start_text()
        elif name == "sql":
            self._start_text()
            self.obj.sql_backend = attrs.get("backend", "")
        elif name == "value":
            self.text.append("{" + attrs["name"] + "}")
        elif name == "argument":
            if "name" not in attrs:
                raise ValueError("Argument name missing")
            if "type" not in attrs:
                raise ValueError("Argument type missing")
            if attrs["type"] not in ("string", "number", "boolean", "timestamp"):
                raise ValueError("Invalid argument type")
            arg = DataViewArgument(name=attrs["name"], type=attrs["type"],
                                   default=attrs.get("default", None),
                                   help=attrs.get("help", None))
            self.obj.arguments.append(arg)
    
    def _end_text(self):
        """
        Stop collecting text and produce a stripped string with deduplicated whitespace
        """
        full_text = re.sub("\s+", " ", u''.join(self.text)).strip()
        self.text = None
        return full_text
        
    def _start_text(self):
        """
        Start collecting text
        """
        self.text = []
                
    def endElement(self, name):
        if name == "sql":
            self.obj.sql[self.obj.sql_backend] = self._end_text()
        elif name == "documentation":
            self.obj.documentation = self._end_text()
        elif name == "summary":
            self.obj.summary = self._end_text()
            
    def characters(self, content):
        if isinstance(self.text, list):
            self.text.append(content)


class DataViewRepository(object):

    _instance = None

    def __init__(self):
        self.data_views = []

    def __iter__(self):
        return iter(self.data_views)

    def __getitem__(self, name):
        for item in self:
            if item.name == name:
                return item
        else:
            raise KeyError(name)

    def load_from_directory(self, directory):
        for name in os.listdir(directory):
            pathname = os.path.join(directory, name)
            if os.path.isfile(pathname) and pathname.endswith(".xml"):
                self.load_from_file(pathname)

    def load_from_file(self, pathname):
        try:
            with open(pathname, "rt") as stream:
                text = stream.read()
            data_view = DataView.load_from_xml(text)
            self.data_views.append(data_view)
        except Exception as exc:
            logging.error("Unable to load data view from %s: %s", pathname, exc)

    @classmethod
    def get_instance(cls):
        from django.conf import settings
        if cls._instance is None:
            cls._instance = cls()
            cls._instance.load_default()

        # I development mode always reload data views
        if getattr(settings, "DEBUG", False) is True:
            cls._instance.data_views = []
            cls._instance.load_default()
        return cls._instance

    def load_default(self):
        from django.conf import settings
        for dirname in getattr(settings, "DATAVIEW_DIRS", []):
            self.load_from_directory(dirname)


__all__ = ["DataView", "DataViewArgument", "DataViewRepository"]
