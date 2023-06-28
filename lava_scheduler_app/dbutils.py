# Copyright (C) 2015-2019 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#         Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""
Database utility functions which use but are not actually models themselves
Used to allow models.py to be shortened and easier to follow.
"""
import contextlib
import logging

import yaml
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.validators import validate_email
from django.db.models import Count, Q
from jinja2 import TemplateError as JinjaTemplateError

from lava_common.decorators import nottest
from lava_common.yaml import yaml_safe_load
from lava_results_app.models import Query
from lava_scheduler_app import environment
from lava_scheduler_app.models import (
    Device,
    DeviceType,
    NotificationRecipient,
    TestJob,
    Worker,
)
from lava_scheduler_app.schema import SubmissionException, validate_submission


def match_vlan_interface(device, job_def):
    if not isinstance(job_def, dict):
        raise RuntimeError("Invalid vlan interface data")
    if (
        "protocols" not in job_def
        or "lava-vland" not in job_def["protocols"]
        or not device
    ):
        return False
    interfaces = []
    logger = logging.getLogger("lava-master")
    device_dict = device.load_configuration()
    if not device_dict or device_dict.get("parameters", {}).get("interfaces") is None:
        return False

    for vlan_name in job_def["protocols"]["lava-vland"]:
        tag_list = job_def["protocols"]["lava-vland"][vlan_name]["tags"]
        for interface in device_dict["parameters"]["interfaces"]:
            tags = device_dict["parameters"]["interfaces"][interface]["tags"]
            if not tags:
                continue
            logger.info(
                "Job requests %s for %s, device %s provides %s for %s",
                tag_list,
                vlan_name,
                device.hostname,
                tags,
                interface,
            )
            if (
                set(tags) & set(tag_list) == set(tag_list)
                and interface not in interfaces
            ):
                logger.info(
                    "Matched vlan %s to interface %s on %s",
                    vlan_name,
                    interface,
                    device,
                )
                interfaces.append(interface)
                # matched, do not check any further interfaces of this device for this vlan
                break

    logger.info(
        "Matched: %s",
        (len(interfaces) == len(job_def["protocols"]["lava-vland"].keys())),
    )
    return len(interfaces) == len(job_def["protocols"]["lava-vland"].keys())


# TODO: check the list of exception that can be raised
@nottest
def testjob_submission(job_definition, user, original_job=None):
    """
    Single submission frontend for YAML
    :param job_definition: string of the job submission
    :param user: user attempting the submission
    :return: a job or a list of jobs
    :raises: SubmissionException, Device.DoesNotExist,
        DeviceType.DoesNotExist, DevicesUnavailableException,
        ValueError
    """
    validate_job(job_definition)
    # returns a single job or a list (not a QuerySet) of job objects.
    job = TestJob.from_yaml_and_user(job_definition, user, original_job=original_job)
    return job


def device_summary():
    device_stats = (
        Device.objects.filter(
            ~Q(health=Device.HEALTH_RETIRED),
        )
        .select_related("last_health_report_job")
        .aggregate(
            num_not_retired=Count("pk"),
            num_online=Count(
                "pk",
                filter=(
                    Q(health__in=(Device.HEALTH_GOOD, Device.HEALTH_UNKNOWN))
                    & Q(worker_host__state=Worker.STATE_ONLINE)
                ),
            ),
            health_checks_total=Count(
                "pk",
                last_health_report_job__isnull=False,
            ),
            health_checks_complete=Count(
                "pk",
                filter=(
                    Q(last_health_report_job__isnull=False)
                    & Q(last_health_report_job__state=TestJob.STATE_FINISHED)
                ),
            ),
            active_devices=Count(
                "pk",
                filter=Q(state__in=(Device.STATE_RESERVED, Device.STATE_RUNNING)),
            ),
        )
    )

    running_jobs_count = TestJob.objects.filter(
        state=TestJob.STATE_RUNNING, actual_device__isnull=False
    ).count()

    return (device_stats, running_jobs_count)


def device_type_summary(user):
    devices = (
        Device.objects.filter(
            ~Q(health=Device.HEALTH_RETIRED),
            Q(device_type__in=DeviceType.objects.visible_by_user(user)),
        )
        .only("state", "health", "device_type", "hostname")
        .values("device_type")
        .annotate(
            idle=Count(
                "pk",
                filter=Q(
                    state=Device.STATE_IDLE,
                    health__in=(Device.HEALTH_GOOD, Device.HEALTH_UNKNOWN),
                    worker_host__state=Worker.STATE_ONLINE,
                ),
            ),
            busy=Count(
                "pk",
                filter=Q(
                    state__in=(Device.STATE_RESERVED, Device.STATE_RUNNING),
                ),
            ),
            offline=Count(
                "pk",
                filter=Q(state=Device.STATE_IDLE)
                & ~Q(health=Device.HEALTH_MAINTENANCE)
                & (
                    Q(worker_host__state=Worker.STATE_OFFLINE)
                    | ~Q(health__in=(Device.HEALTH_GOOD, Device.HEALTH_UNKNOWN))
                ),
            ),
            maintenance=Count(
                "pk",
                filter=Q(health=Device.HEALTH_MAINTENANCE),
            ),
        )
        .order_by("device_type")
    )
    return devices


def active_device_types():
    """
    Filter the available device types to exclude
    all device-types where ALL devices are in health RETIRED
    without excluding device-types where only SOME devices are retired.

    oneliner:
{device.device_type for device in Device.objects.filter(~Q(health=Device.HEALTH_RETIRED))}.union( \
{dt for dt in {device.device_type for device in Device.objects.filter(health=Device.HEALTH_RETIRED)} \
if list(Device.objects.filter(Q(device_type=dt), ~Q(health=Device.HEALTH_RETIRED)))})

    Returns a RestrictedQuerySet of DeviceType objects.
    """
    not_retired_devices = Device.objects.filter(
        Q(device_type__display=True), ~Q(health=Device.HEALTH_RETIRED)
    ).select_related("device_type")
    retired_devices = Device.objects.filter(
        Q(device_type__display=True), health=Device.HEALTH_RETIRED
    ).select_related("device_type")
    not_all_retired = (
        set()
    )  # set of device_type.names where some devices of that device_type are retired but *not* all.
    for device in retired_devices:
        # identify device_types which can be added back because not all devices of that type are retired.
        if list(
            Device.objects.filter(
                Q(device_type=device.device_type), ~Q(health=Device.HEALTH_RETIRED)
            )
        ):
            not_all_retired.add(device.device_type.name)
    # join the two sets as a union.
    candidates = {device.device_type.name for device in not_retired_devices}.union(
        not_all_retired
    )
    device_types = DeviceType.objects.filter(name__in=candidates)
    return device_types


def load_devicetype_template(device_type_name, raw=False):
    """
    Loads the bare device-type template as a python dictionary object for
    representation within the device_type templates.
    No device-specific details are parsed - default values only, so some
    parts of the dictionary may be unexpectedly empty. Not to be used when
    rendering device configuration for a testjob.
    :param device_type_name: DeviceType.name (string)
    :param raw: if True, return the raw yaml
    :return: None or a dictionary of the device type template.
    """
    try:
        template = environment.device_types().get_template(
            "%s.jinja2" % device_type_name
        )
        data = template.render()
        if not data:
            return None
        return data if raw else yaml_safe_load(data)
    except (JinjaTemplateError, yaml.error.YAMLError):
        return None


def invalid_template(dt):
    """
    Careful with the inverted logic here.
    Return True if the template is invalid.
    See unit tests in test_device.py
    """
    d_template = bool(
        load_devicetype_template(dt.name)
    )  # returns None on error ( == False)
    if not d_template:
        queryset = list(
            Device.objects.filter(Q(device_type=dt), ~Q(health=Device.HEALTH_RETIRED))
        )
        if not queryset:
            return False
        extends = {device.get_extends() for device in queryset}
        if not extends:
            return True
        for extend in extends:
            if not extend:
                return True
            d_template = not bool(
                load_devicetype_template(extend.replace(".jinja2", ""))
            )
            # if d_template is False, template is valid, invalid_template returns False
            if d_template:
                return True
    else:
        d_template = False  # template exists, invalid check is False
    return d_template


def validate_job(data):
    try:
        yaml_data = yaml_safe_load(data)
    except yaml.YAMLError as exc:
        raise SubmissionException("Loading job submission failed: %s." % exc)

    # validate against the submission schema.
    validate_submission(yaml_data)  # raises SubmissionException if invalid.
    validate_yaml(yaml_data)  # raises SubmissionException if invalid.


def validate_yaml(yaml_data):
    if "notify" in yaml_data:
        if "recipients" in yaml_data["notify"]:
            for recipient in yaml_data["notify"]["recipients"]:
                if recipient["to"]["method"] == NotificationRecipient.EMAIL_STR:
                    if "email" not in recipient["to"] and "user" not in recipient["to"]:
                        raise SubmissionException(
                            "No valid user or email address specified."
                        )
                else:
                    if (
                        "handle" not in recipient["to"]
                        and "user" not in recipient["to"]
                    ):
                        raise SubmissionException(
                            "No valid user or IRC handle specified."
                        )
                if "user" in recipient["to"]:
                    try:
                        User.objects.get(username=recipient["to"]["user"])
                    except User.DoesNotExist:
                        raise SubmissionException(
                            "%r is not an existing user in LAVA."
                            % recipient["to"]["user"]
                        )
                elif "email" in recipient["to"]:
                    try:
                        validate_email(recipient["to"]["email"])
                    except ValidationError:
                        raise SubmissionException(
                            "%r is not a valid email address."
                            % recipient["to"]["email"]
                        )

        if (
            "compare" in yaml_data["notify"]
            and "query" in yaml_data["notify"]["compare"]
        ):
            query_yaml_data = yaml_data["notify"]["compare"]["query"]
            if "username" in query_yaml_data:
                try:
                    query = Query.objects.get(
                        owner__username=query_yaml_data["username"],
                        name=query_yaml_data["name"],
                    )
                    if query.content_type.model_class() != TestJob:
                        raise SubmissionException("Only TestJob queries allowed.")
                except Query.DoesNotExist:
                    raise SubmissionException(
                        "Query ~%s/%s does not exist"
                        % (query_yaml_data["username"], query_yaml_data["name"])
                    )
            else:  # Custom query.
                if query_yaml_data["entity"] != "testjob":
                    raise SubmissionException("Only TestJob queries allowed.")
                try:
                    conditions = None
                    if "conditions" in query_yaml_data:
                        conditions = query_yaml_data["conditions"]
                    Query.validate_custom_query(query_yaml_data["entity"], conditions)
                except Exception as e:
                    raise SubmissionException(e)


def get_domain():
    domain = "???"
    with contextlib.suppress(Site.DoesNotExist, ImproperlyConfigured):
        site = Site.objects.get_current()
        domain = site.domain

    return domain
