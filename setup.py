#!/usr/bin/env python

from setuptools import setup, find_packages
from lava_dispatcher import __version__ as version

setup(
    name="lava-dispatcher",
    version=version,
    url='https://launchpad.net/lava-dispatcher',
    license='GPL v2 or later',
    description="Part of the LAVA framework for dispatching test jobs",
    author='Linaro Validation Team',
    author_email='linaro-dev@lists.linaro.org',
    packages=find_packages(),
    scripts = [
        'lava-dispatch'
    ],
)
