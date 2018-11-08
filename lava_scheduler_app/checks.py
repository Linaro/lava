# Copyright (C) 2017 Linaro Limited
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
import stat
import subprocess  # nosec system

from django.core.checks import Error, register, Info, Warning

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
        if ht is None and not ht_disabled:
            errors.append(Warning("No health check", obj=device.hostname))
            continue

        # An empty file is an error, provided health checks are not disabled
        # for this device type.
        if not ht and not ht_disabled:
            errors.append(Warning("Empty health check", obj=device.hostname))
            continue

        # Check that the health check job is valid
        if ht:
            try:
                validate_job(ht)
            except SubmissionException as exc:
                errors.append(
                    Error("Invalid health check: '%s'" % exc, obj=device.hostname)
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
    _package_symlinks("lava_scheduler_app", errors)
    _package_symlinks("lava_server", errors)
    _package_symlinks("", errors)

    return errors


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
    return errors
