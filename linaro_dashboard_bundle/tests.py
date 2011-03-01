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
Unit tests for DocumentLoader
"""

from StringIO import StringIO
from decimal import Decimal
from linaro_json.schema import ValidationError
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
        self.expected_text = '{\n  "format": "Dashboard Bundle Format 1.0"\n}'

    def test_dumps_produces_ouptut(self):
        observed_text = DocumentIO.dumps(self.doc)
        self.assertEqual(observed_text, self.expected_text)

    def test_dump_produces_output(self):
        stream = StringIO()
        DocumentIO.dump(stream, self.doc)
        observed_text = stream.getvalue()
        self.assertEqual(observed_text, self.expected_text)


class DocumentIOParsingTests(TestCase):

    def test_loader_uses_decimal_to_parse_numbers(self):
        text = resource_string(
            'linaro_dashboard_bundle',
            'test_documents/dummy_doc_with_numbers.json')
        fmt, doc = DocumentIO.loads(text)
        measurement = doc["test_runs"][0]["test_results"][0]["measurement"]
        self.assertEqual(measurement, Decimal("1.5"))
        self.assertTrue(isinstance(measurement, Decimal))

    def test_dumper_can_dump_decimals(self):
        doc = {
            "format": "Dashboard Bundle Format 1.0",
            "test_runs": [
                {
                    "test_id": "NOT RELEVANT",
                    "analyzer_assigned_date": "2010-11-14T01:03:06Z",
                    "analyzer_assigned_uuid": "NOT RELEVANT",
                    "time_check_performed": False,
                    "test_results": [
                        {
                            "test_case_id": "NOT RELEVANT",
                            "result": "unknown",
                            "measurement": Decimal("1.5")
                        }
                    ]
                }
            ]
        }
        text = DocumentIO.dumps(doc)
        self.assertIn("1.5", text)


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
        ('everything_in_one_bundle_1_1', {
            'filename': 'everything_in_one_bundle_1.1.json'
        }),
    ]

    def test_load_document(self):
        # Note: resource_string uses posix-style paths
        # regardless of the actual system paths
        fmt, doc = DocumentIO.load(
            resource_stream('linaro_dashboard_bundle',
                            'test_documents/' + self.filename))
        self.assertIsNot(doc, None)

    def test_load_and_save_does_not_clobber_the_data(self):
        original_text = resource_string(
            'linaro_dashboard_bundle', 'test_documents/' +
            self.filename)
        fmt, doc = DocumentIO.loads(original_text)
        final_text = DocumentIO.dumps(doc)
        final_text += "\n" # the original string has newline at the end
        self.assertEqual(final_text, original_text)


class DocumentEvolutionTests(TestCase):
    """
    Several simple tests that check how DocumentEvolution behaves
    """

    def test_is_latest_for_1_1(self):
        doc = {"format": "Dashboard Bundle Format 1.1"}
        self.assertTrue(DocumentEvolution.is_latest(doc))

    def test_is_latest_for_1_0_1(self):
        doc = {"format": "Dashboard Bundle Format 1.0.1"}
        self.assertFalse(DocumentEvolution.is_latest(doc))

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

    def test_evolved_document_is_no_latest_format(self):
        self.assertFalse(DocumentEvolution.is_latest(self.doc))
        DocumentEvolution.evolve_document(self.doc, one_step=True)
        self.assertFalse(DocumentEvolution.is_latest(self.doc))

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


class DocumentEvolutionTests_1_0_1_to_1_1(TestCase):

    def setUp(self):
        super(DocumentEvolutionTests_1_0_1_to_1_1, self).setUp()
        self.fmt, self.doc = DocumentIO.load(
            resource_stream('linaro_dashboard_bundle',
                            'test_documents/everything_in_one_bundle_1.0.1.json'))

    def test_format_is_changed(self):
        self.assertEqual(self.doc["format"], "Dashboard Bundle Format 1.0.1")
        DocumentEvolution.evolve_document(self.doc, one_step=True)
        self.assertEqual(self.doc["format"], "Dashboard Bundle Format 1.1")

    def test_evolved_document_is_latest_format(self):
        self.assertFalse(DocumentEvolution.is_latest(self.doc))
        DocumentEvolution.evolve_document(self.doc, one_step=True)
        self.assertTrue(DocumentEvolution.is_latest(self.doc))

    def test_sw_image_becomes_image(self):
        self.assertNotIn("image", self.doc["test_runs"][0]["software_context"])
        self.assertIn("sw_image", self.doc["test_runs"][0]["software_context"])
        DocumentEvolution.evolve_document(self.doc, one_step=True)
        self.assertIn("image", self.doc["test_runs"][0]["software_context"])
        self.assertNotIn("sw_image", self.doc["test_runs"][0]["software_context"])

    def test_sw_image_desc_becomes_image_name(self):
        self.assertNotIn("name", self.doc["test_runs"][0]["software_context"]["sw_image"])
        self.assertIn("desc", self.doc["test_runs"][0]["software_context"]["sw_image"])
        DocumentEvolution.evolve_document(self.doc, one_step=True)
        self.assertIn("name", self.doc["test_runs"][0]["software_context"]["image"])
        self.assertNotIn("desc", self.doc["test_runs"][0]["software_context"]["image"])

    def test_evolved_document_is_valid(self):
        DocumentEvolution.evolve_document(self.doc, one_step=True)
        self.assertEqual(DocumentIO.check(self.doc),
                         "Dashboard Bundle Format 1.1")
