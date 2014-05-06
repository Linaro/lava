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

"""
Unit tests for DocumentLoader
"""

from StringIO import StringIO
from decimal import Decimal
from json_schema_validator.errors import ValidationError
from pkg_resources import (resource_string, resource_stream)
from simplejson.ordered_dict import OrderedDict
from testscenarios import TestWithScenarios
from testtools import TestCase

from linaro_dashboard_bundle.errors import DocumentFormatError
from linaro_dashboard_bundle.evolution import DocumentEvolution
from linaro_dashboard_bundle.io import DocumentIO


class DocumentIOLoadTests(TestCase):
    """
    Various tests checking how DocumentIO load() and loads() operate
    """

    def setUp(self):
        super(DocumentIOLoadTests, self).setUp()
        self.text = '{"format": "Dashboard Bundle Format 1.0", "test_runs": []}'
        self.stream = StringIO(self.text)
        self.expected_fmt = "Dashboard Bundle Format 1.0"
        self.expected_doc = {"format": "Dashboard Bundle Format 1.0", "test_runs": []}
        self.expected_keys = ["format", "test_runs"]

    def test_loads__return_value(self):
        fmt, doc = DocumentIO.loads(self.text)
        self.assertEqual(fmt, self.expected_fmt)
        self.assertEqual(doc, self.expected_doc)

    def test_load__return_value(self):
        fmt, doc = DocumentIO.load(self.stream)
        self.assertEqual(fmt, self.expected_fmt)
        self.assertEqual(doc, self.expected_doc)

    def test_loads__with_enabled_retain_order__key_order(self):
        fmt, doc = DocumentIO.loads(self.text, retain_order=True)
        observed_keys = doc.keys()
        self.assertEqual(observed_keys, self.expected_keys)

    def test_load__with_enabled_retain_order__key_order(self):
        fmt, doc = DocumentIO.load(self.stream, retain_order=True)
        observed_keys = doc.keys()
        self.assertEqual(observed_keys, self.expected_keys)

    def test_loads__with_enabled_retain_order__dict_class(self):
        fmt, doc = DocumentIO.loads(self.text, retain_order=True)
        observed_impl = type(doc)
        # Note:    VVV
        self.assertNotEqual(observed_impl, dict)
        # The returned object is _not_ a plain dictionary

    def test_load__with_enabled_retain_order__dict_class(self):
        fmt, doc = DocumentIO.load(self.stream, retain_order=True)
        observed_impl = type(doc)
        # Note:    VVV
        self.assertNotEqual(observed_impl, dict)
        # The returned object is _not_ a plain dictionary

    def test_loads__with_disabled_retain_order__dict_class(self):
        fmt, doc = DocumentIO.loads(self.text, retain_order=False)
        observed_impl = type(doc)
        self.assertEqual(observed_impl, dict)

    def test_load__with_disabled_retain_order__dict_class(self):
        fmt, doc = DocumentIO.load(self.stream, retain_order=False)
        expected_impl = dict
        observed_impl = type(doc)
        self.assertEqual(observed_impl, expected_impl)


