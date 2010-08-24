"""
Module with the TestCase model.
"""

from launch_control.utils.json.pod import PlainOldData


class TestCase(PlainOldData):
    """
    TestCase model.

    Currently contains just two fields:
        - test_case_id (test-case specific ID)
        - name (human readable)
    """

    __slots__ = ('test_case_id', 'desc')

    def __init__(self, test_case_id, desc):
        self.test_case_id = test_case_id
        self.name = name
