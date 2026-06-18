# Copyright (C) 2019 Linaro Limited
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import logging
import sys
from uuid import uuid4

from django.contrib.auth.models import AnonymousUser
from django.http import HttpRequest
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
        TestTable(self.data)
        logging.debug("Testing preparation of search data on empty input")


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
        view = TestJobView(HttpRequest())
        logging.debug("Testing with a View derived from FilteredSingleTableView")
        TestJobTable(view.get_table_data())

    def test_shell_data_model(self):
        view = TestJobView(HttpRequest(), model=TestJob, table_class=TestJobTable)
        TestJobTable(view.get_table_data())


class TestPrefixJobTable(TestCase):
    prefix = "abc_"

    def test_prefix_support(self):
        view = TestJobView(HttpRequest())
        logging.debug("Testing an unmodelled View with a prefix")
        TestJobTable(view.get_table_data(self.prefix), prefix=self.prefix)

    def test_prefix_support_model(self):
        view = TestJobView(HttpRequest(), model=TestJob, table_class=TestJobTable)
        TestJobTable(view.get_table_data(self.prefix), prefix=self.prefix)
        logging.debug("Testing a view with a model and a prefix")


class TestForDeviceTable(TestCase):
    """
    Device table tests using LavaTable and LavaView
    The assert needs to use the verbose_name of the
    """

    def test_device_table(self):
        logging.debug("Testing with a View derived from LavaView")
        view = TestDeviceView(HttpRequest())
        DeviceTable(view.get_table_data())

    def test_device_table_model(self):
        view = TestDeviceView(HttpRequest(), model=Device, table_class=DeviceTable)
        DeviceTable(view.get_table_data())

    def test_device_table_prefix(self):
        view = TestDeviceView(HttpRequest())
        prefix = "dt_"
        TestDeviceTable(view.get_table_data(prefix), prefix=prefix)

    def test_device_table_model2(self):
        view = TestDeviceView(HttpRequest(), model=Device, table_class=TestDeviceTable)
        TestDeviceTable(view.get_table_data())


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
        view = TestDeviceView(HttpRequest())
        self.assertEqual(len(view.get_queryset()), 1)


class TestDeviceHealthTooltip(TestCase):
    """Tests for DeviceTable.render_health tooltip on latest_health_reason."""

    def _device(self, health, hostname="test-dev"):
        dt, _ = DeviceType.objects.get_or_create(name="generic")
        if hostname == "test-dev":
            hostname = f"test-dev-{uuid4().hex[:8]}"
        return Device.objects.create(
            device_type=dt,
            hostname=hostname,
            health=health,
            state=Device.STATE_IDLE,
        )

    def _table(self, devices):
        return TestDeviceTable(devices, prefix="devices_")

    def _render(self, record):
        return self._table([record]).render_health(record)

    def test_health_states(self):
        """Each health state renders correct badge + tooltip when annotated."""
        cases = [
            (Device.HEALTH_GOOD, "text-success", "Good", True),
            (Device.HEALTH_BAD, "text-danger", "Bad", True),
            (Device.HEALTH_MAINTENANCE, "text-warning", "Maintenance", True),
            (Device.HEALTH_UNKNOWN, "text-info", None, True),
            (Device.HEALTH_RETIRED, "text-muted", "Retired", True),
        ]
        for health, cls, label, has_tooltip in cases:
            d = self._device(health)
            d.latest_health_reason = "reason"
            result = self._render(d)
            self.assertIn(cls, result, f"{health}")
            if label:
                self.assertIn(label, result, f"{health}")
            if has_tooltip:
                self.assertIn('data-toggle="tooltip"', result, f"{health}")
            else:
                self.assertNotIn("data-toggle", result, f"{health}")

    def test_strips_html_from_reason(self):
        d = self._device(Device.HEALTH_BAD)
        d.latest_health_reason = '<script>alert("xss")</script> Bad boot'
        result = self._render(d)
        self.assertIn('data-toggle="tooltip"', result)
        self.assertNotIn("<script>", result)

    def test_no_annotation_no_tooltip(self):
        d = self._device(Device.HEALTH_BAD)
        result = self._render(d)
        self.assertIn("text-danger", result)
        self.assertNotIn("data-toggle", result)
