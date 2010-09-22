"""
Module with non-database helper classes
"""
import datetime
import decimal
import uuid

from django.core.files.base import ContentFile

from launch_control.models import DashboardBundle
from launch_control.utils.json import (
    ClassRegistry,
    PluggableJSONDecoder,
    json,
)
from launch_control.utils.json.proxies.datetime import datetime_proxy
from launch_control.utils.json.proxies.decimal import DecimalProxy
from launch_control.utils.json.proxies.timedelta import timedelta_proxy
from launch_control.utils.json.proxies.uuid import UUIDProxy


class DocumentError(ValueError):
    """
    Document error is raised when JSON document is malformed in any way
    """
    def __init__(self, msg, cause=None):
        super(DocumentError, self).__init__(msg)
        self.cause = cause


class BundleDeserializer(object):
    """
    Helper class for de-serializing JSON bundle content into database models
    """
    def __init__(self):
        self.registry = ClassRegistry()
        self._register_proxies()

    def _register_proxies(self):
        self.registry.register_proxy(datetime.datetime, datetime_proxy)
        self.registry.register_proxy(datetime.timedelta, timedelta_proxy)
        self.registry.register_proxy(uuid.UUID, UUIDProxy)
        self.registry.register_proxy(decimal.Decimal, DecimalProxy)

    def deserialize(self, s_bundle):
        try:
            s_bundle.content.open('rb')
            json_text = s_bundle.content.read()
        finally:
            s_bundle.content.close()
        c_bundle = self.json_to_memory_model(json_text)
        self.memory_model_to_db_model(c_bundle, s_bundle)

    def json_to_memory_model(self, json_text):
        """
        Load a memory model (based on launch_control.models) from
        specified JSON text. Raises DocumentError on any exception.
        """
        try:
            return json.loads(
                json_text, cls=PluggableJSONDecoder,
                registry=self.registry, type_expr=DashboardBundle,
                parse_float=decimal.Decimal)
        except Exception as ex:
            raise DocumentError(
                "Unable to load document: {0}".format(ex), ex)

    def memory_model_to_db_model(self, c_bundle, s_bundle):
        """
        Translate a memory model to database model
        """
        from dashboard_app.models import (
            Attachment,
            HardwareDevice,
            NamedAttribute,
            SoftwarePackage,
            Test,
            TestCase,
            TestResult,
            TestRun,
        )
        # All variables prefixed with c_ refer to CLIENT SIDE models
        # All variables prefixed with s_ refer to SERVER SIDE models
        for c_test_run in c_bundle.test_runs:
            s_test, test_created = Test.objects.get_or_create(
                test_id = c_test_run.test_id)
            if test_created:
                s_test.save()
            s_test_run = TestRun.objects.create(
                bundle = s_bundle,
                test = s_test,
                analyzer_assigned_uuid = c_test_run.analyzer_assigned_uuid,
                analyzer_assigned_date = c_test_run.analyzer_assigned_date,
                time_check_performed = c_test_run.time_check_performed,
                sw_image_desc = (c_test_run.sw_context.sw_image.desc if
                                 c_test_run.sw_context and
                                 c_test_run.sw_context.sw_image else ""))
            s_test_run.save() # needed for foreign key models below
            # Software Context:
            if c_test_run.sw_context:
                for c_package in c_test_run.sw_context.packages:
                    s_package, package_created = SoftwarePackage.objects.get_or_create(
                        name=c_package.name, version=c_package.version)
                    if package_created:
                        s_package.save()
                    s_test_run.packages.add(s_package)
            # Hardware Context:
            if c_test_run.hw_context:
                for c_device in c_test_run.hw_context.devices:
                    s_device = HardwareDevice.objects.create(
                        device_type = c_device.device_type,
                        description = c_device.description)
                    s_device.save()
                    for name, value in c_device.attributes.iteritems():
                        s_device.attributes.create(name=name, value=value)
                    s_test_run.devices.add(s_device)
            # Test Results:
            for c_test_result in c_test_run.test_results:
                if c_test_result.test_case_id:
                    s_test_case, test_case_created = TestCase.objects.get_or_create(
                        test_case_id = c_test_result.test_case_id,
                        test = s_test_run.test,
                        defaults = {'units': c_test_result.units})
                    if test_case_created:
                        s_test_case.save()
                else:
                    s_test_case = None
                s_test_result = TestResult.objects.create(
                    test_run = s_test_run,
                    test_case = s_test_case,
                    result = self._translate_result_string(c_test_result.result),
                    measurement = c_test_result.measurement,
                    filename = c_test_result.log_filename,
                    lineno = c_test_result.log_lineno,
                    message = c_test_result.message,
                    timestamp = c_test_result.timestamp,
                    duration = c_test_result.duration)
                s_test_result.save() # needed for foreign key models below
                for name, value in c_test_result.attributes.iteritems():
                    s_test_result.attributes.create(
                        name=name, value=value)
            # Test Run Attachments
            for filename, lines in c_test_run.attachments.iteritems():
                s_attachment = s_test_run.attachments.create(content_filename=filename)
                s_attachment.save()
                s_attachment.content.save(
                    "attachment-{0}.txt".format(s_attachment.pk),
                    ContentFile("".join(lines).encode("UTF-8")))
            # Test Run Attributes
            for name, value in c_test_run.attributes.iteritems():
                s_test_run.attributes.create(
                    name=str(name), value=str(value))

    def _translate_result_string(self, result):
        """
        Translate result string used by client-side API to our internal
        database integer representing the same value.
        """
        from dashboard_app.models import TestResult
        try:
            return {
                "pass": TestResult.RESULT_PASS,
                "fail": TestResult.RESULT_FAIL,
                "skip": TestResult.RESULT_SKIP,
                "unknown": TestResult.RESULT_UNKNOWN
            }[result]
        except KeyError:
            raise DocumentError(
                "Unsupported value of test result {0!r)".format(result))
