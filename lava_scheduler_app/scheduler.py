# Copyright (C) 2018 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import (
    Count,
    DurationField,
    Exists,
    ExpressionWrapper,
    F,
    IntegerField,
    OuterRef,
    Q,
    Value,
)
from django.utils import timezone

from lava_common.yaml import yaml_safe_dump, yaml_safe_load
from lava_scheduler_app.dbutils import match_vlan_interface
from lava_scheduler_app.models import (
    Device,
    DeviceType,
    Tag,
    TestJob,
    Worker,
    _create_pipeline_job,
)

LOGGER_NAME = "lava-scheduler"
LOGGER = logging.getLogger(LOGGER_NAME)


@dataclass
class WorkerSummary:
    limit: int
    busy: int

    def overused(self):
        return self.limit > 0 and self.busy >= self.limit


def filter_devices(q, workers):
    q = q.filter(state=Device.STATE_IDLE)
    q = q.filter(worker_host__in=workers)
    return q


def worker_summary(workers):
    query = Worker.objects.filter(hostname__in=workers)
    query = query.values("hostname", "job_limit")
    query = query.annotate(
        busy=Count(
            "device",
            filter=Q(device__state__in=(Device.STATE_RESERVED, Device.STATE_RUNNING)),
        )
    )
    ret = {w["hostname"]: WorkerSummary(w["job_limit"], w["busy"]) for w in query}
    return ret


def check_queue_timeout():
    LOGGER.info("Check queue timeouts:")
    jobs = TestJob.objects.filter(state=TestJob.STATE_SUBMITTED)
    jobs = jobs.filter(queue_timeout__isnull=False)
    # TODO: use alias() once Debian 12 is required
    # See https://docs.djangoproject.com/en/dev/ref/models/querysets/#alias
    jobs = jobs.annotate(
        queue_timeout_date=ExpressionWrapper(
            F("submit_time") + datetime.timedelta(seconds=1) * F("queue_timeout"),
            output_field=DurationField(),
        )
    )
    jobs = jobs.filter(queue_timeout_date__lt=timezone.now())

    for testjob in jobs:
        LOGGER.debug("  |--> [%d] canceling", testjob.id)
        if testjob.is_multinode:
            for job in testjob.sub_jobs_list:
                fields = job.go_state_canceling()
                job.save(update_fields=fields)
        else:
            fields = testjob.go_state_canceling()
            testjob.save(update_fields=fields)
    LOGGER.info("done")


def schedule(workers) -> None:
    workers_limit = worker_summary(workers)
    already_scheduled_devices = schedule_health_checks(workers_limit)
    schedule_jobs(already_scheduled_devices, workers_limit)
    check_queue_timeout()


def schedule_health_checks(workers_limit) -> set[str]:
    LOGGER.info("scheduling health checks:")
    already_scheduled_devices: set[str] = set()
    hc_disabled: list[str] = []

    query = DeviceType.objects.filter(display=True)

    for dt in query.order_by("name"):
        if dt.disable_health_check:
            hc_disabled.append(dt.name)
        else:
            with transaction.atomic():
                schedule_health_checks_for_device_type(
                    dt, workers_limit, already_scheduled_devices
                )

    # Print disabled device types
    if hc_disabled:
        LOGGER.debug("-> disabled on: %s", ", ".join(hc_disabled))

    LOGGER.info("done")
    return already_scheduled_devices


