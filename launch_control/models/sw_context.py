"""
Module with the SoftwareContext model.
"""
from ..utils.json import PlainOldData
from .sw_image import SoftwareImage
from .sw_package import SoftwarePackage


class SoftwareContext(PlainOldData):
    """
    Model representing the software context of a test run.

    The whole context is a collection of packages and a name
    of the operating system image.
    """
    __slots__ = ('packages', 'sw_image')

    def __init__(self, packages = None, sw_image = None):
        self.packages = packages or []
        self.sw_image = sw_image

    @classmethod
    def get_json_attr_types(cls):
        return {'packages': [SoftwarePackage],
                'sw_image': SoftwareImage}
