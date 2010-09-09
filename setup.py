#!/usr/bin/env python

from setuptools import setup, find_packages

from launch_control import __version__ as version


setup(
        name = 'launch-control',
        version = version,
        author = "Zygmunt Krynicki",
        author_email = "zygmunt.krynicki@linaro.org",
        packages = ['dashboard_app', 'launch_control', 'dashboard_server'],
        scripts = ['lc-tool.py'],
        long_description = """
        Launch control is a collection of tools for distribution wide QA
        management. It is implemented for the Linaro organization.
        """,
        url='https://launchpad.net/launch-control',
        test_suite='launch_control.tests.test_suite',
        classifiers=[
            "Development Status :: 3 - Alpha",
            "Intended Audience :: Developers",
            "License :: OSI Approved :: GNU Affero General Public License v3",
            "License :: OSI Approved :: GNU Library or Lesser General Public License (LGPL)",
            "Operating System :: OS Independent",
            "Programming Language :: Python :: 2.6",
            "Topic :: Software Development :: Testing",
            ],
        )
