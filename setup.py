#!/usr/bin/env python

import sys
from setuptools import setup, find_packages
from version import version_tag

if sys.version_info[0] == 2:
    lzma = 'pyliblzma >= 0.5.3'
elif sys.version_info[0] == 3:
    lzma = ''

setup(
    name="lava-dispatcher",
    version=version_tag(),
    description="Linaro Automated Validation Architecture dispatcher",
    url='https://git.linaro.org/lava/lava-dispatcher.git',
    author='Linaro Validation Team',
    author_email='linaro-validation@lists.linaro.org',
    license='GPL v2 or later',
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 2.7',
        'Topic :: Software Development :: Embedded Systems',
        'Topic :: Software Development :: Testing',
    ],
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
    namespace_packages=['lava'],
    package_data={
        'lava_dispatcher': [
            'default-config/lava-dispatcher/lava-dispatcher.conf',
            'default-config/lava-dispatcher/lava-dispatcher.conf',
            'default-config/lava-dispatcher/device-defaults.conf',
            'default-config/lava-dispatcher/device-types/*.conf',
            'default-config/lava-dispatcher/devices/*.conf',
            'pipeline/device_types/*.conf',
            'pipeline/devices/*.conf',
            'pipeline/devices/*.yaml',
            'device/sdmux.sh',
            'device/dynamic_vm_keys/lava*',
            'lava_test_shell/lava-background-process-start',
            'lava_test_shell/lava-background-process-stop',
            'lava_test_shell/lava-echo-ipv4',
            'lava_test_shell/lava-vm-groups-setup-host',
            'lava_test_shell/lava-installed-packages',
            'lava_test_shell/lava-os-build',
            'lava_test_shell/lava-test-case',
            'lava_test_shell/lava-test-case-attach',
            'lava_test_shell/lava-test-case-metadata',
            'lava_test_shell/lava-test-run-attach',
            'lava_test_shell/lava-test-runner',
            'lava_test_shell/lava-test-set',
            'lava_test_shell/lava-test-shell',
            'lava_test_shell/multi_node/*',
            'lava_test_shell/vland/*',
            'lava_test_shell/lmp/*',
            'lava_test_shell/distro/fedora/*',
            'lava_test_shell/distro/android/*',
            'lava_test_shell/distro/ubuntu/*',
            'lava_test_shell/distro/debian/*',
            'lava_test_shell/distro/oe/*',
            'pipeline/lava_test_shell/lava-test-case',
            'pipeline/lava_test_shell/lava-test-runner',
            'pipeline/lava_test_shell/lava-target-ip',
            'pipeline/lava_test_shell/lava-target-mac',
            'pipeline/lava_test_shell/multi_node/*',
        ],
        'linaro_dashboard_bundle': [
            'schemas/*',
            'test_documents/*',
        ],
    },
    install_requires=[
        'json-schema-validator >= 2.3',
        'lava-tool >= 0.4',
        'pexpect >= 2.3',
        'configglue',
        'PyYAML',
        'pyserial >= 2.6',
        '%s' % lzma,
        'requests',
        'netifaces >= 0.10.0',
        'nose',
        'pyzmq',
        'configobj'
    ],
    test_suite='lava_dispatcher.tests.test_suite',
    tests_require=[
        'pep8 >= 1.4.6',
        'testscenarios >= 0.4'
    ],
    data_files=[
        ('/usr/share/lava-dispatcher/',
            ['etc/tftpd-hpa']),
        ('/etc/exports.d',
            ['etc/lava-dispatcher-nfs.exports']),
        ('/etc/modprobe.d',
            ['etc/lava-options.conf']),
        ('/etc/modules-load.d/',
            ['etc/lava-modules.conf']),
        ('/etc/logrotate.d/',
            ['etc/logrotate.d/lava-slave-log']),
        ('/etc/init.d/',
            ['etc/lava-slave.init']),
        ('/usr/share/lava-dispatcher/',
            ['etc/lava-slave.service'])
    ],
    scripts=[
        'lava-dispatch',
        'lava/dispatcher/lava-dispatcher-slave',
        'lava/dispatcher/lava-slave'
    ],
)
