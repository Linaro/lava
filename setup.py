#!/usr/bin/env python

from setuptools import setup, find_packages

setup(
    name = 'lava',
    version = "0.1",
    description = "LAVA is Linaro Automated Validation Architecture",
    url = 'https://launchpad.net/lava',
    license = "GPLv2+",
    zip_safe = True, 
    packages = find_packages(),
    entry_points = """
    [lava.overwatch.drivers]
    dummy = lava.overwatch.drivers.dummy:DummyDriver
    """,
    install_requires=[
        'Django >= 1.2.4',
        'South >= 0.7.3',
        'simplejson >= 2.0.9',
    ],
)
