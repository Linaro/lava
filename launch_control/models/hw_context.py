"""
Module with the HardwareContext model.
"""

from launch_control.models.hw_device import HardwareDevice
from launch_control.utils.json import PlainOldData


class HardwareContext(PlainOldData):
    """
    Model representing the hardware context of a test run.

    The whole context is just a collection of devices.
    """
    __slots__ = ('devices',)

    def __init__(self, devices=None):
        self.devices = devices or []

    @classmethod
    def get_json_attr_types(cls):
        return {'devices': [HardwareDevice]}

