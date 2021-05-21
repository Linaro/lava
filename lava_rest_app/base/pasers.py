# -*- coding: utf-8 -*-
# Copyright (C) 2019 Linaro Limited
#
# Author: Chase Qi <chase.qi@linaro.org>
#
# This file is part of LAVA.
#
# LAVA is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# LAVA is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with LAVA.  If not, see <http://www.gnu.org/licenses/>.

import codecs

from rest_framework.parsers import BaseParser
from rest_framework.exceptions import ParseError

from django.conf import settings


class PlainTextParser(BaseParser):
    """
    Plain text parser.
    """

    media_type = "text/plain"

    def parse(self, stream, media_type=None, parser_context=None):
        """
        Simply return a string representing the body of the request.
        """
        parser_context = parser_context or {}
        encoding = parser_context.get("encoding", settings.DEFAULT_CHARSET)

        try:
            decoded_stream = codecs.getreader(encoding)(stream)
            text_content = decoded_stream.read()
            return text_content
        except ValueError as exc:
            raise ParseError("Plain text parse error - %s" % str(exc))
