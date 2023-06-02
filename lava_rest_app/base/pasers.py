# Copyright (C) 2019 Linaro Limited
#
# Author: Chase Qi <chase.qi@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import codecs

from django.conf import settings
from rest_framework.exceptions import ParseError
from rest_framework.parsers import BaseParser


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
