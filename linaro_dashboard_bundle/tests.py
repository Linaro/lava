"""
Unit tests for DocumentLoader
"""

from decimal import Decimal
from StringIO import StringIO

from linaro_json import ValidationError
from pkg_resources import (resource_string, resource_stream)
from testscenarios import TestWithScenarios
from testtools import TestCase

from linaro_dashboard_bundle import (DocumentIO, DocumentFormatError)

class DocumentIOLoadTests(TestCase):
    """
    Various tests checking how DocumentIO load() and loads() operate
    """

    def setUp(self):
        super(DocumentIOLoadTests, self).setUp()
        self.text = '{"format": "Dashboard Bundle Format 1.0"}'
        self.expected_fmt = "Dashboard Bundle Format 1.0"
        self.expected_doc = {"format": "Dashboard Bundle Format 1.0"}

    def test_loads_return_value(self):
        fmt, doc = DocumentIO.loads(self.text)
        self.assertEqual(fmt, self.expected_fmt)
        self.assertEqual(doc, self.expected_doc)

    def test_load_return_value(self):
        stream = StringIO(self.text)
        fmt, doc = DocumentIO.load(stream)
        self.assertEqual(fmt, self.expected_fmt)
        self.assertEqual(doc, self.expected_doc)


class DocumentIODumpTests(TestCase):


    def setUp(self):
        super(DocumentIODumpTests, self).setUp()
        self.doc = {"format": "Dashboard Bundle Format 1.0"}
        self.expected_json = '{\n    "format": "Dashboard Bundle Format 1.0"\n}'

    def test_dump_produces_output(self):
        stream = StringIO()
        DocumentIO.dump(stream, self.doc)
        self.assertEqual(stream.getvalue(), self.expected_json)


class DocumentIOParsingTests(TestCase):

    def test_loader_uses_decimal_to_parse_numbers(self):
        text = '''
        {
            "format": "Dashboard Bundle Format 1.0",
            "test_runs": [
                {
                    "test_id": "NOT RELEVANT",
                    "analyzer_assigned_date": "2010-11-14T01:03:06Z",
                    "analyzer_assigned_uuid": "NOT RELEVANT",
                    "time_check_performed": false,
                    "test_results": [
                        {
                            "test_case_id": "NOT RELEVANT",
                            "result": "unknown",
                            "measurement": 1.5
                        }
                    ]
                }
            ]
        }
        '''
        fmt, doc = DocumentIO.loads(text)
        measurement = doc["test_runs"][0]["test_results"][0]["measurement"]
        self.assertEqual(measurement, Decimal("1.5"))
        self.assertTrue(isinstance(measurement, Decimal))


class DocumentIOCheckTests(TestCase):

    def test_unknown_format_raises_DocumentFormatError(self):
        doc = {"format": "Bad Format"}
        ex = self.assertRaises(DocumentFormatError, DocumentIO.check, doc)
        self.assertEqual(str(ex), "Unrecognized or missing document format")
        self.assertEqual(ex.format, "Bad Format")

    def test_validator_finds_schema_mismatch(self):
        doc = {
            "format": "Dashboard Bundle Format 1.0",
            "property_that_does_not_belong_here": 1
        }
        self.assertRaises(ValidationError, DocumentIO.check, doc)


class DocumentIORegressionTests(TestWithScenarios, TestCase):
    """
    A set of tests ensuring that it's possible to load each of the file
    from the test_documents directory.

    Each test is defined as a scenario
    """
    scenarios = [
        ('smallest_bundle', {'filename': 'smallest_bundle.json'}),
        ('everything_in_one_bundle', {'filename': 'everything_in_one_bundle.json'}),
    ]

    def test_load_document(self):
        # Note: resource_string uses posix-style paths
        # regardless of the actual system paths
        fmt, doc = DocumentIO.load(
            resource_stream('linaro_dashboard_bundle',
                            'test_documents/' + self.filename))
        self.assertIsNot(doc, None)
