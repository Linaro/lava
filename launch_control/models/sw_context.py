"""
Module with the SoftwareContext model.
"""

from launch_control.models.sw_image import SoftwareImage
from launch_control.models.sw_package import SoftwarePackage
from launch_control.utils.json import PlainOldData


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
