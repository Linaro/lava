# Copyright (C) 2010 Linaro Limited
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
#
# This file is part of linaro-dashboard-bundle.
#
# linaro-dashboard-bundle is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License version 3
# as published by the Free Software Foundation
#
# linaro-dashboard-bundle is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with linaro-dashboard-bundle.  If not, see <http://www.gnu.org/licenses/>.

"""
Linaro dashboard bundle manipulation utilities.

Dashboard bundle is a family of file formats designed to store test
results and associated meta data. This module provides standard API for
manipulating such documents.
"""

import decimal

from linaro_json.schema import (Schema, Validator)
from pkg_resources import resource_string
import simplejson as json


__version__ = (1, 2, 0, "alpha", 1)
try:
    import versiontools
    __version__ = versiontools.Version.from_tuple(__version__)
except ImportError:
    pass
__all__ = ["get_version", "DocumentIO", "DocumentEvolution", "DocumentFormatError"]


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


class DocumentEvolution(object):
    """
    Document Evolution encapsulates format changes between subsequent
    document format versions. This is useful when your code is designed
    to handle single, for example the most recent, format of the
    document but would like to interact with any previous format
    transparently.
    """

    @classmethod
    def is_latest(cls, doc):
        """
        Check if the document is at the latest known version
        """
        # The last element of the evolution path, the second item in the
        # tuple is final format
        return cls.EVOLUTION_PATH[-1][1] == doc.get("format")

    @classmethod
    def evolve_document(cls, doc, one_step=False):
        """
        Evolve document to the latest known version.

        Runs an in-place evolution of the document `doc` converting it
        to more recent versions. The conversion process is lossless.

        :param doc: document (changed in place)
        :type doc: JSON document, usually python dictionary
        :param one_step: if true then just one step of the evolution path is taken before exiting.
        :rtype: None
        """
        for src_fmt, dst_fmt, convert_fn in cls.EVOLUTION_PATH:
            if doc.get("format") == src_fmt:
                convert_fn(doc)
                if one_step:
                    break

    def _evolution_from_1_0_to_1_0_1(doc):
        """
        Evolution method for 1.0 -> 1.0.1
            * TestRun's sw_context is changed to software_context
            * TestRun's hw_context is changed to hardware_context
            * Format is upgraded to "Dashboard Bundle Format 1.0.1"
        """
        assert doc.get("format") == "Dashboard Bundle Format 1.0"
        for test_run in doc.get("test_runs", []):
            if "hw_context" in test_run:
                test_run["hardware_context"] = test_run["hw_context"]
                del test_run["hw_context"]
            if "sw_context" in test_run:
                test_run["software_context"] = test_run["sw_context"]
                del test_run["sw_context"]
        doc["format"] = "Dashboard Bundle Format 1.0.1"

    EVOLUTION_PATH = [
        ("Dashboard Bundle Format 1.0",
         "Dashboard Bundle Format 1.0.1",
         _evolution_from_1_0_to_1_0_1),
    ]


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
                    'schemas/dashboard_bundle_format_1.0.json'))),
        'Dashboard Bundle Format 1.0.1': Schema(
            json.loads(
                resource_string(
                    __name__,
                    'schemas/dashboard_bundle_format_1.0.1.json'))),
        'Dashboard Bundle Format 1.1': Schema(
            json.loads(
                resource_string(
                    __name__,
                    'schemas/dashboard_bundle_format_1.1.json'))),
    }

    @classmethod
    def load(cls, stream):
        """
        Load and check a JSON document from the specified stream

        :Discussion:
            The document is read from the stream and parsed as JSON
            text. It is then validated against a set of known formats
            and their schemas.

        :Return value:
            Tuple (format, document) where format is the string
            identifying document format and document is a JSON document
            loaded from the passed text.

        :Exceptions:
            ValueError
                When the text does not represent a correct JSON document.
            Other exceptions
                This method can also raise exceptions raised by
                DocumentIO.check()
        """
        doc = json.load(stream, parse_float=decimal.Decimal, object_pairs_hook=json.ordered_dict.OrderedDict)
        fmt = cls.check(doc)
        return fmt, doc

    @classmethod
    def loads(cls, text):
        """
        Same as load() but reads data from a string
        """
        doc = json.loads(text, parse_float=decimal.Decimal, object_pairs_hook=json.ordered_dict.OrderedDict)
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
        json.dump(doc, stream, indent=" " * 2, use_decimal=True)

    @classmethod
    def dumps(cls, doc):
        """
        Check and save a JSON document as string

        :Discussion:
            The document is validated against a set of known formats and
            schemas and saved to a string

        :Return value:
            JSON document as string

        :Exceptions:
            Other exceptions
                This method can also raise exceptions raised by
                DocumentIO.check()
        """
        cls.check(doc)
        return json.dumps(doc, indent=" " * 2, use_decimal=True)

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
        fmt = doc.get('format')
        schema = cls.SCHEMAS.get(fmt)
        if schema is None:
            raise DocumentFormatError(fmt)
        Validator.validate(schema, doc)
        return fmt
