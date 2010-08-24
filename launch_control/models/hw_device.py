"""
Module with the HardwareDevice model.
"""

from launch_control.utils.json import PlainOldData


class HardwareDevice(PlainOldData):
    """
    Model representing any HardwareDevice

    A device is just a "device_type" attribute with a bag of properties
    and a human readable description. Individual device types can be
    freely added. For simplicity some common types of devices are
    provided as class properties DEVICE_xxx.

    Instances will come from a variety of factory classes, each capable
    of enumerating devices that it understands. The upside of having a
    common class like this is that it's easier to store it in the
    database _and_ not have to agree on a common set of properties for,
    say, all CPUs.

    If you want you can create instances manually, like this:
    >>> cpu = HardwareDevice(HardwareDevice.DEVICE_CPU,
    ...     u"800MHz OMAP3 Processor")
    >>> cpu.attributes[u'machine'] = u'arm'
    >>> cpu.attributes[u'mhz'] = '800'
    >>> cpu.attributes[u'vendor'] = u'Texas Instruments'
    """

    DEVICE_CPU = "device.cpu"
    DEVICE_MEM = "device.mem"
    DEVICE_USB = "device.usb"
    DEVICE_PCI = "device.pci"
    DEVICE_BOARD = "device.board"

    __slots__ = ('device_type', 'description', 'attributes')

    def __init__(self, device_type, description, attributes=None):
        self.device_type = device_type
        self.description = description
        self.attributes = attributes or {}
