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

from dashboard_app.repositories import Repository, Undefined, Object
from dashboard_app.repositories.common import BaseContentHandler


class _DataViewHandler(BaseContentHandler):

    """
    ContentHandler subclass for parsing DataView documents
    """
    
    def startDocument(self):
        # Classic-classes 
        BaseContentHandler.startDocument(self)
        # Data view object
        self.obj = Object()
        # Set default values
        self.obj.name = Undefined
        self.obj.backend_queries = {}
        self.obj.arguments = []
        self.obj.documentation = None
        self.obj.summary = None
        # Internal variables
        self._current_backend_query = None

    def endDocument(self):
        # TODO: check if we have anything defined
        if self.obj.name is Undefined:
            raise ValueError("No data view definition found")

    def startElement(self, name, attrs):
        if name == "data-view":
            self.obj.name = attrs["name"]
        elif name == "summary" or name == "documentation":
            self._start_text()
        elif name == "sql":
            self._start_text()
            self._current_backend_query = BackendSpecificQuery(
                attrs.get("backend"), None, [])
            self.obj.backend_queries[
                self._current_backend_query.backend] = self._current_backend_query
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
            self.obj.arguments.append(argument)
                
    def endElement(self, name):
        if name == "sql":
            self._current_backend_query.sql_template = self._end_text()
            self._current_backend_query = None
        elif name == "documentation":
            self.obj.documentation = self._end_text()
        elif name == "summary":
            self.obj.summary = self._end_text()


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


class DataViewRepository(Repository):

    @property
    def settings_variable(self):
        return "DATAVIEW_DIRS"

    def load_from_xml_string(self, text):
        handler = _DataViewHandler()
        parseString(text, handler)
        return self.item_cls(**handler.obj.__dict__)


__all__ = [
    "DataViewRepository",
]
