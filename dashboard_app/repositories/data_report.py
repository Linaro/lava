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


from xml.sax import parseString
from xml.sax.handler import ContentHandler
import re

from dashboard_app.repositories import Repository, Undefined, Object


class _DataReportHandler(ContentHandler):
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
        # Data report object
        self.obj = Object()

    def endDocument(self):
        if self.obj.name is Undefined:
            raise ValueError("No data view definition found")
        if self.obj.title is Undefined:
            raise ValueError("Data report without a title")
        if self.obj.path is Undefined:
            raise ValueError("Data report without a path")

    def startElement(self, name, attrs):
        if name == "data-report":
            if "name" not in attrs:
                raise ValueError("Data report without a name")
            self.obj.name = attrs["name"]
        elif name == "title" or name == "path":
            self._start_text()
                
    def endElement(self, name):
        if name == "title":
            self.obj.title = self._end_text()
        elif name == "path":
            self.obj.path = self._end_text()
            
    def characters(self, content):
        if isinstance(self._text, list):
            self._text.append(content)


class DataReportRepository(Repository):

    @property
    def settings_variable(self):
        return "DATAREPORT_DIRS"

    def load_from_xml_string(self, text):
        handler = _DataReportHandler()
        parseString(text, handler)
        return self.item_cls(
            name=handler.obj.name,
            title=handler.obj.title,
            path=handler.obj.path)


__all__ = [
    "DataReportRepository",
]
