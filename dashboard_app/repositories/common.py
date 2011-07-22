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


from xml.sax.handler import ContentHandler
import re


class BaseContentHandler(ContentHandler):

    def _end_text(self):
        """
        Stop collecting text and produce a stripped string with de-duplicated
        whitespace
        """
        full_text = re.sub("\s+", " ", u''.join(self._text)).strip()
        self.text = None
        return full_text
        
    def _start_text(self):
        """
        Start collecting text
        """
        self._text = []
            
    def characters(self, content):
        if isinstance(self._text, list):
            self._text.append(content)

    def startDocument(self):
        # Text can be None or a [] that accumulates all detected text
        self._text = None
