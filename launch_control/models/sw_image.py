"""
Module with the SoftwareImage model.
"""

from launch_control.utils.json.pod import PlainOldData


class SoftwareImage(PlainOldData):
    """
    Model for representing software images.
    """

    __slots__ = ('name',)

    def __init__(self, name):
        self.name = name
