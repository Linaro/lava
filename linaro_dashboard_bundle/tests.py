"""
Unit tests for DocumentLoader
"""

from decimal import Decimal
from StringIO import StringIO

from linaro_json import ValidationError
from pkg_resources import (resource_string, resource_stream)
from testscenarios import TestWithScenarios
from testtools import TestCase

from linaro_dashboard_bundle import (
    DocumentEvolution,
    DocumentFormatError,
    DocumentIO,
)


class DocumentIOLoadTests(TestCase):
    """
    Various tests checking how DocumentIO load() and loads() operate
    """

    def setUp(self):
        super(DocumentIOLoadTests, self).setUp()
        self.text = '{"format": "Dashboard Bundle Format 1.0"}'
        self.expected_fmt = "Dashboard Bundle Format 1.0"
        self.expected_doc = {"format": "Dashboard Bundle Format 1.0"}

    def test_loads_return_value_without_quirks(self):
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
        ('smallest_bundle', {
            'filename': 'smallest_bundle.json'
        }),
        ('everything_in_one_bundle_1_0', {
            'filename': 'everything_in_one_bundle_1.0.json'
        }),
        ('everything_in_one_bundle_1_0_1', {
            'filename': 'everything_in_one_bundle_1.0.1.json'
        }),
    ]

    def test_load_document(self):
        # Note: resource_string uses posix-style paths
        # regardless of the actual system paths
        fmt, doc = DocumentIO.load(
            resource_stream('linaro_dashboard_bundle',
                            'test_documents/' + self.filename))
        self.assertIsNot(doc, None)


class DocumentEvolutionTests(TestCase):
    """
    Several simple tests that check how DocumentEvolution behaves
    """
    def test_is_latest_for_1_0_1(self):
        doc = {"format": "Dashboard Bundle Format 1.0.1"}
        self.assertTrue(DocumentEvolution.is_latest(doc))

    def test_is_lastest_for_1_0(self):
        doc = {"format": "Dashboard Bundle Format 1.0"}
        self.assertFalse(DocumentEvolution.is_latest(doc))


class DocumentEvolutionTests_1_0_to_1_0_1(TestCase):

    def setUp(self):
        super(DocumentEvolutionTests_1_0_to_1_0_1, self).setUp()
        self.fmt, self.doc = DocumentIO.load(
            resource_stream('linaro_dashboard_bundle',
                            'test_documents/everything_in_one_bundle_1.0.json'))

    def test_format_is_changed(self):
        self.assertEqual(self.doc["format"], "Dashboard Bundle Format 1.0")
        DocumentEvolution.evolve_document(self.doc, one_step=True)
        self.assertEqual(self.doc["format"], "Dashboard Bundle Format 1.0.1")

    def test_evolved_document_is_latest_format(self):
        self.assertFalse(DocumentEvolution.is_latest(self.doc))
        DocumentEvolution.evolve_document(self.doc, one_step=True)
        self.assertTrue(DocumentEvolution.is_latest(self.doc))

    def test_sw_context_becomes_software_context(self):
        self.assertNotIn("software_context", self.doc["test_runs"][0])
        self.assertIn("sw_context", self.doc["test_runs"][0])
        DocumentEvolution.evolve_document(self.doc, one_step=True)
        self.assertIn("software_context", self.doc["test_runs"][0])
        self.assertNotIn("sw_context", self.doc["test_runs"][0])

    def test_hw_context_becomes_hardware_context(self):
        self.assertNotIn("hardware_context", self.doc["test_runs"][0])
        self.assertIn("hw_context", self.doc["test_runs"][0])
        DocumentEvolution.evolve_document(self.doc, one_step=True)
        self.assertIn("hardware_context", self.doc["test_runs"][0])
        self.assertNotIn("hw_context", self.doc["test_runs"][0])

    def test_evolved_document_is_valid(self):
        DocumentEvolution.evolve_document(self.doc, one_step=True)
        self.assertEqual(DocumentIO.check(self.doc),
                         "Dashboard Bundle Format 1.0.1")
