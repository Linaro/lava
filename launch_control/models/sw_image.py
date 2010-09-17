"""
Module with the SoftwareImage model.
"""

from launch_control.utils.json.pod import PlainOldData


class SoftwareImage(PlainOldData):
    """
    Model for representing software images.
    """

    __slots__ = ('desc',)

    def __init__(self, desc=None):
        self.desc = desc
