# Copyright (C) 2017-2019 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# This file is part of LAVA.
#
# LAVA is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# LAVA is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with LAVA.  If not, see <http://www.gnu.org/licenses/>.

import os
from pwd import getpwuid
import simplejson
import yaml
import stat
import subprocess  # nosec system

from django.conf import settings
from django.core.checks import Error, register, Info, Warning
from voluptuous import Invalid

from lava_common.schemas import validate
from lava_scheduler_app.dbutils import invalid_template, validate_job
from lava_scheduler_app.models import Device, DeviceType
from lava_scheduler_app.schema import SubmissionException

# pylint: disable=unused-argument,missing-docstring,invalid-name


@register(deploy=True)
def check_health_checks(app_configs, **kwargs):
    errors = []

    for device in Device.objects.all():
        ht = device.get_health_check()
        ht_disabled = device.device_type.disable_health_check

        # All active devices should have a health check,
        # provided that health checks are not disabled for this device type.
        if device.health == Device.HEALTH_RETIRED:
            continue
        if ht is None:
            if not ht_disabled:
                errors.append(
                    Warning(
                        "No health check for '%s'" % device.hostname,
                        obj="health-checks",
                    )
                )
            continue

        # check the health-check YAML syntax
        try:
            data = yaml.safe_load(ht)
        except yaml.YAMLError as exc:
            errors.append(
                Error(
                    "Invalid YAML syntax for '%s': '%s'" % (device.hostname, exc),
                    obj="health-checks",
                )
            )
            continue

        # check the schema
        try:
            validate(
                data,
                strict=False,
                extra_context_variables=settings.EXTRA_CONTEXT_VARIABLES,
            )
        except Invalid as exc:
            errors.append(
                Error(
                    "Invalid schema for '%s': '%s'" % (device.hostname, exc),
                    obj="health-checks",
                )
            )

        try:
            validate_job(ht)
        except SubmissionException as exc:
            errors.append(
                Error(
                    "Invalid schema for '%s': '%s'" % (device.hostname, exc),
                    obj="health-checks",
                )
            )

    return errors


# Check device dict
@register(deploy=True)
def check_device_configuration(app_configs, **kwargs):
    errors = []

    for device in Device.objects.exclude(health=Device.HEALTH_RETIRED):
        if not device.is_valid():
            errors.append(
                Error("Invalid configuration for '%s'" % device.hostname, obj="devices")
            )

    return errors


# Check device-type templates
@register(deploy=True)
def check_dt_templates(app_configs, **kwargs):
    errors = []

    for dt in DeviceType.objects.filter(display=True):
        if invalid_template(dt):
            errors.append(
                Error("Invalid template for '%s'" % dt.name, obj="device-types")
            )

    return errors


# Check permissions
@register(deploy=True)
def check_permissions(app_configs, **kwargs):
    files = ["/etc/lava-server/instance.conf", "/etc/lava-server/secret_key.conf"]
    errors = []
    for filename in files:
        st = os.stat(filename)
        if stat.S_IMODE(st.st_mode) != 416:
            errors.append(
                Error(
                    "Invalid permissions (should be 0o640) for '%s'" % filename,
                    obj="permissions",
                )
            )
        try:
            if getpwuid(st.st_uid).pw_name != "lavaserver":
                errors.append(
                    Error(
                        "Invalid owner (should be lavaserver) for '%s'" % filename,
                        obj="permissions",
                    )
                )
        except KeyError:
            errors.append(
                Error(
                    "Unknown user id %d for '%s'" % (st.st_uid, filename),
                    obj="permissions",
                )
            )
    return errors


def _package_status(name, errors, info=False):
    try:
        out = (
            subprocess.check_output(  # nosec system
                ["dpkg-query", "--status", name], stderr=subprocess.STDOUT
            )
            .decode("utf-8")
            .split("\n")
        )
        if out[1] != "Status: install ok installed":
            errors.append(
                Error("'%s' not installed correctly" % name, obj="debian pkg")
            )
    except FileNotFoundError:
        errors.append(Warning("Unable to query %s" % name, obj="debian pkg"))
    except subprocess.CalledProcessError:
        if info:
            errors.append(
                Info(
                    "'%s' not installed from a Debian package" % name, obj="debian pkg"
                )
            )
        else:
            errors.append(
                Error(
                    "'%s' not installed from a Debian package" % name, obj="debian pkg"
                )
            )


