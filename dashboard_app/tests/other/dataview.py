# Copyright (C) 2011 Linaro Limited
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
#
# This file is part of Launch Control.
#
# Launch Control is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# Launch Control is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Launch Control.  If not, see <http://www.gnu.org/licenses/>.

from mocker import Mocker, expect
from testtools import TestCase

from dashboard_app.models import DataView


class DataViewHandlerTests(TestCase):

    text = """
    <data-view name="foo">
        <documentation>
        Simple dataview that selects all bundle streams
        </documentation>
        <summary>List all bundle streams</summary>
        <sql backend="sqlite">
            SELECT *
            FROM dashboard_app_bundlestreams
            ORDER BY <value name="order_by"/>
        </sql>
        <arguments>
            <argument name="order_by" default="pathname" type="string" help="sorting order"/>
        </arguments>
    </data-view>
    """

    def setUp(self):
        super(DataViewHandlerTests, self).setUp()
        self.dataview = DataView.repository.load_from_xml_string(self.text) 

    def test_name_parsed_ok(self):
        self.assertEqual(self.dataview.name, "foo")

    def test_documentation_parsed_ok(self):
        self.assertEqual(
            self.dataview.documentation,
            "Simple dataview that selects all bundle streams")

    def test_summary_parsed_ok(self):
        self.assertEqual(self.dataview.summary, "List all bundle streams")

    def test_sql_parsed_ok(self):
        self.assertTrue("sqlite" in self.dataview.backend_queries)
        backend_query = self.dataview.backend_queries["sqlite"]
        self.assertEqual(backend_query.backend, "sqlite")
        self.assertEqual(
            backend_query.sql_template,
            "SELECT * FROM dashboard_app_bundlestreams ORDER BY {order_by}")
        self.assertEqual(backend_query.argument_list, ["order_by"])

    def test_arguments_parsed_ok(self):
        self.assertEqual(len(self.dataview.arguments), 1)
        arg = self.dataview.arguments[0]
        self.assertEqual(arg.name, "order_by")
        self.assertEqual(arg.default, "pathname")
        self.assertEqual(arg.type, "string")
        self.assertEqual(arg.help, "sorting order")


class DataViewConnectionTests(TestCase):

    def test_get_connection_without_sandbox(self):
        # Mock connections['dataview'] to raise ConnectionDoesNotExist
        from django.db.utils import ConnectionDoesNotExist
        mocker = Mocker()
        connections = mocker.replace("django.db.connections")
        expect(connections['dataview']).throw(ConnectionDoesNotExist)
        connection = mocker.replace("django.db.connection")
        logging = mocker.replace("logging")
        logging.warning("dataview-specific database connection not available, dataview query is NOT sandboxed")
        with mocker:
            observed = DataView.get_connection()
            expected = connection
            self.assertIs(observed, expected)

    def test_get_connection_with_sandbox(self):
        """
        Test for DataView.get_connection()
        """
        # Mock connections['dataview'] to return special connection 
        mocker = Mocker()
        connections = mocker.replace("django.db.connections")
        special_connection = mocker.mock()
        expect(connections['dataview']).result(special_connection)
        with mocker:
            observed = DataView.get_connection()
            expected = special_connection
            self.assertIs(observed, expected)
