#!/usr/bin/env python3
#
# Copyright (C) 2010-2019 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#         Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import glob
import os
import shutil
import sys

import setuptools.command.install
import setuptools.command.install_scripts
from setuptools import find_packages, setup


class install_and_change_permission(setuptools.command.install.install):
    """
    Custom install to change dynamic_vm_keys's permission
    """

    def run(self):
        super().run()

        for file_path in self.get_outputs():
            if "dynamic_vm_keys" in file_path:
                print("Change permission of %s" % file_path)
                os.chmod(file_path, 0o600)


class rename_scripts(setuptools.command.install_scripts.install_scripts):
    """
    Custom install script to rename 'manage.py' to 'lava-server'
    """

    SCRIPTS = {"manage.py": "lava-server"}

    def run(self):
        super().run()
        for script in self.get_outputs():
            for key in self.SCRIPTS:
                if script.endswith(key):
                    new_name = script.replace(key, self.SCRIPTS[key])
                    print("Rename %r to %r" % (script, new_name))
                    shutil.move(script, new_name)
                    continue


def modules(name):
    pkgs = [name + "." + p for p in find_packages(name)]
    return [name] + pkgs


COMMON = {
    "name": "lava-common",
    "description": "LAVA common",
    "packages": modules("lava_common"),
    "scripts": [],
    "data_files": [("/usr/share/lava-common/", ["share/lava-schema.py"])],
}

COORDINATOR = {
    "name": "lava-coordinator",
    "description": "LAVA coordinator",
    "packages": ["lava.coordinator"],
    "scripts": ["lava/coordinator/lava-coordinator"],
    "data_files": [
        (
            "/etc/lava-coordinator/",
            ["etc/lava-coordinator", "etc/lava-coordinator.conf"],
        ),
        ("/etc/logrotate.d/", ["etc/logrotate.d/lava-coordinator-log"]),
        ("/usr/lib/systemd/system/", ["etc/lava-coordinator.service"]),
    ],
    "cmdclass": {"install_scripts": rename_scripts},
}

DISPATCHER = {
    "name": "lava-dispatcher",
    "description": "LAVA dispatcher",
    "packages": modules("lava_dispatcher"),
    "package_data": {
        "lava_dispatcher": ["dynamic_vm_keys/lava*", "lava_test_shell/**"]
    },
    "scripts": [
        "lava/dispatcher/lava-outerr",
        "lava/dispatcher/lava-run",
        "lava/dispatcher/lava-worker",
    ],
    "data_files": [
        ("/etc/exports.d/", ["etc/lava-dispatcher-nfs.exports"]),
        ("/etc/lava-dispatcher/", ["etc/lava-worker"]),
        ("/etc/logrotate.d/", ["etc/logrotate.d/lava-worker-log"]),
        ("/etc/modprobe.d/", ["etc/lava-modules.conf"]),
        ("/usr/lib/systemd/system/", ["etc/lava-worker.service"]),
        ("/etc/systemd/system/systemd-udevd.service.d/", ["etc/udev/override.conf"]),
        ("/usr/share/lava-dispatcher/", ["etc/tftpd-hpa"]),
        ("/usr/share/lava-dispatcher/apache2/", ["share/apache2/lava-dispatcher.conf"]),
        ("/var/lib/lava/dispatcher/tmp/", []),
        ("/var/log/lava-dispatcher/", []),
    ],
    "cmdclass": {"install": install_and_change_permission},
}

