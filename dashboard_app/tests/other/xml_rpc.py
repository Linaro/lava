# Copyright (C) 2010 Linaro Limited
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

"""
Unit tests of the Dashboard application
"""
import xmlrpclib

from django_testscenarios import TestCaseWithScenarios

from dashboard_app.dispatcher import (
        DjangoXMLRPCDispatcher,
        FaultCodes,
        xml_rpc_signature,
        )


class TestAPI(object):
    """
    Test API that gets exposed by the dispatcher for test runs.
    """

    @xml_rpc_signature()
    def ping(self):
        """
        Return "pong" message
        """
        return "pong"

    def echo(self, arg):
        """
        Return the argument back to the caller
        """
        return arg

    def boom(self, code, string):
        """
        Raise a Fault exception with the specified code and string
        """
        raise xmlrpclib.Fault(code, string)

    def internal_boom(self):
        """
        Raise a regular python exception (this should be hidden behind
        an internal error fault)
        """
        raise Exception("internal boom")


class DjangoXMLRPCDispatcherTestCase(TestCaseWithScenarios):

    def setUp(self):
        super(DjangoXMLRPCDispatcherTestCase, self).setUp()
        self.dispatcher = DjangoXMLRPCDispatcher()
        self.dispatcher.register_instance(TestAPI())

    def xml_rpc_call(self, method, *args):
        """
        Perform XML-RPC call on our internal dispatcher instance

        This calls the method just like we would have normally from our view.
        All arguments are marshaled and un-marshaled. XML-RPC fault exceptions
        are raised like normal python exceptions (by xmlrpclib.loads)
        """
        request = xmlrpclib.dumps(tuple(args), methodname=method)
        response = self.dispatcher._marshaled_dispatch(request)
        # This returns return value wrapped in a tuple and method name
        # (which we don't have here as this is a response message).
        return xmlrpclib.loads(response)[0][0]


class DjangoXMLRPCDispatcherTests(DjangoXMLRPCDispatcherTestCase):

    def test_standard_fault_code_for_missing_method(self):
        try:
            self.xml_rpc_call("method_that_hopefully_does_not_exist")
        except xmlrpclib.Fault as ex:
            self.assertEqual(
                    ex.faultCode,
                    FaultCodes.ServerError.REQUESTED_METHOD_NOT_FOUND)
        else:
            self.fail("Calling missing method did not raise an exception")

    def test_ping(self):
        retval = self.xml_rpc_call("ping")
        self.assertEqual(retval, "pong")

    def test_echo(self):
        self.assertEqual(self.xml_rpc_call("echo", 1), 1)
        self.assertEqual(self.xml_rpc_call("echo", "string"), "string")
        self.assertEqual(self.xml_rpc_call("echo", 1.5), 1.5)

    def test_boom(self):
        self.assertRaises(xmlrpclib.Fault,
                self.xml_rpc_call, "boom", 1, "str")


class DjangoXMLRPCDispatcherFaultCodeTests(DjangoXMLRPCDispatcherTestCase):

    scenarios = [
            ('method_not_found', {
                'method': "method_that_hopefully_does_not_exist",
                'faultCode': FaultCodes.ServerError.REQUESTED_METHOD_NOT_FOUND,
                }),
            ('internal_error', {
                'method': "internal_boom",
                'faultCode': FaultCodes.ServerError.INTERNAL_XML_RPC_ERROR,
                }),
            ]

    def test_standard_fault_codes(self):
        try:
            self.xml_rpc_call(self.method)
        except xmlrpclib.Fault as ex:
            self.assertEqual(ex.faultCode, self.faultCode)
        else:
            self.fail("Exception not raised")
