# Copyright (C) 2013-2018 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#         Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""
Simple shell-sourcable configuration file class
"""

import os
import re


class ConfigFile:
    """
    Configuration file parser compatible with files generated
    dbconfig-generate-include using sh format.
    """

    _pattern = re.compile(
        r"^(?P<key>[_a-zA-Z][_a-zA-Z0-9]*)=['\"](?P<value>[^']*)['\"]\s*(?:#.*)?$"
    )

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
        with open(pathname) as stream:
            for lineno, line in enumerate(stream, start=1):
                match = cls._pattern.match(line)
                if match:
                    yield match.group("key"), match.group("value")

    @classmethod
    def serialize(cls, pathname, config):
        """
        Store all the values from config in the file from pathname
        """
        os.makedirs(os.path.dirname(pathname), exist_ok=True)
        with open(pathname, "w+") as handle:
            for key in config:
                handle.write('%s="%s"\n' % (key, config[key]))
