#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  config_file.py
#
#  Copyright (C) 2011 Linaro Limited
#  Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
#  Copyright 2013 Neil Williams <codehelp@debian.org>
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
#


"""
Simple shell-sourcable configuration file class
"""

import re


class ConfigFile(object):
    """
    Configuration file parser compatible with files generated
    dbconfig-generate-include using sh format.
    """

    _pattern = re.compile(
        "^(?P<key>[_a-zA-Z][_a-zA-Z0-9]*)=['\"](?P<value>[^']*)['\"]\s*(?:#.*)?$")

    @classmethod
    def load(cls, pathname):
        """
        Load file from pathname and store all the values as instance attributes
        """
        self = cls()
        for key, value in cls._parse(pathname):
            setattr(self, key, value)
        return self

    @classmethod
    def _parse(cls, pathname):
        """
        Parse the contents of pathname and return key-value pairs
        """
        with open(pathname, "r") as stream:
            for lineno, line in enumerate(stream, start=1):
                match = cls._pattern.match(line)
                if match:
                    yield match.group("key"), match.group("value")