def schedule_health_checks_for_device_type(
    dt: DeviceType, workers_limit, already_scheduled_devices: set[str]
):
    devices = dt.device_set.select_for_update()
    devices = filter_devices(devices, workers_limit.keys())
    devices = devices.filter(
        health__in=[Device.HEALTH_GOOD, Device.HEALTH_UNKNOWN, Device.HEALTH_LOOPING]
    )
    devices = devices.order_by("hostname")

    print_header = True
    for device in devices:
        if workers_limit[device.worker_host_id].overused():
            LOGGER.debug(
                "SKIP healthcheck for %s due to %s having %d jobs (greater than %d)"
                % (
                    device.hostname,
                    device.worker_host,
                    workers_limit[device.worker_host_id].busy,
                    workers_limit[device.worker_host_id].limit,
                )
            )
            continue
        # Do we have an health check
        health_check = device.get_health_check()
        if health_check is None:
            continue

        # Do we have to schedule an health check?
        scheduling = False
        if device.health in [Device.HEALTH_UNKNOWN, Device.HEALTH_LOOPING]:
            scheduling = True
        elif device.last_health_report_job is None:
            scheduling = True
        else:
            submit_time = device.last_health_report_job.submit_time
            if dt.health_denominator == DeviceType.HEALTH_PER_JOB:
                count = device.testjobs.filter(
                    health_check=False, start_time__gte=submit_time
                ).count()

                scheduling = count >= dt.health_frequency
            else:
                frequency = datetime.timedelta(hours=dt.health_frequency)
                now = timezone.now()

                scheduling = submit_time + frequency < now

        if not scheduling:
            continue

        # log some information
        if print_header:
            LOGGER.debug("- %s", dt.name)
            print_header = False

        LOGGER.debug(
            " -> %s (%s, %s)",
            device.hostname,
            device.get_state_display(),
            device.get_health_display(),
        )
        if not device.is_valid():
            prev_health_display = device.get_health_display()
            device.health = Device.HEALTH_BAD
            device.log_admin_entry(
                None,
                "%s → %s (Invalid device configuration)"
                % (prev_health_display, device.get_health_display()),
            )
            device.save(update_fields=["health"])
            LOGGER.debug(
                "%s → %s (Invalid device configuration for %s)"
                % (prev_health_display, device.get_health_display(), device.hostname)
            )
            continue
        LOGGER.debug("  |--> scheduling health check")
        try:
            schedule_health_check(device, health_check)
            workers_limit[device.worker_host_id].busy += 1
        except Exception as exc:
            # If the health check cannot be schedule, set health to BAD to exclude the device
            LOGGER.error("  |--> Unable to schedule health check")
            LOGGER.exception(exc)
            prev_health_display = device.get_health_display()
            device.health = Device.HEALTH_BAD
            device.log_admin_entry(
                None,
                "%s → %s (Invalid health check)"
                % (prev_health_display, device.get_health_display()),
            )
            device.save(update_fields=["health"])

        already_scheduled_devices.add(device.hostname)


def schedule_health_check(device, definition):
    user = User.objects.get(username="lava-health")
    job = _create_pipeline_job(
        yaml_safe_load(definition),
        user,
        [],
        device=device,
        device_type=device.device_type,
        orig=definition,
        health_check=True,
    )
    fields = job.go_state_scheduled(device)
    job.save(update_fields=fields)


def schedule_jobs(
    already_scheduled_devices: set[str],
    workers_limit,
):
    LOGGER.info("scheduling jobs:")

    with transaction.atomic():
        schedule_jobs_for_devices(
            already_scheduled_devices,
            workers_limit,
        )

    with transaction.atomic():
        # Transition multinode if needed
        transition_multinode_jobs()

    LOGGER.info("done")


def schedule_jobs_for_devices(
    already_scheduled_devices: set[str],
    workers_limit,
):
    devices = Device.objects.select_for_update()
    devices = filter_devices(devices, workers_limit.keys())
    devices = devices.filter(health__in=[Device.HEALTH_GOOD, Device.HEALTH_UNKNOWN])
    # Check that the device had not been already scheduled by
    # schedule_health_checks. In fact, it's possible that a device is made IDLE
    # between the two functions.  If that the case, we can miss an
    # health-check.
    devices = devices.exclude(hostname__in=already_scheduled_devices)
    # Only schedule device types that have jobs
    devices = (
        devices.annotate(
            _has_submitted_jobs=Exists(
                TestJob.objects.filter(
                    state=TestJob.STATE_SUBMITTED,
                    requested_device_type_id=OuterRef("device_type_id"),
                ).values("id")
            )
            # TODO: Pass Exists() directly to filter()
            # once Debian 12 is minimal version
        )
        .filter(_has_submitted_jobs=True)
        .annotate(_has_submitted_jobs=Value(1, output_field=IntegerField()))
    )
    # Add a random sort: with N devices and num(jobs) < N, if we don't sort
    # randomly, the same devices will always be used while the others will
    # never be used.
    devices = devices.order_by("?")

    print_header = True
    for device in devices:
        if workers_limit[device.worker_host_id].overused():
            LOGGER.debug(
                "SKIP %s due to %s having %d jobs (greater than %d)"
                % (
                    device.hostname,
                    device.worker_host,
                    workers_limit[device.worker_host_id].busy,
                    workers_limit[device.worker_host_id].limit,
                )
            )
            continue

        if not device.is_valid():
            prev_health_display = device.get_health_display()
            device.health = Device.HEALTH_BAD
            device.log_admin_entry(
                None,
                "%s → %s (Invalid device configuration)"
                % (prev_health_display, device.get_health_display()),
            )
            device.save(update_fields=["health"])
            LOGGER.debug(
                "%s → %s (Invalid device configuration for %s)"
                % (prev_health_display, device.get_health_display(), device.hostname)
            )
            continue

        if schedule_jobs_for_device(device, print_header) is not None:
            print_header = False
            workers_limit[device.worker_host_id].busy += 1


