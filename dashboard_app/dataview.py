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

from contextlib import closing
from xml.sax import parseString
from xml.sax.handler import ContentHandler
import logging
import os
import re


class DataView(object):
    """
    Data view, a container for SQL query and optional arguments
    """
    
    def __init__(self, name, backend_queries, arguments, documentation, summary):
        self.name = name
        self.backend_queries = backend_queries
        self.arguments = arguments
        self.documentation = documentation
        self.summary = summary

    def _get_connection_backend_name(self, connection):
        backend = str(type(connection))
        if "sqlite" in backend:
            return "sqlite"
        elif "postgresql" in backend:
            return "postgresql"
        else:
            return ""

    def get_backend_specific_query(self, connection):
        """
        Return BackendSpecificQuery for the specified connection
        """
        sql_backend_name = self._get_connection_backend_name(connection)
        try:
            return self.backend_queries[sql_backend_name]
        except KeyError:
            return self.backend_queries.get(None, None)

    def lookup_argument(self, name):
        """
        Return Argument with the specified name

        Raises LookupError if the argument cannot be found
        """
        for argument in self.arguments:
            if argument.name == name:
                return argument
        raise LookupError(name)

    @classmethod
    def load_from_xml(self, xml_string):
        """
        Load a data view instance from XML description

        This raises ValueError in several error situations.
        TODO: check what kind of exceptions this can raise
        """
        handler = _DataViewHandler()
        parseString(xml_string, handler)
        return handler.data_view

    @classmethod
    def get_connection(cls):
        """
        Get the appropriate connection for data views
        """
        from django.db import connection, connections
        from django.db.utils import ConnectionDoesNotExist
        try:
            return connections['dataview']
        except ConnectionDoesNotExist:
            logging.warning("dataview-specific database connection not available, dataview query is NOT sandboxed")
            return connection  # NOTE: it's connection not connectionS (the default connection)

    def __call__(self, connection, **arguments):
        # Check if arguments have any bogus names
        valid_arg_names = frozenset([argument.name for argument in self.arguments])
        for arg_name in arguments:
            if arg_name not in valid_arg_names:
                raise TypeError("Data view %s has no argument %r" % (self.name, arg_name))
        # Get the SQL template for our database connection
        query = self.get_backend_specific_query(connection)
        if query is None:
            raise LookupError("Specified data view has no SQL implementation "
                              "for current database")
        # Replace SQL aruments with django placeholders (connection agnostic)
        sql = query.sql_template.format(**dict([(arg_name, "%s") for arg_name in query.argument_list]))
        # Construct argument list using defaults for missing values
        sql_args = [
            arguments.get(arg_name, self.lookup_argument(arg_name).default)
            for arg_name in query.argument_list]
        with closing(connection.cursor()) as cursor:
            # Execute the query with the specified arguments
            cursor.execute(sql, sql_args)
            # Get and return the results
            rows = cursor.fetchall()
            columns = cursor.description
            return rows, columns


class Argument(object):
    """
    Data view argument for SQL prepared statements
    """

    def __init__(self, name, type, default, help):
        self.name = name
        self.type = type
        self.default = default
        self.help = help 


class BackendSpecificQuery(object):
    """
    Backend-specific query and argument list
    """

    def __init__(self, backend, sql_template, argument_list):
        self.backend = backend
        self.sql_template = sql_template
        self.argument_list = argument_list


class _DataViewHandler(ContentHandler):
    """
    ContentHandler subclass for parsing DataView documents
    """
    
    def _end_text(self):
        """
        Stop collecting text and produce a stripped string with deduplicated whitespace
        """
        full_text = re.sub("\s+", " ", u''.join(self._text)).strip()
        self.text = None
        return full_text
        
    def _start_text(self):
        """
        Start collecting text
        """
        self._text = []

    def startDocument(self):
        # Text can be None or a [] that accumulates all detected text
        self._text = None
        # Data view object
        self.data_view = DataView(None, {}, [], None, None)
        # Internal variables
        self._current_backend_query = None

    def endDocument(self):
        # TODO: check if we have anything defined
        if self.data_view.name is None:
            raise ValueError("No data view definition found")

    def startElement(self, name, attrs):
        if name == "data-view":
            self.data_view.name = attrs["name"]
        elif name == "summary" or name == "documentation":
            self._start_text()
        elif name == "sql":
            self._start_text()
            self._current_backend_query = BackendSpecificQuery(attrs.get("backend"), None, [])
            self.data_view.backend_queries[self._current_backend_query.backend] = self._current_backend_query 
        elif name == "value":
            if "name" not in attrs:
                raise ValueError("<value> requires attribute 'name'")
            self._text.append("{" + attrs["name"] + "}")
            self._current_backend_query.argument_list.append(attrs["name"])
        elif name == "argument":
            if "name" not in attrs:
                raise ValueError("<argument> requires attribute 'name'")
            if "type" not in attrs:
                raise ValueError("<argument> requires attribute 'type'")
            if attrs["type"] not in ("string", "number", "boolean", "timestamp"):
                raise ValueError("invalid value for argument 'type' on <argument>")
            argument = Argument(name=attrs["name"], type=attrs["type"],
                                   default=attrs.get("default", None),
                                   help=attrs.get("help", None))
            self.data_view.arguments.append(argument)
                
    def endElement(self, name):
        if name == "sql":
            self._current_backend_query.sql_template = self._end_text()
            self._current_backend_query = None
        elif name == "documentation":
            self.data_view.documentation = self._end_text()
        elif name == "summary":
            self.data_view.summary = self._end_text()
            
    def characters(self, content):
        if isinstance(self._text, list):
            self._text.append(content)


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


__all__ = [
    "Argument",
    "BackendSpecificQuery",
    "DataView", 
    "DataViewRepository",
]
