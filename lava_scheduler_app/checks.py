from django.core.checks import Debug, Error, register

from lava_scheduler_app.models import Device, validate_job
from lava_scheduler_app.schema import SubmissionException


@register(deploy=True)
def check_health_checks(app_configs, **kwargs):
    errors = []

    for device in Device.objects.filter(is_pipeline=True):
        ht = device.get_health_check()
        ht_disabled = device.device_type.disable_health_check

        # Every device should have a health check, provided health checks are
        # not disabled for this device type.
        if ht is None and not ht_disabled:
            errors.append(Debug("No health check", obj=device.hostname))
            continue

        # An empty file is an error, provided health checks are not disabled
        # for this device type.
        if not ht and not ht_disabled:
            errors.append(Error("Empty health check", obj=device.hostname))
            continue

        # Check that the health check job is valid
        if ht:
            try:
                validate_job(ht)
            except SubmissionException as exc:
                errors.append(Error("Invalid health check: '%s'" % exc,
                                    obj=device.hostname))

    return errors


@register(deploy=True)
def check_device_configuration(app_configs, **kwargs):
    errors = []

    for device in Device.objects.filter(is_pipeline=True):
        if not device.is_valid():
            errors.append(Error('Invalid configuration', obj=device.hostname))

    return errors
