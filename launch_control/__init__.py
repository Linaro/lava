# This file is part of the ARM Validation Dashboard Project.
# for the Linaro organization (http://linaro.org/)
#
# For more details see:
#   https://blueprints.launchpad.net/ubuntu/+spec/arm-m-validation-dashboard
"""
Launch Control
"""

__version__ = (0, 0, 1, "dev", 0)


def get_version():
    return ".".join(map(str, __version__))
