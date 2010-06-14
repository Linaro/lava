#!/usr/bin/env python

from launch_control import __version__ as version


import os
import sys


try:
    import DistUtilsExtra.auto
except ImportError:
    print >> sys.stderr, 'To build launch-control you need https://launchpad.net/python-distutils-extra'
    sys.exit(1)
assert DistUtilsExtra.auto.__version__ >= '2.18', 'needs DistUtilsExtra.auto >= 2.18'


DistUtilsExtra.auto.setup(
        name='launch-control',
        version=version,
        url='https://launchpad.net/launch-control',
        )
