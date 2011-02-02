"""
Module with non-database helper classes
"""

from django.core.files.base import ContentFile
from django.db import transaction
from linaro_dashboard_bundle import (
    DocumentIO,
    DocumentFormatError
)
from uuid import UUID
from linaro_json.extensions import datetime_extension, timedelta_extension


class IBundleFormatImporter(object):
    """
    Interface for bundle format importers.
    """

    def import_document(self, s_bundle, doc):
        """
        Import document in a supported format and tie it to the
        specified server side DashboardBundle model (s_bundle)

        :Discussion:
            Imports specified document in a supported format and tie it
            to the specified server side DashboardBundle model
            (s_bundle)

        :Return value:
            None

        :Exceptions raised:
            ValueError
            TypeError
            others (?)
        """
        raise NotImplementedError(self.import_document)


class BundleFormatImporter_1_0(IBundleFormatImporter):
    """
    IFormatImporter subclass capable of loading "Dashboard Bundle Format 1.0"
    """

    def import_document(self, s_bundle, doc):
        """
        Import specified bundle document into the database.
        """
        try:
            for c_test_run in doc.get("test_runs", []):
                s_test_run = self._import_test_run(c_test_run, s_bundle)
                #print "Imported test run:", s_test_run
        except Exception:
            #import logging
            #logging.exception("Exception while loading document")
            raise

    def _import_test_run(self, c_test_run, s_bundle):
        """
        Import TestRun
        """
        from dashboard_app.models import TestRun

        s_test = self._import_test(c_test_run)
        analyzer_assigned_uuid = UUID(c_test_run["analyzer_assigned_uuid"])
        s_test_run = TestRun.objects.create(
            bundle = s_bundle,
            test = s_test,
            analyzer_assigned_uuid = str(analyzer_assigned_uuid),
            analyzer_assigned_date = datetime_extension.from_json(
                # required by schema
                c_test_run["analyzer_assigned_date"]),
            time_check_performed = (
                # required by schema
                c_test_run["time_check_performed"]),
            sw_image_desc = self._get_sw_context(c_test_run).get(
                "sw_image", {}).get("desc", "")
        )
        s_test_run.save() # needed for foreign key models below
        self._import_test_results(c_test_run, s_test_run)
        self._import_packages(c_test_run, s_test_run)
        self._import_devices(c_test_run, s_test_run)
        self._import_attributes(c_test_run, s_test_run)
        self._import_attachments(c_test_run, s_test_run)
        return s_test_run

    def _import_test(self, c_test_run):
        """
        Import dashboard_app.models.Test into the database
        based on a client-side description of a TestRun
        """
        from dashboard_app.models import Test

        s_test, test_created = Test.objects.get_or_create(
            test_id = c_test_run["test_id"]) # required by schema
        if test_created:
            s_test.save()
        return s_test

    def _import_test_results(self, c_test_run, s_test_run):
        """
        Import TestRun.test_results
        """
        from dashboard_app.models import TestResult

        for c_test_result in c_test_run.get("test_results", []):
            s_test_case = self._import_test_case(
                c_test_result, s_test_run.test)
            timestamp = c_test_result.get("timestamp")
            if timestamp:
                timestamp = datetime_extension.from_json(timestamp)
            duration = c_test_result.get("duration", None)
            if duration:
                duration = timedelta_extension.from_json(duration)
            result = self._translate_result_string(c_test_result["result"])
            s_test_result = TestResult.objects.create(
                test_run = s_test_run,
                test_case = s_test_case,
                result = result,
                measurement = c_test_result.get("measurement", None),
                filename = c_test_result.get("log_filename", None),
                lineno = c_test_result.get("log_lineno", None),
                message = c_test_result.get("message", None),
                timestamp = timestamp,
                duration = duration,
            )
            s_test_result.save() # needed for foreign key models below
            self._import_attributes(c_test_result, s_test_result)

    def _import_test_case(self, c_test_result, s_test):
        """
        Import TestCase
        """
        if "test_case_id" not in c_test_result:
            return
        from dashboard_app.models import TestCase
        s_test_case, test_case_created = TestCase.objects.get_or_create(
            test = s_test,
            test_case_id = c_test_result["test_case_id"],
            defaults = {'units': c_test_result.get("units", "")})
        if test_case_created:
            s_test_case.save()
        return s_test_case

    def _import_packages(self, c_test_run, s_test_run):
        """
        Import TestRun.pacakges
        """
        from dashboard_app.models import SoftwarePackage

        for c_package in self._get_sw_context(c_test_run).get("packages", []):
            s_package, package_created = SoftwarePackage.objects.get_or_create(
                name=c_package["name"], # required by schema
                version=c_package["version"] # required by schema
            )
            if package_created:
                s_package.save()
            s_test_run.packages.add(s_package)

    def _import_devices(self, c_test_run, s_test_run):
        """
        Import TestRun.devices
        """
        from dashboard_app.models import HardwareDevice

        for c_device in self._get_hw_context(c_test_run).get("devices", []):
            s_device = HardwareDevice.objects.create(
                device_type = c_device["device_type"],
                description = c_device["description"]
            )
            s_device.save()
            self._import_attributes(c_device, s_device)
            s_test_run.devices.add(s_device)

    def _import_attributes(self, c_object, s_object):
        """
        Import attributes from any client-side object into any
        server-side object
        """
        for name, value in c_object.get("attributes", {}).iteritems():
            s_object.attributes.create(
                name=str(name), value=str(value))

    def _import_attachments(self, c_test_run, s_test_run):
        """
        Import TestRun.attachments
        """
        for filename, lines in c_test_run.get("attachments", {}).iteritems():
            s_attachment = s_test_run.attachments.create(
                content_filename=filename)
            s_attachment.save()
            s_attachment.content.save(
                "attachment-{0}.txt".format(s_attachment.pk),
                ContentFile("".join(lines).encode("UTF-8")))

    def _translate_result_string(self, result):
        """
        Translate result string used by client-side API to our internal
        database integer representing the same value.
        """
        from dashboard_app.models import TestResult
        return {
            "pass": TestResult.RESULT_PASS,
            "fail": TestResult.RESULT_FAIL,
            "skip": TestResult.RESULT_SKIP,
            "unknown": TestResult.RESULT_UNKNOWN
        }[result]

    def _get_sw_context(self, c_test_run):
        return c_test_run.get("sw_context", {})

    def _get_hw_context(self, c_test_run):
        return c_test_run.get("hw_context", {})