def _package_symlinks(name, errors):
    dirname = os.path.join("/usr/lib/python3/dist-packages/", name)
    if os.path.islink(dirname):
        errors.append(
            Error(
                "%s symlinked to %s" % (name, os.path.realpath(dirname)),
                obj="debian pkg",
            )
        )


@register(deploy=True)
def check_packaging(app_configs, **kwargs):
    errors = []

    _package_status("lava-common", errors)
    _package_status("lava-dispatcher", errors, info=True)
    _package_status("lava-server", errors)

    _package_symlinks("lava_common", errors)
    _package_symlinks("lava_dispatcher", errors)
    _package_symlinks("lava_results_app", errors)
    _package_symlinks("lava_rest_app", errors)
    _package_symlinks("lava_scheduler_app", errors)
    _package_symlinks("lava_server", errors)
    _package_symlinks("", errors)

    return errors


def find_our_daemons():
    """
    Allow check that all daemons are running without relying
    on systemd which cannot connect to DBus in Docker.
    """
    daemons = {
        "lava-server-gunicorn": None,
        "lava-master": None,
        "lava-logs": None,
        "lava-publisher": None,
        "lava-slave": None,
    }

    for dirname in os.listdir("/proc"):
        if dirname == "curproc":
            continue

        try:
            with open("/proc/{}/cmdline".format(dirname), mode="rb") as fd:
                content = fd.read().decode().split("\x00")
        except Exception:  # nosec bare except ok here.
            continue

        if "gunicorn: master [lava_server.wsgi]" in content[0]:
            daemons["lava-server-gunicorn"] = "%s" % dirname
            continue
        elif len(content) >= 3:
            if "/usr/bin/gunicorn3" in content[1] and "lava_server.wsgi" in content[2]:
                daemons["lava-server-gunicorn"] = "%s" % dirname
                continue

        if "python3" not in content[0]:
            continue

        if "/usr/bin/lava-server" in content[1]:
            if "manage" not in content[2]:
                continue
            if "lava-master" in content[3]:
                daemons["lava-master"] = "%s" % dirname
            elif "lava-logs" in content[3]:
                daemons["lava-logs"] = "%s" % dirname
            elif "lava-publisher" in content[3]:
                daemons["lava-publisher"] = "%s" % dirname
            continue

        if "/usr/bin/lava-slave" in content[1]:
            daemons["lava-slave"] = "%s" % dirname
            continue

    return daemons


@register(deploy=True)
def check_services(app_configs, **kwargs):

    errors = []
    services = [
        "apache2",
        "lava-server-gunicorn",
        "lava-master",
        "lava-publisher",
        "lava-logs",
        "postgresql",
    ]
    optional = ["lava-slave"]

    # check if systemd is running
    try:
        subprocess.check_output(["systemctl"], stderr=subprocess.PIPE)
        running_systemd = True
    except subprocess.CalledProcessError:
        running_systemd = False

    if running_systemd:
        # we can call systemctl
        for service in services:
            try:
                subprocess.check_call(  # nosec system
                    ["systemctl", "-q", "is-active", service]
                )
            except subprocess.CalledProcessError:
                errors.append(
                    Error("%s service is not active." % service, obj="lava services")
                )

        for service in optional:
            try:
                subprocess.check_call(  # nosec system
                    ["systemctl", "-q", "is-active", service]
                )
            except subprocess.CalledProcessError:
                errors.append(
                    Info("%s service is not active." % service, obj="lava services")
                )
    else:
        # systemd is not running, check /proc directly.
        daemons = find_our_daemons()
        for key, value in daemons.items():
            if key in services:
                if not value:
                    errors.append(
                        Error("%s daemon is not active." % key, obj="lava daemons")
                    )
            if key in optional:
                if not value:
                    errors.append(
                        Info("%s daemon is not active." % key, obj="lava daemons")
                    )
    return errors


@register(deploy=True)
def check_settings(app_configs, **kwargs):
    settings = {}
    try:
        with open("/etc/lava-server/settings.conf", "r") as f_conf:
            for (k, v) in simplejson.load(f_conf).items():
                settings[k] = v
    except (AttributeError, ValueError):
        return [Error("settings.conf is not a valid json file", obj="settings.conf")]
    return []
