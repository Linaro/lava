"""
Module with the SoftwareImage model.
"""

from ..utils.json.pod import PlainOldData


class SoftwareImage(PlainOldData):
    """
    Model for representing software images.
    """
    __slots__ = ('name',)
    def __init__(self, desc):
        self.name = name
