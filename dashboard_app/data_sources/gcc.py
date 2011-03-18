from django.db import connection
from linaro_json.schema import Schema, Validator


class SQLBuilder(object):

    def __init__(self):
        self.sql = ""
        self.var_list = []

    def append(self, sql, *var_list):
        self.sql += sql
        self.var_list.extend(var_list)

    def result(self):
        return self.sql, self.var_list


class DataSourceBase(object):

    def __init__(self, config):
        config_schema = Schema(self.get_config_schema())
        Validator.validate(config_schema, config)
        self.config = config

    @classmethod
    def get_config_schema(cls):
        return getattr(cls, "config_schema", {})

    def get_data(self):
        return list(self._gen_data())

    def _gen_data(self):
        cursor = connection.cursor()
        cursor.execute(*self._to_sql_and_var_list())
        return cursor.fetchall()

    def _to_sql_and_var_list(self):
        raise NotImplementedError


class AvailableAttributeValues(DataSourceBase):

    def __init__(self, attr_name):
        self.attr_name = attr_name

    def _to_sql_and_var_list(self):
        sql = """
        SELECT DISTINCT value FROM dashboard_app_namedattribute
        WHERE content_type_id = (
            SELECT id FROM django_content_type
            WHERE app_label = 'dashboard_app'
            AND model = 'testrun'
        )
        AND name=%s
        ORDER BY value
        """
        sql_var_list = [self.attr_name]
        return sql, sql_var_list


class AvailableCompilerValues(DataSourceBase):

    # TODO confirm this with Michael Hope, add Code Sourcery compiler

    config_schema = {
        "type": "null"
    }

    def get_data(self):
        return ['gcc-linaro', 'gcc']

    def _gen_data(self):
        raise NotImplementedError


class Benchmark(DataSourceBase):
    """
    Data source for tapping into benchmark producing multiple values for
    each run and having specific values of custom attributes.

    This data source produces a sequence of tuples:
        (commit_timestamp_javascript, measurement, test_result_id)

    Out of test results that:
        - belong to a specific bundle stream (required)
        - belong to specific test and test case (required)
        - have a reference to source project "project_name" (optionally)
        - have the source project use a specific branch (optionally)
        - have any combination of custom attributes _at test run level_
          (optionally)
    """

    config_schema = {
        "type": "object",
        "properties": {
            "bundle_stream_pathname": {
                "type": "string"
            },
            "test_id": {
                "type": "string"
            },
            "test_case_id": {
                "type": "string"
            },
            "project_name": {
                "type": "string",
                "optional": True
            },
            "branch_url": {
                "type": "string",
                "optional": True
            },
            "custom_attrs": {
                "type": "object",
                "optional": True,
                "additionalProperties": {
                    "type": "string"
                }
            }
        },
        "additionalProperties": False
    }


    def _get_commit_timestamp_sql(self):
        if "postgresql" in str(type(connection)):
            return """
            CAST(
                (EXTRACT(EPOCH FROM commit_timestamp)) * 1000 AS BIGINT
            ) AS commit_timestamp_javascript,
            """
        elif "sqlite" in str(type(connection)):
            return """
            CAST(
                strftime('%%s', commit_timestamp) * 1000 AS INTEGER
            ) AS commit_timestamp_javascript,
            """
        else:
            raise NotImplementedError

    def _to_sql_and_var_list(self):
        sql = SQLBuilder()
        sql.append(
            """
            SELECT
            """
            + self._get_commit_timestamp_sql() +
            """
                measurement,
                dashboard_app_testresult.id
            FROM
                dashboard_app_testresult,
                dashboard_app_softwaresource,
                dashboard_app_testrun_sources
            WHERE
                dashboard_app_testresult.test_run_id IN (
                    SELECT
                        dashboard_app_testrun.id
                    FROM
                        dashboard_app_testrun,
                        dashboard_app_bundle
                    WHERE
                        dashboard_app_testrun.bundle_id = dashboard_app_bundle.id
                        AND dashboard_app_bundle.bundle_stream_id = (
                            SELECT dashboard_app_bundlestream.id
                            FROM dashboard_app_bundlestream
                            WHERE dashboard_app_bundlestream.pathname = %s
                        )
                )
                AND dashboard_app_testresult.test_run_id = dashboard_app_testrun_sources.testrun_id
                AND dashboard_app_testrun_sources.softwaresource_id = dashboard_app_softwaresource.id
            """,
            self.config["bundle_stream_pathname"]
        )

        # Filter by project name if needed
        project_name = self.config.get("project_name")
        if project_name is not None:
            sql.append(
                "AND dashboard_app_softwaresource.project_name = %s ",
                project_name
            )

        # Filter by branch URL if needed
        branch_url = self.config.get("branch_url")
        if branch_url is not None:
            sql.append(
                "AND dashboard_app_softwaresource.branch_url = %s ",
                branch_url
            )

        sql.append(
            """
            AND dashboard_app_testresult.test_case_id = (
                SELECT dashboard_app_testcase.id FROM dashboard_app_testcase
                WHERE dashboard_app_testcase.test_case_id = %s
                AND dashboard_app_testcase.test_id = (
                    SELECT dashboard_app_test.id FROM dashboard_app_test
                    WHERE dashboard_app_test.test_id = %s
                )
            )
            """,
            self.config.get("test_case_id"), self.config.get("test_id")
        )

        custom_attrs = self.config.get("custom_attrs", {})

        if custom_attrs:
            sql.append(" AND dashboard_app_testresult.test_run_id IN (")
            for index0, (name, value) in enumerate(custom_attrs.iteritems()):
                if index0 > 0:
                    sql.append(" INTERSECT ")
                sql.append(
                    """
                    SELECT object_id FROM dashboard_app_namedattribute
                    WHERE content_type_id = (
                        SELECT id FROM django_content_type
                        WHERE app_label = 'dashboard_app' AND model = 'testrun'
                    )
                    AND name = %s
                    AND value = %s
                    """,
                    name, value
                )
            sql.append(")")
        sql.append("ORDER BY commit_timestamp_javascript")
        return sql.result()
