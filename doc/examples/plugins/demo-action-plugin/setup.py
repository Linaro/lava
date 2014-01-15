#!/usr/bin/env python

from setuptools import setup

setup(
    name='demo-action-plugin',
    version='0.0.1',
    author='Paul Larson',
    author_email='paul.larson@linaro.org',
    url='',
    description='LAVA Dispatcher plugin test',
    packages=['demo_action_plugin'],
    entry_points="""
    [lava_dispatcher.actions]
    foo = demo_action_plugin.foo:cmd_foo
    """,
    zip_safe=False,
    include_package_data=True
)
