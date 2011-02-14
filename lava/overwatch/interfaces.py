"""
Interfaces for pluggable components of the stack.
"""

class IOverwatchDriver(object):
    """
    Overwatch drivers are responsible for "wrapping" all the logic required to
    manage physical devices connected to the LAVA environment. Since it's
    impossible to predict all theoretical use-cases that this stack can
    participate in the design is modeled around pluggable interfaces.

    A driver can advertise all the implemented interfaces via the
    enumerate_interfaces() method. Any service that wants to use a particular
    interface can call get_interface() with the name of the required
    functionality.

    By convention all interfaces designed by the LAVA team will use the
    ``lava.*`` namespace.  Other namespaces are available to experiments,
    extensions and proprietary subsystems.

    In practice we expect some common functionality from overwatch drivers to
    be able to use them in our test environment in the way that we currently
    designed the system to support (for typical linux distributions built for
    ARM).
    """

    def __init__(self, config):
        """
        Initialize the driver with the specified configuration string.
        """
    
    def enumerate_interfaces(self):
        """
        Enumerate interfaces supported and implemented by this overwatch driver
        """

    def get_interface(self, name):
        """
        Contruct an instance of the interface with the requested name.

        Raises ValueError if the name does not designate an interface
        implemeted by this driver 
        """
