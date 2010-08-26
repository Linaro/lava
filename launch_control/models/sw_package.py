"""
Module with the SoftwarePackage model.
"""

from launch_control.utils.json.pod import PlainOldData


class SoftwarePackage(PlainOldData):
    """
    Model for representing SoftwarePackages.

    Immutable glorified tuple with 'name' and 'version' fields.
    """

    __slots__ = ('name', 'version')

    def __init__(self, name, version):
        """
        Initialize package with name and version
        """
        self.name = name
        self.version = version
