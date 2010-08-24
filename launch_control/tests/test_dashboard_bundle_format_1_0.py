"""
Module with unit tests for launch_control.models package
"""

from unittest import TestCase

from launch_control.models import (
        DashboardBundle,
        HardwareContext,
        HardwareDevice,
        SoftwareContext,
        SoftwareImage,
        SoftwarePackage,
        TestCase,
        TestResult,
        TestRun,
        )


class DashboardBundleTests(TestCase):

    def test_format(self):
        self.assertEqual(DashboardBundle.FORMAT, "Dashboard Bundle Format 1.0")

    def test_construction_1(self):
        bundle = DashboardBundle()
        self.assertEqual(bundle.format, DashboardBundle.FORMAT)
        self.assertEqual(bundle.test_runs, [])

    def test_construction_2(self):
        test_runs = object()
        bundle = DashboardBundle(test_runs=test_runs)
        self.assertEqual(bundle.test_runs, test_runs)

    def test_get_json_attr_types(self):
        self.assertEqual(DashboardBundle.get_json_attr_types(),
                {'test_runs': [TestRuns]})


class HardwareContextTests(TestCase):

    def test_construction_1(self):
        hw_context = HardwareContext()
        self.assertEqual(context.devices, [])

    def test_construction_2(self):
        devices = object()
        hw_context = HardwareContext(devices=devices)
        self.assertEqual(context.devices, devices)

    def test_get_json_attr_types(self):
        self.assertEqual(HardwareContext.get_json_attr_types(),
                {'devices': [HardwareDevice]})

