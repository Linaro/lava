# Copyright (C) 2010 Linaro Limited
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
#
# This file is part of Launch Control.
#
# Launch Control is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License version 3
# as published by the Free Software Foundation
#
# Launch Control is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Launch Control.  If not, see <http://www.gnu.org/licenses/>.

"""
Linaro dashboard bundle manipulation utilities.

Dashboard bundle is a family of file formats designed to store test
results and associated meta data.
"""

import decimal

from linaro_json import (json, Schema, Validator)
from pkg_resources import resource_string


__version__ = (1, 0, 0, "alpha", 0)
__all__ = ["get_version", "DocumentIO", "DocumentFormatError"]


def get_version():
    """
    Return a string representing the version of linaro_dashboard_bundle
    package
    """
    major, minor, micro, releaselevel, serial = __version__
    assert releaselevel in ('alpha', 'beta', 'candidate', 'final')
    base_version = "%s.%s.%s" % (major, minor, micro)
    if releaselevel != 'final':
        base_version += "-%s" % releaselevel
    return base_version



class DocumentFormatError(ValueError):
    """
    Exception raised when document format is not in the set of known
    values.

    You can access the :format: property to inspect the format that was
    found in the document
    """

    def __init__(self, format):
        self.format = format

    def __str__(self):
        return "Unrecognized or missing document format"


class DocumentIO(object):
    """
    Document IO encapsulates various (current and past) file
    formats and provides a single entry point for analyzing a document,
    determining its format and validating the contents.
    """

    SCHEMAS = {
        'Dashboard Bundle Format 1.0': Schema(
            json.loads(
                resource_string(
                    __name__,
                    'schemas/dashboard_bundle_format_1.0.1.json'))),
    }

    @classmethod
    def _apply_load_quirks(cls, doc):
        """
        Quirks for the older 1.0 format

        The following quirks are applied:
            * TestRun's sw_context is changed to software_context
            * TestRun's hw_context is changed to hardware_context
        """
        if doc.get("format") == "Dashboard Bundle Format 1.0":
            for test_run in doc.get("test_runs", []):
                if "hw_context" in test_run and "hardware_context" not in test_run:
                    test_run["hardware_context"] = test_run["hw_context"]
                    del test_run["hw_context"]
                if "sw_context" in test_run and "software_context" not in test_run:
                    test_run["software_context"] = test_run["sw_context"]
                    del test_run["sw_context"]

    @classmethod
    def load(cls, stream, quirks=True):
        """
        Load and check a JSON document from the specified stream

        :Discussion:
            The document is read from the stream and parsed as JSON
            text. It is then validated against a set of known formats
            and their schemas.

        :Return value:
            Tuple (format, document)
            where format is the string identifying document format and
            document is a JSON document loaded from the passed text.

        :Exceptions:
            ValueError
                When the text does not represent a correct JSON document.
            Other exceptions
                This method can also raise exceptions raised by
                DocumentIO.check()
        """
        doc = json.load(stream, parse_float=decimal.Decimal)
        if quirks:
            cls._apply_load_quirks(doc)
        fmt = cls.check(doc)
        return fmt, doc

    @classmethod
    def dump(cls, stream, doc):
        """
        Check and save a JSON document to the specified stream

        :Discussion:
            The document is validated against a set of known formats and
            schemas and saved to the specified stream.

        :Return value:
            None

        :Exceptions:
            Other exceptions
                This method can also raise exceptions raised by
                DocumentIO.check()
        """
        cls.check(doc)
        json.dump(doc, stream, indent=4)

    @classmethod
    def loads(cls, text):
        """
        Same as load() but reads data from a string
        """
        doc = json.loads(text, parse_float=decimal.Decimal)
        fmt = cls.check(doc)
        return fmt, doc

    @classmethod
    def check(cls, doc):
        """
        Check document format and validate the contents against a schema.

        :Discussion:
            The document is validated against a set of known versions
            and their schemas.

        :Return value:
            String identifying document format

        :Exceptions:
            linaro_json.ValidationError
                When the document does not match the appropriate schema.
            linaro_dashboard_bundle.errors.DocumentFormatError
                When the document format is not in the known set of formats.
        """
        fmt = doc.get('format', None)
        schema = cls.SCHEMAS.get(fmt, None)
        if schema is None:
            raise DocumentFormatError(fmt)
        Validator.validate(schema, doc)
        return fmt
