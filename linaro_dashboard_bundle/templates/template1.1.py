import datetime
import uuid

from linaro_dashboard_bundle.schemas import format1_1 as schema
from linaro_json import document


class DashboardBundle(document.Template):

    __schema__ = schemas.DashboardBundle

    @property
    def format(self):
        return "Dashboard Bundle Format 1.1"

    @property
    def test_runs(self):
        return []


class TestRun(document.Template):

    __schema__ = schemas.TestRun

    @property
    def analyzer_assigned_uuid(self):
        return uuid.uuid1()

    @property
    def analyzer_assigned_date(self):
        return datetime.datetime.now()

    time_check_performed = False

    @property
    def test_results(self):
        return []
