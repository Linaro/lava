# Copyright (C) 2017-2019 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import stat
import subprocess  # nosec system
from pathlib import Path
from pwd import getpwuid

import yaml
from django.conf import settings
from django.core.checks import Error, Info, Warning, register
from voluptuous import Invalid

from lava_common.schemas import validate
from lava_common.yaml import yaml_safe_load
from lava_scheduler_app.dbutils import invalid_template, validate_job
from lava_scheduler_app.models import Device, DeviceType
from lava_scheduler_app.schema import SubmissionException


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
            data = yaml_safe_load(ht)
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


def check_permission(path):
    try:
        st = path.stat()
    except FileNotFoundError:
        return None

    if stat.S_IMODE(st.st_mode) != 416:
        return Error(
            f"Invalid permissions (should be 0o640) for '{path}'", obj="permissions"
        )
    try:
        if getpwuid(st.st_uid).pw_name != "lavaserver":
            return Error(
                f"Invalid owner (should be lavaserver) for '{path}'", obj="permissions"
            )
    except KeyError:
        return Error(f"Unknown user id {st.st_uid} for '{path}'", obj="permissions")
    return None


# Check permissions
@register(deploy=True)
def check_permissions(app_configs, **kwargs):
    files = [
        Path("/etc/lava-server/instance.conf"),
        Path("/etc/lava-server/secret_key.conf"),
        Path("/etc/lava-server/settings.conf"),
        Path("/etc/lava-server/settings.yaml"),
        *Path("/etc/lava-server/settings.d").glob("*.yaml"),
    ]

    errors = [check_permission(path) for path in files]
    return [err for err in errors if err is not None]


def _package_status(name, info=False):
    try:
        out = (
            subprocess.check_output(  # nosec system
                ["dpkg-query", "--status", name], stderr=subprocess.STDOUT
            )
            .decode("utf-8")
            .split("\n")
        )
        if out[1] != "Status: install ok installed":
            return Error(f"'{name}' not installed correctly", obj="debian pkg")
    except FileNotFoundError:
        return Warning(f"Unable to query {name}", obj="debian pkg")
    except subprocess.CalledProcessError:
        if info:
            return Info(
                f"'{name}' not installed from a Debian package", obj="debian pkg"
            )
        else:
            return Error(
                f"'{name}' not installed from a Debian package", obj="debian pkg"
            )


def _package_symlinks(name):
    dirname = Path("/usr/lib/python3/dist-packages/") / name
    if dirname.exists() and dirname.is_symlink():
        return Error(f"{name} symlinked to {dirname.resolve()}", obj="debian pkg")


@register(deploy=True)
def check_packaging(app_configs, **kwargs):
    errors = [
        _package_status("lava-common"),
        _package_status("lava-coordinator", info=True),
        _package_status("lava-dispatcher", info=True),
        _package_status("lava-dispatcher-host", info=True),
        _package_status("lava-server"),
        _package_status("lava-server-doc"),
        _package_symlinks("lava_common"),
        _package_symlinks("lava_dispatcher"),
        _package_symlinks("lava_dispatcher_host"),
        _package_symlinks("lava_rest_app"),
        _package_symlinks("lava_results_app"),
        _package_symlinks("lava_scheduler_app"),
        _package_symlinks("lava_server"),
        _package_symlinks("linaro_django_xmlrpc"),
    ]

    return [err for err in errors if err is not None]


def find_our_daemons():
    """
    Allow check that all daemons are running without relying
    on systemd which cannot connect to DBus in Docker.
    """
    daemons = {
        "lava-server-gunicorn": None,
        "lava-publisher": None,
        "lava-scheduler": None,
        "lava-worker": None,
    }

    for path in Path("/proc").glob("*/cmdline"):
        pid = path.parts[2]
        if "self" in pid:
            continue

        try:
            content = path.read_text(encoding="utf-8").split("\x00")
        except OSError:
            continue

        if "gunicorn: master [lava_server.wsgi]" in content[0]:
            daemons["lava-server-gunicorn"] = pid
            continue
        elif len(content) >= 3:
            if "/usr/bin/gunicorn3" in content[1] and "lava_server.wsgi" in content[2]:
                daemons["lava-server-gunicorn"] = pid
                continue

        if "python3" not in content[0]:
            continue

        if "/usr/bin/lava-server" in content[1]:
            if "manage" not in content[2]:
                continue
            if "lava-publisher" in content[3]:
                daemons["lava-publisher"] = pid
            elif "lava-scheduler" in content[3]:
                daemons["lava-scheduler"] = pid
            continue

        if "/usr/bin/lava-worker" in content[1]:
            daemons["lava-worker"] = pid
            continue

    return daemons


@register(deploy=True)
def check_services(app_configs, **kwargs):
    errors = []
    services = [
        "apache2",
        "lava-server-gunicorn",
        "lava-publisher",
        "lava-scheduler",
        "postgresql",
    ]
    optional = ["lava-worker"]

    # check if systemd is running
    try:
        subprocess.check_output(["systemctl"], stderr=subprocess.PIPE)
        running_systemd = True
    except (FileNotFoundError, subprocess.CalledProcessError):
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


def check_setting(path):
    try:
        yaml_safe_load(path.read_text(encoding="utf-8"))
    except OSError:
        return None
    except Exception:
        return Error(f"{path} is not a valid yaml file", obj="settings")
    return None


@register(deploy=True)
def check_settings(app_configs, **kwargs):
    files = [
        Path("/etc/lava-server/settings.conf"),
        Path("/etc/lava-server/settings.yaml"),
        *Path("/etc/lava-server/settings.d").glob("*.yaml"),
    ]

    errors = [check_setting(path) for path in files]
    return [err for err in errors if err is not None]
