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

from django.core.checks import Error, register, Info, Warning
from voluptuous import MultipleInvalid
from lava_common.schemas import job
from lava_scheduler_app.dbutils import invalid_template, validate_job
from lava_scheduler_app.models import Device, DeviceType
from lava_scheduler_app.schema import SubmissionException

# pylint: disable=unused-argument,missing-docstring,invalid-name


@register(deploy=True)
def check_health_checks(app_configs, **kwargs):
    errors = []

    schema = job.schema()
    for device in Device.objects.all():
        ht = device.get_health_check()
        ht_disabled = device.device_type.disable_health_check

        # All active devices should have a health check,
        # provided that health checks are not disabled for this device type.
        if device.health == Device.HEALTH_RETIRED:
            continue
        if ht is None:
            if not ht_disabled:
                errors.append(Warning("No health check", obj=device.hostname))
            continue

        # check the health-check YAML syntax
        try:
            data = yaml.safe_load(ht)
        except yaml.YAMLError as exc:
            errors.append(
                Error(
                    "Invalid health check YAML: '%s' '%s'." % (device.hostname, exc),
                    obj=device.hostname,
                )
            )
            continue

        # check the schema
        try:
            schema(data)
        except MultipleInvalid as exc:
            errors.append(
                Error(
                    "Invalid health check schema: '%s' '%s'." % (device.hostname, exc),
                    obj=device.hostname,
                )
            )

        try:
            validate_job(ht)
        except SubmissionException as exc:
            errors.append(
                Error("Invalid health check test job: '%s'" % exc, obj=device.hostname)
            )

    return errors


# Check device dict
@register(deploy=True)
def check_device_configuration(app_configs, **kwargs):
    errors = []

    for device in Device.objects.exclude(health=Device.HEALTH_RETIRED):
        if not device.is_valid():
            errors.append(Error("Invalid configuration", obj=device.hostname))

    return errors


# Check device-type templates
@register(deploy=True)
def check_dt_templates(app_configs, **kwargs):
    errors = []

    for dt in DeviceType.objects.filter(display=True):
        if invalid_template(dt):
            errors.append(Error("Invalid template", obj=dt.name))

    return errors


# Check permissions
@register(deploy=True)
def check_permissions(app_configs, **kwargs):
    files = ["/etc/lava-server/instance.conf", "/etc/lava-server/secret_key.conf"]
    errors = []
    for filename in files:
        st = os.stat(filename)
        if stat.S_IMODE(st.st_mode) != 416:
            errors.append(Error("Invalid permissions (should be 0o640)", obj=filename))
        if getpwuid(st.st_uid).pw_name != "lavaserver":
            errors.append(Error("Invalid owner (should be lavaserver)", obj=filename))
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
            errors.append(Error("not installed correctly", obj=name))
    except subprocess.CalledProcessError:
        if info:
            errors.append(Info("not installed from a Debian package", obj=name))
        else:
            errors.append(Error("not installed from a Debian package", obj=name))


def _package_symlinks(name, errors):
    dirname = os.path.join("/usr/lib/python3/dist-packages/", name)
    if os.path.islink(dirname):
        errors.append(Error("symlink to %s" % os.path.realpath(dirname), obj=name))


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
        elif "/usr/bin/gunicorn3" in content[1] and "lava_server.wsgi" in content[2]:
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

    # identify command line of PID 1
    if "/lib/systemd/systemd" in os.readlink("/proc/1/exe"):
        # we can call systemctl
        for service in services:
            try:
                subprocess.check_call(  # nosec system
                    ["systemctl", "-q", "is-active", service]
                )
            except subprocess.CalledProcessError:
                errors.append(
                    Error("%s service is not active." % service, obj="lava service")
                )

        for service in optional:
            try:
                subprocess.check_call(  # nosec system
                    ["systemctl", "-q", "is-active", service]
                )
            except subprocess.CalledProcessError:
                errors.append(
                    Info("%s service is not active." % service, obj="lava service")
                )
    else:
        # systemd is not PID 1, check /proc directly.
        daemons = find_our_daemons()
        for key, value in daemons.items():
            if key in services:
                if not value:
                    errors.append(
                        Error("%s daemon is not active." % key, obj="lava daemon")
                    )
            if key in optional:
                if not value:
                    errors.append(
                        Info("%s daemon is not active." % key, obj="lava daemon")
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