DISPATCHER_HOST = {
    "name": "lava-dispatcher-host",
    "description": "LAVA dispatcher host",
    "packages": modules("lava_dispatcher_host"),
    "scripts": [
        "lava_dispatcher_host/lava-dispatcher-host",
        "lava_dispatcher_host/lava-docker-worker",
        "lava_dispatcher_host/lava-dispatcher-host-server",
    ],
    "data_files": [
        (
            "/usr/lib/systemd/system/",
            [
                "etc/lava-docker-worker.service",
                "etc/lava-dispatcher-host.socket",
                "etc/lava-dispatcher-host.service",
            ],
        ),
        ("/etc/lava-dispatcher-host/", ["etc/lava-docker-worker"]),
        (
            "/etc/logrotate.d/",
            [
                "etc/logrotate.d/lava-dispatcher-host-log",
                "etc/logrotate.d/lava-docker-worker-log",
            ],
        ),
        ("/var/log/lava-dispatcher-host/", []),
    ],
}

SERVER = {
    "name": "lava-server",
    "description": "LAVA server",
    "packages": (
        modules("lava_rest_app")
        + modules("lava_results_app")
        + modules("lava_scheduler_app")
        + modules("lava_server")
        + modules("linaro_django_xmlrpc")
    ),
    "scripts": ["manage.py"],
    "data_files": [
        ("/etc/apache2/sites-available/", ["etc/lava-server.conf"]),
        (
            "/etc/lava-server/",
            [
                "etc/env.yaml",
                "etc/lava-celery-worker",
                "etc/lava-publisher",
                "etc/lava-scheduler",
                "etc/lava-server-gunicorn",
            ],
        ),
        ("/etc/lava-server/dispatcher-config/devices/", []),
        ("/etc/lava-server/dispatcher-config/device-types/", []),
        ("/etc/lava-server/dispatcher-config/health-checks/", []),
        ("/etc/lava-server/dispatcher.d/", []),
        ("/etc/lava-server/settings.d/", []),
        (
            "/etc/logrotate.d/",
            [
                "etc/logrotate.d/django-log",
                "etc/logrotate.d/lava-celery-worker-log",
                "etc/logrotate.d/lava-publisher-log",
                "etc/logrotate.d/lava-scheduler-log",
                "etc/logrotate.d/lava-server-gunicorn-log",
            ],
        ),
        (
            "/usr/lib/systemd/system/",
            [
                "etc/lava-celery-worker.service",
                "etc/lava-publisher.service",
                "etc/lava-scheduler.service",
                "etc/lava-server-gunicorn.service",
            ],
        ),
        ("/usr/share/lava-server/", ["etc/dispatcher.yaml", "share/postinst.py"]),
        (
            "/usr/share/lava-server/device-types/",
            glob.glob("etc/dispatcher-config/device-types/*.jinja2"),
        ),
        ("/var/lib/lava-server/default/media/job-output/", []),
        ("/var/lib/lava-server/home/", []),
        ("/var/log/lava-server/", []),
    ],
    "cmdclass": {"install_scripts": rename_scripts},
}

PKGS = {
    "lava-common": COMMON,
    "lava-coordinator": COORDINATOR,
    "lava-dispatcher": DISPATCHER,
    "lava-dispatcher-host": DISPATCHER_HOST,
    "lava-server": SERVER,
}


def merge_data_files(srcs):
    data_files = [{i[0]: i[1] for i in src} for src in srcs if src]
    ret = {}
    for data in data_files:
        for k, v in data.items():
            if k in ret:
                ret[k].extend(v)
            else:
                ret[k] = v
    return sorted((k, sorted(set(v))) for (k, v) in ret.items())


if sys.argv[-1].startswith("lava-"):
    # For lava-server
    # TODO: check file ownership
    pkg = sys.argv.pop()
    setup(**PKGS[pkg])
else:
    LAVA = {
        "name": "lava",
        "description": "LAVA",
        "packages": sorted({n for p in PKGS for n in PKGS[p]["packages"]}),
        "package_data": PKGS["lava-dispatcher"]["package_data"],
        "scripts": sorted([n for p in PKGS for n in PKGS[p].get("scripts", [])]),
        "data_files": merge_data_files([PKGS[p].get("data_files", []) for p in PKGS]),
        "cmdclass": PKGS["lava-server"]["cmdclass"],
    }
    setup(**LAVA)
