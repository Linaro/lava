import logging
import sys

from django.contrib.auth.models import AnonymousUser
from django.test import TestCase

from lava_common.decorators import nottest
from lava_scheduler_app.models import Device, DeviceType, TestJob
from lava_scheduler_app.tables import DeviceTable, visible_jobs_with_custom_sort
from lava_scheduler_app.tables_jobs import AllJobsTable
from lava_server.lavatable import LavaTable, LavaView

LOGGER = logging.getLogger()
LOGGER.level = logging.INFO  # change to DEBUG to see *all* output
LOGGER.addHandler(logging.StreamHandler(sys.stdout))

# pylint does not like TestCaseWithFactory


@nottest
class TestTable(LavaTable):
    pass


@nottest
class TestLengthTable(LavaTable):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.length = 50


class TestTestTable(TestCase):
    data = {}

    def test_default_length(self):
        table = TestTable(self.data)
        logging.debug("Creating an empty LavaTable")
        self.assertEqual(table.length, 25)

    def test_default_length_table(self):
        table = TestLengthTable(self.data)
        logging.debug("Creating a derived LavaTable")
        self.assertEqual(table.length, 50)

    def test_empty_data(self):
        table = TestTable(self.data)
        logging.debug("Testing preparation of search data on empty input")
        self.assertEqual(table.prepare_search_data(self.data), {})
        self.assertEqual(table.prepare_terms_data(self.data), {})
        self.assertEqual(table.prepare_times_data(self.data), {})


@nottest
class TestJobTable(AllJobsTable):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.length = 18


@nottest
class TestDeviceTable(DeviceTable):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.length = 8


@nottest
class TestDeviceView(LavaView):
    def get_queryset(self):
        return (
            Device.objects.select_related("device_type")
            .visible_by_user(AnonymousUser())
            .order_by("hostname")
        )


@nottest
class TestJobView(LavaView):
    def get_queryset(self):
        return visible_jobs_with_custom_sort(AnonymousUser())


class TestTestJobTable(TestCase):
    def test_default_length(self):
        table = TestJobTable([])
        self.assertEqual(table.length, 18)

    def test_shell_data(self):
        view = TestJobView(None)
        logging.debug("Testing with a View derived from FilteredSingleTableView")
        table = TestJobTable(view.get_table_data())
        self.assertEqual(table.prepare_search_data(view), {"search": []})
        self.assertEqual(table.prepare_terms_data(view), {"terms": {}})
        self.assertEqual(table.prepare_times_data(view), {"times": []})

    def test_shell_data_model(self):
        view = TestJobView(None, model=TestJob, table_class=TestJobTable)
        table = TestJobTable(view.get_table_data())
        logging.debug("Passing a model and table_class to get search data")
        proxied = {}
        for key, value in table.prepare_search_data(view).items():
            proxied[key] = []
            if isinstance(value, list):
                for item in value:
                    proxied[key].append(str(item))
        self.assertEqual(
            proxied,
            {
                "search": [
                    "Description",
                    "device",
                    "ID",
                    "requested_device_type",
                    "state",
                    "Sub ID",
                    "submitter",
                ]
            },
        )
        self.assertEqual(table.prepare_terms_data(view), {"terms": {}})
        self.assertEqual(
            table.prepare_times_data(view),
            {"times": ["End time (hours)", "Submit time (hours)"]},
        )


class TestPrefixJobTable(TestCase):
    prefix = "abc_"

    def test_prefix_support(self):
        view = TestJobView(None)
        logging.debug("Testing an unmodelled View with a prefix")
        table = TestJobTable(view.get_table_data(self.prefix), prefix=self.prefix)
        self.assertEqual(table.prepare_search_data(view), {self.prefix: []})
        self.assertEqual(table.prepare_terms_data(view), {self.prefix: {}})
        self.assertEqual(table.prepare_times_data(view), {self.prefix: []})

    def test_prefix_support_model(self):
        view = TestJobView(None, model=TestJob, table_class=TestJobTable)
        table = TestJobTable(view.get_table_data(self.prefix), prefix=self.prefix)
        logging.debug("Testing a view with a model and a prefix")
        proxied = {}
        for key, value in table.prepare_search_data(view).items():
            proxied[key] = []
            if isinstance(value, list):
                for item in value:
                    proxied[key].append(str(item))

        self.assertEqual(
            proxied,
            {
                self.prefix: [
                    "Description",
                    "device",
                    "ID",
                    "requested_device_type",
                    "state",
                    "Sub ID",
                    "submitter",
                ]
            },
        )
        self.assertEqual(table.prepare_terms_data(view), {self.prefix: {}})
        self.assertEqual(
            table.prepare_times_data(view),
            {self.prefix: ["End time (hours)", "Submit time (hours)"]},
        )


class TestForDeviceTable(TestCase):
    """
    Device table tests using LavaTable and LavaView
    The assert needs to use the verbose_name of the
    """

    def test_device_table(self):
        logging.debug("Testing with a View derived from LavaView")
        view = TestDeviceView(None)
        table = DeviceTable(view.get_table_data())
        self.assertEqual(table.prepare_search_data(view), {"search": []})
        self.assertEqual(table.prepare_terms_data(view), {"terms": {}})
        self.assertEqual(table.prepare_times_data(view), {"times": []})

    def test_device_table_model(self):
        view = TestDeviceView(None, model=Device, table_class=DeviceTable)
        table = DeviceTable(view.get_table_data())
        self.assertEqual(
            table.prepare_search_data(view),
            {"search": ["device_type", "health", "Hostname", "state", "tags"]},
        )
        self.assertEqual(table.prepare_terms_data(view), {"terms": {}})
        self.assertEqual(table.prepare_times_data(view), {"times": []})

    def test_device_table_prefix(self):
        view = TestDeviceView(None)
        prefix = "dt_"
        table = TestDeviceTable(view.get_table_data(prefix), prefix=prefix)
        self.assertEqual(table.prepare_search_data(view), {prefix: []})
        self.assertEqual(table.prepare_terms_data(view), {prefix: {}})
        self.assertEqual(table.prepare_times_data(view), {prefix: []})

    def test_device_table_model2(self):
        view = TestDeviceView(None, model=Device, table_class=TestDeviceTable)
        table = TestDeviceTable(view.get_table_data())
        self.assertEqual(
            table.prepare_search_data(view),
            {"search": ["device_type", "health", "Hostname", "state", "tags"]},
        )
        self.assertEqual(table.prepare_terms_data(view), {"terms": {}})
        self.assertEqual(table.prepare_times_data(view), {"times": []})


class TestHiddenDevicesInDeviceTable(TestCase):
    """
    Tests for the DeviceTable when it contains hidden
    device types
    """

    def test_device_table_view(self):
        device_type = DeviceType(name="generic")
        device_type.save()
        device = Device(device_type=device_type, hostname="generic1")
        device.save()
        view = TestDeviceView(None)
        self.assertEqual(len(view.get_queryset()), 1)
