#!/usr/bin/env python

from setuptools import setup, find_packages

setup(
    name="lava-dispatcher",
    version=":versiontools:lava_dispatcher:",
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
        ],
    },
    data_files=[
        ('lava_test_shell', [
            'lava_test_shell/lava-installed-packages',
            'lava_test_shell/lava-os-build',
            'lava_test_shell/lava-test-case',
            'lava_test_shell/lava-test-case-attach',
            'lava_test_shell/lava-test-run-attach',
            'lava_test_shell/lava-test-runner-android',
            'lava_test_shell/lava-test-runner-ubuntu',
            'lava_test_shell/lava-test-shell',
            'lava_test_shell/README']),
        ('lava_test_shell/multi_node', [
            'lava_test_shell/multi_node/lava-group',
            'lava_test_shell/multi_node/lava-multi-node.lib',
            'lava_test_shell/multi_node/lava-role',
            'lava_test_shell/multi_node/lava-self',
            'lava_test_shell/multi_node/lava-send',
            'lava_test_shell/multi_node/lava-sync',
            'lava_test_shell/multi_node/lava-wait',
            'lava_test_shell/multi_node/lava-wait-all']),
        ('lava_test_shell/lmp', [
            'lava_test_shell/lmp/lava-lmp-audio-jack',
            'lava_test_shell/lmp/lava-lmp-eth',
            'lava_test_shell/lmp/lava-lmp-hdmi',
            'lava_test_shell/lmp/lava-lmp.lib',
            'lava_test_shell/lmp/lava-lmp-lsgpio',
            'lava_test_shell/lmp/lava-lmp-sata',
            'lava_test_shell/lmp/lava-lmp-usb'])
    ],
    install_requires=[
        'json-schema-validator >= 2.3',
        'lava-tool >= 0.4',
        'lava-utils-interface',
        'linaro-dashboard-bundle',
        'pexpect >= 2.3',
        'configglue',
        'PyYAML',
        'versiontools >= 1.8',
        'pyserial >= 2.6',
    ],
    setup_requires=[
        'versiontools >= 1.8',
    ],
    scripts=[
        'lava-dispatch'
    ],
)
