import datetime
import uuid

from linaro_dashboard_bundle import schemas
from linaro_json.document import DocumentTemplate


class DashboardBundle(DocumentTemplate):

    __schema__ = schemas.DashboardBundle

    @property
    def format(self):
        return "Dashboard Bundle Format 1.0.1"


class TestRun(DocumentTemplate):

    __schema__ = schemas.TestRun

    @property
    def analyzer_assigned_uuid(self):
        return uuid.uuid1()

    @property
    def analyzer_assigned_date(self):
        return datetime.datetime.now()

    time_check_performed = False
