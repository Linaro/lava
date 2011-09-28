"""
Module with non-database helper classes
"""

from uuid import UUID
import base64
import logging
import time

from django.core.files.base import ContentFile
from django.db import connection, transaction, IntegrityError
from linaro_dashboard_bundle.errors import DocumentFormatError
from linaro_dashboard_bundle.evolution import DocumentEvolution
from linaro_dashboard_bundle.io import DocumentIO
from linaro_json.extensions import datetime_extension, timedelta_extension


PROFILE_LOGGING = False


def is_postgres():
    return (connection.settings_dict['ENGINE']
            == 'django.db.backends.postgresql_psycopg2')


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
        self._content_files = []
        self._import_sanity_check(doc)
        try:
            self._import_document_with_transaction(s_bundle, doc)
        except IntegrityError:
            self._remove_created_files()
            raise

    def _remove_created_files(self):
        """
        Remove any files that may have already been flushed to disk. Otherwise
        the transaction handling should rollback anything evil that was
        happening while we were here
        """
        for content_file in self._content_files:
            content_file.delete(save=False)

    def _import_sanity_check(self, doc):
        """
        Sanity check before any import is attempted.

        This prevents InternalError (but is racy with other transactions).
        Still it's a little bit better to report the exception raised below
        rather than the IntegrityError that would have been raised otherwise.

        The code copes with both (using transactions around _import_document()
        and _remove_created_files() that gets called if something is wrong)
        """
        from dashboard_app.models import TestRun

        for test_run in doc.get("test_runs", []):
            analyzer_assigned_uuid = test_run["analyzer_assigned_uuid"]
            if TestRun.objects.filter(
                analyzer_assigned_uuid=analyzer_assigned_uuid).exists():
                raise ValueError("A test with UUID {0} already exists".format(analyzer_assigned_uuid))

    @transaction.commit_on_success
    def _import_document_with_transaction(self, s_bundle, doc):
        """
        Note: This function uses commit_on_success to ensure the database is in
        a consistent state after IntegrityErrors that would clog the
        transaction on pgsql. Since transactions will not rollback any files we
        created in the meantime there is a helper that cleans attachments in
        case something goes wrong
        """
        self._import_document(s_bundle, doc)

    def _import_document(self, s_bundle, doc):
        for c_test_run in doc.get("test_runs", []):
            self._import_test_run(c_test_run, s_bundle)

    def __init__(self):
        self._qc = 0
        self._time = time.time()

    def _log(self, method_name):
        if PROFILE_LOGGING:
            t = time.time() - self._time
            if t > 0.1:
                p = '**'
            else:
                p = '  '
            logging.warning(
                '%s %s %.2f %d', p, method_name, t,
                len(connection.queries) - self._qc)
            self._qc = len(connection.queries)
            self._time = time.time()

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
        )
        # needed for foreign key models below
        s_test_run.save()
        # import all the bits and pieces
        self._log('starting')
        self._import_test_results(c_test_run, s_test_run)
        self._log('results')
        self._import_attachments(c_test_run, s_test_run)
        self._log('attachments')
        self._import_hardware_context(c_test_run, s_test_run)
        self._log('hardware')
        self._import_software_context(c_test_run, s_test_run)
        self._log('software')
        self._import_attributes(c_test_run, s_test_run)
        self._log('attributes')
        # collect all the changes that happen before the previous save
        s_test_run.save()
        s_test_run.denormalize()
        return s_test_run

    def _import_software_context(self, c_test_run, s_test_run):
        """
        Import software context.

        In format 1.0 that's just a list of packages and software image
        description
        """
        self._import_packages(c_test_run, s_test_run)
        s_test_run.sw_image_desc = self._get_sw_context(c_test_run).get(
                "sw_image", {}).get("desc", "")

    def _import_hardware_context(self, c_test_run, s_test_run):
        """
        Import hardware context.

        In format 1.0 that's just a list of devices
        """
        self._import_devices(c_test_run, s_test_run)

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

    def _import_test_results_sqlite(self, c_test_results, s_test_run):
        cursor = connection.cursor()

        # XXX I don't understand how the _order column that Django adds is
        # supposed to work.  I just set it to 0 here.

        data = []

        for index, c_test_result in enumerate(c_test_results, 1):

            timestamp = c_test_result.get("timestamp")
            if timestamp:
                timestamp = datetime_extension.from_json(timestamp)
            duration = c_test_result.get("duration", None)
            if duration:
                duration = timedelta_extension.from_json(duration)
                duration = (duration.microseconds +
                            (duration.seconds * 10 ** 6) +
                            (duration.days * 24 * 60 * 60 * 10 ** 6))
            result = self._translate_result_string(c_test_result["result"])

            data.append((
                s_test_run.id,
                index,
                timestamp,
                duration,
                c_test_result.get("log_filename", None),
                result,
                c_test_result.get("measurement", None),
                c_test_result.get("message", None),
                c_test_result.get("log_lineno", None),
                s_test_run.test.id,
                c_test_result.get("test_case_id", None),
                ))

        cursor.executemany(
            """
            INSERT INTO dashboard_app_testresult (
                test_run_id,
                relative_index,
                timestamp,
                microseconds,
                filename,
                result,
                measurement,
                message,
                lineno,
                _order,
                test_case_id
            ) select
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                0,
                dashboard_app_testcase.id
                FROM dashboard_app_testcase
                  WHERE dashboard_app_testcase.test_id = %s
                    AND dashboard_app_testcase.test_case_id
                      = %s
            """, data)

        cursor.close()

    def _import_test_results_pgsql(self, c_test_results, s_test_run):
        cursor = connection.cursor()

        # XXX I don't understand how the _order column that Django adds is
        # supposed to work.  I just let it default to 0 here.

        data = []

        for i in range(0, len(c_test_results), 1000):

            cursor.execute(
                """
                CREATE TEMPORARY TABLE newtestresults (
                    relative_index INTEGER,
                    timestamp      TIMESTAMP WITH TIME ZONE,
                    microseconds   BIGINT,
                    filename       TEXT,
                    result         SMALLINT,
                    measurement    NUMERIC(20,10),
                    message        TEXT,
                    test_case_id   TEXT,
                    lineno         INTEGER
                    )
                """)

            data = []

            for index, c_test_result in enumerate(c_test_results[i:i+1000], i+1):

                timestamp = c_test_result.get("timestamp")
                if timestamp:
                    timestamp = datetime_extension.from_json(timestamp)
                duration = c_test_result.get("duration", None)
                if duration:
                    duration = timedelta_extension.from_json(duration)
                    duration = (duration.microseconds +
                                (duration.seconds * 10 ** 6) +
                                (duration.days * 24 * 60 * 60 * 10 ** 6))
                result = self._translate_result_string(c_test_result["result"])

                data.extend([
                    index,
                    timestamp,
                    duration,
                    c_test_result.get("log_filename", None),
                    result,
                    c_test_result.get("measurement", None),
                    c_test_result.get("message", None),
                    c_test_result.get("test_case_id", None),
                    c_test_result.get("log_lineno", None),
                    ])

            sequel = ',\n'.join(
                ["(" + "%s" % (', '.join(['%s']*9),) + ")"] * (len(data) // 9))

            cursor.execute(
                """
                INSERT INTO newtestresults (
                    relative_index,
                    timestamp,
                    microseconds,
                    filename,
                    result,
                    measurement,
                    message,
                    test_case_id,
                    lineno
                ) VALUES """ + sequel, data)

            cursor.execute(
                """
                INSERT INTO dashboard_app_testresult (
                    test_run_id,
                    relative_index,
                    timestamp,
                    microseconds,
                    filename,
                    result,
                    measurement,
                    message,
                    test_case_id,
                    lineno
                ) SELECT
                    %s,
                    relative_index,
                    timestamp,
                    microseconds,
                    filename,
                    result,
                    measurement,
                    message,
                    dashboard_app_testcase.id,
                    lineno
                    FROM newtestresults, dashboard_app_testcase
                      WHERE dashboard_app_testcase.test_id = %s
                        AND dashboard_app_testcase.test_case_id
                          = newtestresults.test_case_id
                """ % (s_test_run.id, s_test_run.test.id))

            cursor.execute(
                """
                DROP TABLE newtestresults
                """)

        cursor.close()

    def _import_test_results(self, c_test_run, s_test_run):
        """
        Import TestRun.test_results
        """
        from dashboard_app.models import TestResult

        c_test_results = c_test_run.get("test_results", [])

        if not c_test_results:
            return

        if is_postgres():
            self._import_test_cases_pgsql(c_test_results, s_test_run.test)
        else:
            self._import_test_cases_sqlite(c_test_results, s_test_run.test)

        if is_postgres():
            self._import_test_results_pgsql(c_test_results, s_test_run)
        else:
            self._import_test_results_sqlite(c_test_results, s_test_run)

        for index, c_test_result in enumerate(c_test_run.get("test_results", []), 1):
            if c_test_result.get("attributes", {}):
                s_test_result = TestResult.objects.get(
                    relative_index=index, test_run=s_test_run)
                self._import_attributes(c_test_result, s_test_result)
        self._log('test result attributes')

    def _import_test_cases_sqlite(self, c_test_results, s_test):
        """
        Import TestCase
        """
        id_units = []
        for c_test_result in c_test_results:
            if "test_case_id" not in c_test_result:
                continue
            id_units.append(
                (c_test_result["test_case_id"],
                 c_test_result.get("units", "")))

        cursor = connection.cursor()

        data = []
        for (test_case_id, units) in id_units:
            data.append((s_test.id, units, test_case_id))
        cursor.executemany(
            """
            INSERT OR IGNORE INTO
                dashboard_app_testcase (test_id, units, name, test_case_id)
            VALUES (%s, %s, '', %s)
            """, data)
        cursor.close()

    def _import_test_cases_pgsql(self, c_test_results, s_test):
        """
        Import TestCase
        """
        id_units = {}
        for c_test_result in c_test_results:
            if "test_case_id" not in c_test_result:
                continue
            id_units.setdefault(
                c_test_result["test_case_id"], c_test_result.get("units", ""))
        id_units = id_units.items()

        cursor = connection.cursor()
        for i in range(0, len(id_units), 1000):

            cursor.execute(
                """
                CREATE TEMPORARY TABLE
                    newtestcases (test_case_id text, units text)
                """)
            data = []
            for (id, units) in id_units[i:i+1000]:
                data.append(id)
                data.append(units)
            sequel = ',\n'.join(["(%s, %s)"] * (len(data) // 2))
            cursor.execute(
                """
                INSERT INTO newtestcases (test_case_id, units) VALUES
                """ + sequel, data)

            cursor.execute(
                """
                INSERT INTO
                    dashboard_app_testcase (test_id, units, name, test_case_id)
                SELECT %s, units, E'', test_case_id FROM newtestcases
                WHERE NOT EXISTS (SELECT 1 FROM dashboard_app_testcase
                                  WHERE test_id = %s
                                    AND newtestcases.test_case_id
                                      = dashboard_app_testcase.test_case_id)
                """ % (s_test.id, s_test.id))
            cursor.execute(
                """
                drop table newtestcases
                """)
        cursor.close()

    def _import_packages_scratch_sqlite(self, cursor, packages):
        data = []
        for c_package in packages:
            data.append((c_package['name'], c_package['version']))
        cursor.executemany(
            """
            INSERT INTO dashboard_app_softwarepackagescratch
                   (name, version) VALUES (%s, %s)
            """, data)

    def _import_packages_scratch_pgsql(self, cursor, packages):
        for i in range(0, len(packages), 1000):
            data = []
            for c_package in packages[i:i+1000]:
                data.append(c_package['name'])
                data.append(c_package['version'])
            sequel = ', '.join(["(%s, %s)"] * (len(data) // 2))
            cursor.execute(
                "INSERT INTO dashboard_app_softwarepackagescratch (name, version) VALUES " + sequel, data)

    def _import_packages(self, c_test_run, s_test_run):
        """
        Import TestRun.pacakges
        """
        packages = self._get_sw_context(c_test_run).get("packages", [])
        if not packages:
            return
        cursor = connection.cursor()

        if is_postgres():
            self._import_packages_scratch_pgsql(cursor, packages)
        else:
            self._import_packages_scratch_sqlite(cursor, packages)

        cursor.execute(
            """
            INSERT INTO dashboard_app_softwarepackage (name, version)
            SELECT name, version FROM dashboard_app_softwarepackagescratch
            EXCEPT SELECT name, version FROM dashboard_app_softwarepackage
            """)
        cursor.execute(
            """
            INSERT INTO
                dashboard_app_testrun_packages (testrun_id, softwarepackage_id)
            SELECT %s, id FROM dashboard_app_softwarepackage
                WHERE EXISTS (
                    SELECT * FROM dashboard_app_softwarepackagescratch
                        WHERE dashboard_app_softwarepackage.name
                            = dashboard_app_softwarepackagescratch.name
                          AND dashboard_app_softwarepackage.version
                            = dashboard_app_softwarepackagescratch.version)
            """ % s_test_run.id)
        cursor.execute(
            """
            delete from dashboard_app_softwarepackagescratch
            """)
        cursor.close()

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
                mime_type="text/plain",
                content_filename=filename)
            s_attachment.save()
            s_attachment.content.save(
                "attachment-{0}.txt".format(s_attachment.pk),
                ContentFile("".join(lines).encode("UTF-8")))
            # Collect this attachment for cleanup in case something goes wrong
            # and we need to rollback the transaction
            self._content_files.append(s_attachment)

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

    def _import_software_context(self, c_test_run, s_test_run):
        """
        Import software context in 1.1 format.

        Note: We're not upcalling super here as the second line importing
        software image name is quite different in the previous format and I did
        not want to create another function for that. Copying the frozen
        implementation from previous format is IMHO cleaner.
        """
        self._import_packages(c_test_run, s_test_run)
        s_test_run.sw_image_desc = self._get_sw_context(c_test_run).get(
                "image", {}).get("name", "")
        self._import_sources(c_test_run, s_test_run)

    def _import_attachments(self, c_test_run, s_test_run):
        """
        Import TestRun.attachments
        """
        for c_attachment in c_test_run.get("attachments", []):
            s_attachment = s_test_run.attachments.create(
                content_filename = c_attachment["pathname"],
                mime_type = c_attachment["mime_type"])
            # Save to get pk
            s_attachment.save()
            content = base64.standard_b64decode(c_attachment["content"])
            s_attachment.content.save(
                "attachment-{0}.txt".format(s_attachment.pk),
                ContentFile(content))

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


class BundleFormatImporter_1_2(BundleFormatImporter_1_1):
    """
    IFormatImporter subclass capable of loading "Dashboard Bundle Format 1.2"
    """

    def _import_attachments(self, c_test_run, s_test_run):
        """
        Import TestRun.attachments
        """
        for c_attachment in c_test_run.get("attachments", []):
            s_attachment = s_test_run.attachments.create(
                content_filename = c_attachment["pathname"],
                public_url = c_attachment.get("public_url", ""),
                mime_type = c_attachment["mime_type"])
            s_attachment.save()
            if "content" in c_attachment:
                # Content is optional now
                content = base64.standard_b64decode(c_attachment["content"])
                s_attachment.content.save(
                    "attachment-{0}.txt".format(s_attachment.pk),
                    ContentFile(content))


class BundleFormatImporter_1_3(BundleFormatImporter_1_2):
    """
    IFormatImporter subclass capable of loading "Dashboard Bundle Format 1.3"
    """

    def _import_test_run(self, c_test_run, s_bundle):
        from dashboard_app.models import Tag

        s_test_run = super(BundleFormatImporter_1_3, self)._import_test_run(c_test_run, s_bundle)
        self._log('tags')
        for c_tag in c_test_run.get("tags", []):
            s_tag, created = Tag.objects.get_or_create(name=c_tag)
            if created:
                s_tag.save()
            s_test_run.tags.add(s_tag)
        return s_test_run


class BundleDeserializer(object):
    """
    Helper class for de-serializing JSON bundle content into database models
    """

    IMPORTERS = {
        "Dashboard Bundle Format 1.0": BundleFormatImporter_1_0,
        "Dashboard Bundle Format 1.0.1": BundleFormatImporter_1_0_1,
        "Dashboard Bundle Format 1.1": BundleFormatImporter_1_1,
        "Dashboard Bundle Format 1.2": BundleFormatImporter_1_2,
        "Dashboard Bundle Format 1.3": BundleFormatImporter_1_3,
    }

    def deserialize(self, s_bundle, prefer_evolution):
        """
        Deserializes specified Bundle.

        :Discussion:
            This method also handles internal transaction handling.
            All operations performed during bundle deserialization are
            _rolled_back_ if anything fails.

            If prefer_evolution is enabled then the document is first evolved
            to the latest known format and only then imported into the
            database. This operation is currently disabled to ensure that all
            old documents are imported exactly as before. Enabling it should
            be quite safe though as it passes all tests.

        :Exceptions raised:
            linaro_json.ValidationError
                When the document does not match the appropriate schema.
            linaro_dashboard_bundle.errors.DocumentFormatError
                When the document format is not in the known set of formats.
            ValueError
                When the text does not represent a correct JSON document.
        """
        assert s_bundle.is_deserialized is False
        s_bundle.content.open('rb')
        try:
            logging.debug("Loading document")
            fmt, doc = DocumentIO.load(s_bundle.content)
            logging.debug("Document loaded")
            if prefer_evolution:
                logging.debug("Evolving document")
                DocumentEvolution.evolve_document(doc)
                logging.debug("Document evolution complete")
                fmt = doc["format"]
        finally:
            s_bundle.content.close()
        importer = self.IMPORTERS.get(fmt)
        if importer is None:
            raise DocumentFormatError(fmt)
        try:
            logging.debug("Importing document")
            importer().import_document(s_bundle, doc)
            logging.debug("Document import complete")
        except Exception as exc:
            logging.debug("Exception while importing document: %r", exc)
            raise