class BundleFormatImporter_1_0_1(BundleFormatImporter_1_0):
    """
    IFormatImporter subclass capable of loading "Dashboard Bundle Format 1.0.1"
    """

    def _get_sw_context(self, c_test_run):
        return c_test_run.get("software_context", {})

    def _get_hw_context(self, c_test_run):
        return c_test_run.get("hardware_context", {})


class BundleFormatImporter_1_1(BundleFormatImporter_1_0_1):
    """
    IFormatImporter subclass capable of loading "Dashboard Bundle Format 1.1"
    """

    def _import_test_run(self, c_test_run, s_bundle):
        """
        Import TestRun
        """
        s_test_run = super(BundleFormatImporter_1_1, self)._import_test_run(
            c_test_run, s_bundle)
        self._import_sources(c_test_run, s_test_run)
        return s_test_run

    def _import_sources(self, c_test_run, s_test_run):
        """
        Import TestRun.sources
        """
        from dashboard_app.models import SoftwareSource

        for c_source in self._get_sw_context(c_test_run).get("sources", []):
            s_source, source_created = SoftwareSource.objects.get_or_create(
                project_name = c_source["project_name"], # required by schema
                branch_url = c_source["branch_url"], # required by schema
                branch_vcs = c_source["branch_vcs"], # required by schema
                # required by schema, may be either int or string so upconvert to string
                branch_revision = str(c_source["branch_revision"]),
                # optional
                commit_timestamp = (
                    datetime_extension.from_json(
                        c_source["commit_timestamp"])
                    if "commit_timestamp" in c_source
                    else None)
            )
            if source_created:
                s_source.save()
            s_test_run.sources.add(s_source)



class BundleDeserializer(object):
    """
    Helper class for de-serializing JSON bundle content into database models
    """

    IMPORTERS = {
        "Dashboard Bundle Format 1.0": BundleFormatImporter_1_0,
        "Dashboard Bundle Format 1.0.1": BundleFormatImporter_1_0_1,
        "Dashboard Bundle Format 1.1": BundleFormatImporter_1_1,
    }

    @transaction.commit_on_success
    def deserialize(self, s_bundle):
        """
        Deserializes specified Bundle.

        :Discussion:
            This method also handles internal transaction handling.
            All operations performed during bundle deserialization are
            _rolled_back_ if anything fails.

        :Exceptions raised:
            linaro_json.ValidationError
                When the document does not match the appropriate schema.
            linaro_dashboard_bundle.errors.DocumentFormatError
                When the document format is not in the known set of formats.
            ValueError
                When the text does not represent a correct JSON document.
        """
        s_bundle.content.open('rb')
        try:
            fmt, doc = DocumentIO.load(s_bundle.content)
        except:
            #import logging
            #logging.exception("Exception while deserializing JSON document")
            raise
        finally:
            s_bundle.content.close()
        importer = self.IMPORTERS.get(fmt)
        if importer is None:
            raise DocumentFormatError(fmt)
        importer().import_document(s_bundle, doc)
