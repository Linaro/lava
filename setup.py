#!/usr/bin/env python

from setuptools import setup, find_packages
from version import version_tag


setup(
    name="lava-dispatcher",
    version=version_tag(),
    url='https://launchpad.net/lava-dispatcher',
    license='GPL v2 or later',
    description="Part of the LAVA framework for dispatching test jobs",
    author='Linaro Validation Team',
    author_email='linaro-validation@lists.linaro.org',
    namespace_packages=['lava'],
    entry_points="""
    [lava.commands]
    dispatch = lava.dispatcher.commands:dispatch
    connect = lava.dispatcher.commands:connect
    devices = lava.dispatcher.commands:devices
    power-cycle = lava.dispatcher.commands:power_cycle

    [lava.signal_handlers]
    add-duration = lava_dispatcher.signals.duration:AddDuration
    arm-probe = lava_dispatcher.signals.armprobe:ArmProbe
    shell-hooks = lava_dispatcher.signals.shellhooks:ShellHooks
    """,
    packages=find_packages(),
    package_data={
        'lava_dispatcher': [
            'default-config/lava-dispatcher/lava-dispatcher.conf',
            'default-config/lava-dispatcher/lava-dispatcher.conf',
            'default-config/lava-dispatcher/device-defaults.conf',
            'default-config/lava-dispatcher/device-types/*.conf',
            'default-config/lava-dispatcher/devices/*.conf',
            'device/sdmux.sh',
            'lava_test_shell/lava-installed-packages',
            'lava_test_shell/lava-os-build',
            'lava_test_shell/lava-test-case',
            'lava_test_shell/lava-test-case-attach',
            'lava_test_shell/lava-test-run-attach',
            'lava_test_shell/lava-test-runner',
            'lava_test_shell/lava-test-shell',
            'lava_test_shell/multi_node/*',
            'lava_test_shell/lmp/*',
            'lava_test_shell/distro/fedora/*',
            'lava_test_shell/distro/android/*',
            'lava_test_shell/distro/ubuntu/*',
        ],
    },
    install_requires=[
        'json-schema-validator >= 2.3',
        'lava-tool >= 0.4',
        'lava-utils-interface',
        'linaro-dashboard-bundle >= 1.10.2',
        'pexpect >= 2.3',
        'configglue',
        'PyYAML',
        'pyserial >= 2.6',
    ],
    data_files=[
        ('/etc/default',
            ['etc/tftpd-hpa']),
    ],
    scripts=[
        'lava-dispatch'
    ],
)