class DocumentIODumpTests(TestCase):

    def setUp(self):
        super(DocumentIODumpTests, self).setUp()
        self.doc = OrderedDict([
            ("test_runs", []),
            ("format", "Dashboard Bundle Format 1.0"),
        ])
        self.expected_readable_text = '{\n  "test_runs": [], \n  "format": "Dashboard Bundle Format 1.0"\n}'
        self.expected_readable_sorted_text = '{\n  "format": "Dashboard Bundle Format 1.0", \n  "test_runs": []\n}'
        self.expected_compact_text = '{"test_runs":[],"format":"Dashboard Bundle Format 1.0"}'
        self.expected_compact_sorted_text = '{"format":"Dashboard Bundle Format 1.0","test_runs":[]}'

    def test_dumps_produces_readable_ouptut(self):
        observed_text = DocumentIO.dumps(self.doc, human_readable=True)
        self.assertEqual(observed_text, self.expected_readable_text)

    def test_dumps_produces_readable_sorted_ouptut(self):
        observed_text = DocumentIO.dumps(self.doc, human_readable=True, sort_keys=True)
        self.assertEqual(observed_text, self.expected_readable_sorted_text)

    def test_dumps_produces_compact_ouptut(self):
        observed_text = DocumentIO.dumps(self.doc, human_readable=False)
        self.assertEqual(observed_text, self.expected_compact_text)

    def test_dumps_produces_compact_sorted_ouptut(self):
        observed_text = DocumentIO.dumps(self.doc, human_readable=False, sort_keys=True)
        self.assertEqual(observed_text, self.expected_compact_sorted_text)

    def test_dump_produces_readable_output(self):
        stream = StringIO()
        DocumentIO.dump(stream, self.doc, human_readable=True)
        observed_text = stream.getvalue()
        self.assertEqual(observed_text, self.expected_readable_text)

    def test_dump_produces_compact_output(self):
        stream = StringIO()
        DocumentIO.dump(stream, self.doc, human_readable=False)
        observed_text = stream.getvalue()
        self.assertEqual(observed_text, self.expected_compact_text)

    def test_dump_produces_readable_sorted_output(self):
        stream = StringIO()
        DocumentIO.dump(stream, self.doc, human_readable=True, sort_keys=True)
        observed_text = stream.getvalue()
        self.assertEqual(observed_text, self.expected_readable_sorted_text)

    def test_dump_produces_compact_sorted_output(self):
        stream = StringIO()
        DocumentIO.dump(stream, self.doc, human_readable=False, sort_keys=True)
        observed_text = stream.getvalue()
        self.assertEqual(observed_text, self.expected_compact_sorted_text)


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
        ('everything_in_one_bundle_1_2', {
            'filename': 'everything_in_one_bundle_1.2.json'
        }),
        ('everything_in_one_bundle_1_3', {
            'filename': 'everything_in_one_bundle_1.3.json'
        }),
        ('everything_in_one_bundle_1_4', {
            'filename': 'everything_in_one_bundle_1.4.json'
        }),
        ('everything_in_one_bundle_1_5', {
            'filename': 'everything_in_one_bundle_1.5.json'
        }),
        ('everything_in_one_bundle_1_6', {
            'filename': 'everything_in_one_bundle_1.6.json'
        }),
        ('everything_in_one_bundle_1_7', {
            'filename': 'everything_in_one_bundle_1.7.json'
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


class DocumentEvolutionTests_1_0_to_1_0_1(TestCase):

    def setUp(self):
        super(DocumentEvolutionTests_1_0_to_1_0_1, self).setUp()
        self.fmt, self.doc = DocumentIO.load(
            resource_stream('linaro_dashboard_bundle',
                            'test_documents/evolution_1.0.json'),
            retain_order=False)

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

    def test_evolved_document_is_what_we_expect(self):
        DocumentEvolution.evolve_document(self.doc, one_step=True)
        fmt, expected = DocumentIO.load(
            resource_stream('linaro_dashboard_bundle',
                            'test_documents/evolution_1.0.1.json'),
            retain_order=False)
        self.assertEqual(self.doc, expected)


class DocumentEvolutionTests_1_0_1_to_1_1(TestCase):

    def setUp(self):
        super(DocumentEvolutionTests_1_0_1_to_1_1, self).setUp()
        self.fmt, self.doc = DocumentIO.load(
            resource_stream('linaro_dashboard_bundle',
                            'test_documents/evolution_1.0.1.json'),
            retain_order=False)

    def test_format_is_changed(self):
        self.assertEqual(self.doc["format"], "Dashboard Bundle Format 1.0.1")
        DocumentEvolution.evolve_document(self.doc, one_step=True)
        self.assertEqual(self.doc["format"], "Dashboard Bundle Format 1.1")

    def test_evolved_document_is_latest_format(self):
        self.assertFalse(DocumentEvolution.is_latest(self.doc))
        DocumentEvolution.evolve_document(self.doc, one_step=True)
        self.assertFalse(DocumentEvolution.is_latest(self.doc))

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

    def test_evolved_document_is_what_we_expect(self):
        DocumentEvolution.evolve_document(self.doc, one_step=True)
        fmt, evolved_doc = DocumentIO.load(
            resource_stream('linaro_dashboard_bundle',
                            'test_documents/evolution_1.1.json'),
            retain_order=False)
        self.assertEqual(self.doc, evolved_doc)


class DocumentEvolutionTests_1_1_to_1_2(TestCase):

    def setUp(self):
        super(DocumentEvolutionTests_1_1_to_1_2, self).setUp()
        self.fmt, self.doc = DocumentIO.load(
            resource_stream('linaro_dashboard_bundle',
                            'test_documents/evolution_1.1.json'),
            retain_order=False)

    def test_format_is_changed(self):
        self.assertEqual(self.doc["format"], "Dashboard Bundle Format 1.1")
        DocumentEvolution.evolve_document(self.doc, one_step=True)
        self.assertEqual(self.doc["format"], "Dashboard Bundle Format 1.2")

    def test_evolved_document_is_latest_format(self):
        self.assertFalse(DocumentEvolution.is_latest(self.doc))
        DocumentEvolution.evolve_document(self.doc, one_step=True)
        self.assertFalse(DocumentEvolution.is_latest(self.doc))

    def test_evolved_document_is_valid(self):
        DocumentEvolution.evolve_document(self.doc, one_step=True)
        self.assertEqual(DocumentIO.check(self.doc),
                         "Dashboard Bundle Format 1.2")

    def test_evolved_document_is_what_we_expect(self):
        DocumentEvolution.evolve_document(self.doc, one_step=True)
        fmt, evolved_doc = DocumentIO.load(
            resource_stream('linaro_dashboard_bundle',
                            'test_documents/evolution_1.2.json'),
            retain_order=False)
        self.assertEqual(self.doc, evolved_doc)


class DocumentEvolutionTests_1_2_to_1_3(TestCase):

    def setUp(self):
        super(DocumentEvolutionTests_1_2_to_1_3, self).setUp()
        self.fmt, self.doc = DocumentIO.load(
            resource_stream('linaro_dashboard_bundle',
                            'test_documents/evolution_1.2.json'),
            retain_order=False)

    def test_format_is_changed(self):
        self.assertEqual(self.doc["format"], "Dashboard Bundle Format 1.2")
        DocumentEvolution.evolve_document(self.doc, one_step=True)
        self.assertEqual(self.doc["format"], "Dashboard Bundle Format 1.3")

    def test_evolved_document_is_latest_format(self):
        self.assertFalse(DocumentEvolution.is_latest(self.doc))
        DocumentEvolution.evolve_document(self.doc, one_step=True)
        self.assertFalse(DocumentEvolution.is_latest(self.doc))

    def test_evolved_document_is_valid(self):
        DocumentEvolution.evolve_document(self.doc, one_step=True)
        self.assertEqual(DocumentIO.check(self.doc),
                         "Dashboard Bundle Format 1.3")

    def test_evolved_document_is_what_we_expect(self):
        DocumentEvolution.evolve_document(self.doc, one_step=True)
        fmt, evolved_doc = DocumentIO.load(
            resource_stream('linaro_dashboard_bundle',
                            'test_documents/evolution_1.3.json'),
            retain_order=False)
        self.assertEqual(self.doc, evolved_doc)


class DocumentEvolutionTests_1_3_to_1_4(TestCase):

    def setUp(self):
        super(DocumentEvolutionTests_1_3_to_1_4, self).setUp()
        self.fmt, self.doc = DocumentIO.load(
            resource_stream('linaro_dashboard_bundle',
                            'test_documents/evolution_1.3.json'),
            retain_order=False)

    def test_format_is_changed(self):
        self.assertEqual(self.doc["format"], "Dashboard Bundle Format 1.3")
        DocumentEvolution.evolve_document(self.doc, one_step=True)
        self.assertEqual(self.doc["format"], "Dashboard Bundle Format 1.4")

    def test_evolved_document_is_latest_format(self):
        self.assertFalse(DocumentEvolution.is_latest(self.doc))
        DocumentEvolution.evolve_document(self.doc, one_step=True)
        self.assertFalse(DocumentEvolution.is_latest(self.doc))

    def test_evolved_document_is_valid(self):
        DocumentEvolution.evolve_document(self.doc, one_step=True)
        self.assertEqual(DocumentIO.check(self.doc),
                         "Dashboard Bundle Format 1.4")

    def test_evolved_document_is_what_we_expect(self):
        DocumentEvolution.evolve_document(self.doc, one_step=True)
        fmt, evolved_doc = DocumentIO.load(
            resource_stream('linaro_dashboard_bundle',
                            'test_documents/evolution_1.4.json'),
            retain_order=False)
        self.assertEqual(self.doc, evolved_doc)


class DocumentEvolutionTests_1_4_to_1_5(TestCase):

    def setUp(self):
        super(DocumentEvolutionTests_1_4_to_1_5, self).setUp()
        self.fmt, self.doc = DocumentIO.load(
            resource_stream('linaro_dashboard_bundle',
                            'test_documents/evolution_1.4.json'),
            retain_order=False)

    def test_format_is_changed(self):
        self.assertEqual(self.doc["format"], "Dashboard Bundle Format 1.4")
        DocumentEvolution.evolve_document(self.doc, one_step=True)
        self.assertEqual(self.doc["format"], "Dashboard Bundle Format 1.5")

    def test_evolved_document_is_latest_format(self):
        self.assertFalse(DocumentEvolution.is_latest(self.doc))
        DocumentEvolution.evolve_document(self.doc, one_step=True)
        self.assertFalse(DocumentEvolution.is_latest(self.doc))

    def test_evolved_document_is_valid(self):
        DocumentEvolution.evolve_document(self.doc, one_step=True)
        self.assertEqual(DocumentIO.check(self.doc),
                         "Dashboard Bundle Format 1.5")

    def test_evolved_document_is_what_we_expect(self):
        DocumentEvolution.evolve_document(self.doc, one_step=True)
        fmt, evolved_doc = DocumentIO.load(
            resource_stream('linaro_dashboard_bundle',
                            'test_documents/evolution_1.5.json'),
            retain_order=False)
        self.assertEqual(self.doc, evolved_doc)


class DocumentEvolutionTests_1_5_to_1_6(TestCase):

    def setUp(self):
        super(DocumentEvolutionTests_1_5_to_1_6, self).setUp()
        self.fmt, self.doc = DocumentIO.load(
            resource_stream('linaro_dashboard_bundle',
                            'test_documents/evolution_1.5.json'),
            retain_order=False)

    def test_format_is_changed(self):
        self.assertEqual(self.doc["format"], "Dashboard Bundle Format 1.5")
        DocumentEvolution.evolve_document(self.doc, one_step=True)
        self.assertEqual(self.doc["format"], "Dashboard Bundle Format 1.6")

    def test_evolved_document_is_latest_format(self):
        self.assertFalse(DocumentEvolution.is_latest(self.doc))
        DocumentEvolution.evolve_document(self.doc, one_step=True)
        self.assertTrue(DocumentEvolution.is_latest(self.doc))

    def test_evolved_document_is_valid(self):
        DocumentEvolution.evolve_document(self.doc, one_step=True)
        self.assertEqual(DocumentIO.check(self.doc),
                         "Dashboard Bundle Format 1.6")

    def test_evolved_document_is_what_we_expect(self):
        DocumentEvolution.evolve_document(self.doc, one_step=True)
        fmt, evolved_doc = DocumentIO.load(
            resource_stream('linaro_dashboard_bundle',
                            'test_documents/evolution_1.6.json'),
            retain_order=False)
        self.assertEqual(self.doc, evolved_doc)


class DocumentEvolutionTests_1_6_to_1_7(TestCase):

    def setUp(self):
        super(DocumentEvolutionTests_1_6_to_1_7, self).setUp()
        self.fmt, self.doc = DocumentIO.load(
            resource_stream('linaro_dashboard_bundle',
                            'test_documents/evolution_1.6.json'),
            retain_order=False)

    def test_format_is_changed(self):
        self.assertEqual(self.doc["format"], "Dashboard Bundle Format 1.6")
        DocumentEvolution.evolve_document(self.doc, one_step=True)
        self.assertEqual(self.doc["format"], "Dashboard Bundle Format 1.7")

    def test_evolved_document_is_latest_format(self):
        self.assertFalse(DocumentEvolution.is_latest(self.doc))
        DocumentEvolution.evolve_document(self.doc, one_step=True)
        self.assertTrue(DocumentEvolution.is_latest(self.doc))

    def test_evolved_document_is_valid(self):
        DocumentEvolution.evolve_document(self.doc, one_step=True)
        self.assertEqual(DocumentIO.check(self.doc),
                         "Dashboard Bundle Format 1.7")

    def test_evolved_document_is_what_we_expect(self):
        DocumentEvolution.evolve_document(self.doc, one_step=True)
        fmt, evolved_doc = DocumentIO.load(
            resource_stream('linaro_dashboard_bundle',
                            'test_documents/evolution_1.7.json'),
            retain_order=False)
        self.assertEqual(self.doc, evolved_doc)
