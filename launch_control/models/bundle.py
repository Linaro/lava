"""
Module with the DashboardBundle model.
"""

from ..utils.json import PlainOldData
from .test_run import TestRun


class DashboardBundle(PlainOldData):
    """
    Model representing the stand-alone document that can store arbitrary
    test runs.

    For useful methods related to the bundle see api module
    """
    # Default format name. If you are working on a fork/branch that is
    # producing incompatible documents you _must_ change the format
    # string. Dashboard Server will be backwards-compatible with all
    # past formats. This format is the _default_ format for new
    # documents.

    # Note: Current format was selected during Linaro 10.11 Cycle.
    FORMAT = "Dashboard Bundle Format 1.0"

    __slots__ = ('format', 'test_runs')

    def __init__(self, format=None, test_runs=None):
        self.format = format or self.FORMAT
        self.test_runs = test_runs or []

    @classmethod
    def get_json_attr_types(cls):
        return {'test_runs': [TestRun]}
