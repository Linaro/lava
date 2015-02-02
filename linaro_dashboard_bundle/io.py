# Copyright (C) 2010, 2011 Linaro Limited
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


import decimal

from json_schema_validator.schema import Schema
from json_schema_validator.validator import Validator
from pkg_resources import resource_string
import simplejson as json


from linaro_dashboard_bundle.errors import DocumentFormatError


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
        'Dashboard Bundle Format 1.2': Schema(
            json.loads(
                resource_string(
                    __name__,
                    'schemas/dashboard_bundle_format_1.2.json'))),
        'Dashboard Bundle Format 1.3': Schema(
            json.loads(
                resource_string(
                    __name__,
                    'schemas/dashboard_bundle_format_1.3.json'))),
        'Dashboard Bundle Format 1.4': Schema(
            json.loads(
                resource_string(
                    __name__,
                    'schemas/dashboard_bundle_format_1.4.json'))),
        'Dashboard Bundle Format 1.5': Schema(
            json.loads(
                resource_string(
                    __name__,
                    'schemas/dashboard_bundle_format_1.5.json'))),
        'Dashboard Bundle Format 1.6': Schema(
            json.loads(
                resource_string(
                    __name__,
                    'schemas/dashboard_bundle_format_1.6.json'))),
        'Dashboard Bundle Format 1.7': Schema(
            json.loads(
                resource_string(
                    __name__,
                    'schemas/dashboard_bundle_format_1.7.json'))),
        'Dashboard Bundle Format 1.7.1': Schema(
            json.loads(
                resource_string(
                    __name__,
                    'schemas/dashboard_bundle_format_1.7.1.json'))),
    }

    @classmethod
    def _get_dict_impl(cls, retain_order):
        if retain_order:
            object_pairs_hook = json.OrderedDict
        else:
            object_pairs_hook = None
        return object_pairs_hook

    @classmethod
    def _get_indent_and_separators(cls, human_readable):
        if human_readable:
            indent = ' ' * 2
            separators = (',', ': ')
        else:
            indent = None
            separators = (',', ':')
        return indent, separators

    @classmethod
    def load(cls, stream, retain_order=True):
        """
        Load and check a JSON document from the specified stream

        :Discussion:
            The document is read from the stream and parsed as JSON text. It is
            then validated against a set of known formats and their schemas.

        :Return value:
            Tuple (format, document) where format is the string identifying
            document format and document is a JSON document loaded from the
            passed text. If retain_order is True then the resulting objects are
            composed of ordered dictionaries. This mode is slightly slower and
            consumes more memory.

        :Exceptions:
            ValueError
                When the text does not represent a correct JSON document.
            Other exceptions
                This method can also raise exceptions raised by
                DocumentIO.check()
        """
        object_pairs_hook = cls._get_dict_impl(retain_order)
        doc = json.load(stream, parse_float=decimal.Decimal, object_pairs_hook=object_pairs_hook)
        fmt = cls.check(doc)
        return fmt, doc

    @classmethod
    def loads(cls, text, retain_order=True):
        """
        Same as load() but reads data from a string
        """
        object_pairs_hook = cls._get_dict_impl(retain_order)
        doc = json.loads(text, parse_float=decimal.Decimal, object_pairs_hook=object_pairs_hook)
        fmt = cls.check(doc)
        return fmt, doc

    @classmethod
    def dump(cls, stream, doc, human_readable=True, sort_keys=False):
        """
        Check and save a JSON document to the specified stream

        :Discussion:
            The document is validated against a set of known formats and
            schemas and saved to the specified stream.

            If human_readable is True the serialized stream is meant to be read
            by humans, it will have newlines, proper indentation and spaces
            after commas and colons. This option is enabled by default.

            If sort_keys is True then resulting JSON object will have sorted
            keys in all objects. This is useful for predictable format but is
            not recommended if you want to load-modify-save an existing
            document without altering it's general structure. This option is
            not enabled by default.

        :Return value:
            None

        :Exceptions:
            Other exceptions
                This method can also raise exceptions raised by
                DocumentIO.check()
        """
        cls.check(doc)
        indent, separators = cls._get_indent_and_separators(human_readable)
        json.dump(doc, stream,
                  use_decimal=True,
                  indent=indent,
                  separators=separators,
                  sort_keys=sort_keys)

    @classmethod
    def dumps(cls, doc, human_readable=True, sort_keys=False):
        """
        Check and save a JSON document as string

        :Discussion:
            The document is validated against a set of known formats and
            schemas and saved to a string.

            If human_readable is True the serialized value is meant to be read
            by humans, it will have newlines, proper indentation and spaces
            after commas and colons. This option is enabled by default.

            If sort_keys is True then resulting JSON object will have sorted
            keys in all objects. This is useful for predictable format but is
            not recommended if you want to load-modify-save an existing
            document without altering it's general structure. This option is
            not enabled by default.

        :Return value:
            JSON document as string

        :Exceptions:
            Other exceptions
                This method can also raise exceptions raised by
                DocumentIO.check()
        """
        cls.check(doc)
        indent, separators = cls._get_indent_and_separators(human_readable)
        return json.dumps(doc,
                          use_decimal=True,
                          indent=indent,
                          separators=separators,
                          sort_keys=sort_keys)

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
            json_schema_validator.errors.ValidationError
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