def schedule_jobs_for_device(device: Device, print_header: bool):
    job_extra_tags_subquery = Exists(
        Tag.objects.filter(testjob=OuterRef("pk")).exclude(pk__in=device.tags.all())
    )
    jobs = (
        TestJob.objects.select_for_update()
        .annotate(_tags_are_subset=~job_extra_tags_subquery)
        .filter(
            state=TestJob.STATE_SUBMITTED,
            actual_device__isnull=True,
            requested_device_type_id=device.device_type_id,
            # TODO: Pass ~job_extra_tags_subquery directly to filter()
            # once Debian 12 is minimal version
            _tags_are_subset=True,
        )
        .annotate(_tags_are_subset=Value(1, output_field=IntegerField()))
        .select_related("submitter")
        .order_by("-priority", "submit_time", "sub_id", "id")
    )

    with transaction.atomic():
        for job in jobs:
            if not device.can_submit(job.submitter):
                continue

            # Only load the yaml file if the string is in the document
            # This will save many CPU cycles
            if "lava-vland" in job.definition:
                job_dict = yaml_safe_load(job.definition)
                if "protocols" in job_dict and "lava-vland" in job_dict["protocols"]:
                    if not match_vlan_interface(device, job_dict):
                        continue

            if print_header:
                LOGGER.debug("- %s", device.device_type.name)

            LOGGER.debug(
                " -> %s (%s, %s)",
                device.hostname,
                device.get_state_display(),
                device.get_health_display(),
            )
            LOGGER.debug("  |--> [%d] scheduling", job.id)
            if job.is_multinode:
                # TODO: keep track of the multinode jobs
                fields = job.go_state_scheduling(device)
            else:
                fields = job.go_state_scheduled(device)
            job.save(update_fields=fields)
            return job.id

    return None


def transition_multinode_jobs():
    """
    Transition multinode jobs that are ready to be scheduled.
    A multinode is ready when all sub jobs are in STATE_SCHEDULING.
    """
    jobs = TestJob.objects.filter(state=TestJob.STATE_SCHEDULING)
    # Ordering by target_group is mandatory for distinct to work
    jobs = jobs.order_by("target_group", "id")
    jobs = jobs.distinct("target_group")

    for job in jobs:
        sub_jobs = job.sub_jobs_list
        if not all(
            [
                j.state == TestJob.STATE_SCHEDULING or j.dynamic_connection
                for j in sub_jobs
            ]
        ):
            continue

        LOGGER.debug("-> multinode [%d] scheduled", job.id)
        # Inject the actual group hostnames into the roles for the dispatcher
        # to populate in the overlay.
        devices = {}
        for sub_job in sub_jobs:
            # build a list of all devices in this group
            if sub_job.dynamic_connection:
                continue
            definition = yaml_safe_load(sub_job.definition)
            devices[str(sub_job.id)] = definition["protocols"]["lava-multinode"]["role"]

        for sub_job in sub_jobs:
            # apply the complete list to all jobs in this group
            definition = yaml_safe_load(sub_job.definition)
            definition["protocols"]["lava-multinode"]["roles"] = devices
            sub_job.definition = yaml_safe_dump(definition)
            # transition the job and device
            fields = ["definition"] + sub_job.go_state_scheduled()
            sub_job.save(update_fields=fields)
            LOGGER.debug("--> %d", sub_job.id)
