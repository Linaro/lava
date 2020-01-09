# -*- coding: utf-8 -*-
# Copyright (C) 2018 Linaro Limited
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

import datetime

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Case, When, IntegerField, Sum
from django.utils import timezone

from lava_common.compat import yaml_safe_load, yaml_safe_dump
from lava_scheduler_app.dbutils import match_vlan_interface
from lava_scheduler_app.models import (
    DeviceType,
    Device,
    _create_pipeline_job,
    TestJob,
    Worker,
)


def worker_summary():
    query = Worker.objects.all()
    query = query.values("hostname", "job_limit")
    query = query.annotate(
        busy=Sum(
            Case(
                When(
                    device__state__in=[Device.STATE_RESERVED, Device.STATE_RUNNING],
                    then=1,
                ),
                default=0,
                output_field=IntegerField(),
            )
        )
    )
    ret = {w["hostname"]: {"max": w["job_limit"], "busy": w["busy"]} for w in query}
    return ret


def schedule(logger, available_dt=None):
    (available_devices, jobs) = schedule_health_checks(logger, available_dt)
    jobs.extend(schedule_jobs(logger, available_devices))
    return jobs


def schedule_health_checks(logger, available_dt=None):
    logger.info("scheduling health checks:")
    available_devices = {}
    jobs = []
    hc_disabled = []
    query = DeviceType.objects.filter(display=True)
    if available_dt:
        query = DeviceType.objects.filter(name__in=available_dt, display=True)
    query = query.order_by("name").only("disable_health_check", "name")
    for dt in query:
        if dt.disable_health_check:
            hc_disabled.append(dt.name)
            # Add all devices of that type to the list of available devices
            devices = dt.device_set.filter(state=Device.STATE_IDLE)
            devices = devices.filter(worker_host__state=Worker.STATE_ONLINE)
            devices = devices.filter(
                health__in=[Device.HEALTH_GOOD, Device.HEALTH_UNKNOWN]
            )
            devices = devices.order_by("hostname")
            available_devices[dt.name] = list(
                devices.values_list("hostname", flat=True)
            )

        else:
            with transaction.atomic():
                (
                    available_devices[dt.name],
                    new_jobs,
                ) = schedule_health_checks_for_device_type(logger, dt)
                jobs.extend(new_jobs)

    # Print disabled device types
    if hc_disabled:
        logger.debug("-> disabled on: %s", ", ".join(hc_disabled))

    return (available_devices, jobs)


def schedule_health_checks_for_device_type(logger, dt):
    devices = dt.device_set.select_for_update()
    devices = devices.filter(state=Device.STATE_IDLE)
    devices = devices.filter(worker_host__state=Worker.STATE_ONLINE)
    devices = devices.filter(
        health__in=[Device.HEALTH_GOOD, Device.HEALTH_UNKNOWN, Device.HEALTH_LOOPING]
    )
    devices = devices.order_by("hostname")

    workers_limit = worker_summary()

    print_header = True
    available_devices = []
    jobs = []
    for device in devices:
        if (
            workers_limit[device.worker_host.hostname]["max"] > 0
            and workers_limit[device.worker_host.hostname]["busy"]
            >= workers_limit[device.worker_host.hostname]["max"]
        ):
            logger.debug(
                "SKIP healthcheck for %s due to %s having %d jobs (greater than %d)"
                % (
                    device.hostname,
                    device.worker_host,
                    workers_limit[device.worker_host.hostname]["busy"],
                    workers_limit[device.worker_host.hostname]["max"],
                )
            )
            continue
        # Do we have an health check
        health_check = device.get_health_check()
        if health_check is None:
            available_devices.append(device.hostname)
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
            available_devices.append(device.hostname)
            continue

        # log some information
        if print_header:
            logger.debug("- %s", dt.name)
            print_header = False

        logger.debug(
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
            device.save()
            logger.debug(
                "%s → %s (Invalid device configuration for %s)"
                % (prev_health_display, device.get_health_display(), device.hostname)
            )
            continue
        logger.debug("  |--> scheduling health check")
        try:
            jobs.append(schedule_health_check(device, health_check))
            workers_limit[device.worker_host.hostname]["busy"] += 1
        except Exception as exc:
            # If the health check cannot be schedule, set health to BAD to exclude the device
            logger.error("  |--> Unable to schedule health check")
            logger.exception(exc)
            prev_health_display = device.get_health_display()
            device.health = Device.HEALTH_BAD
            device.log_admin_entry(
                None,
                "%s → %s (Invalid health check)"
                % (prev_health_display, device.get_health_display()),
            )
            device.save()

    return (available_devices, jobs)


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
    job.go_state_scheduled(device)
    job.save()
    return job.id


def schedule_jobs(logger, available_devices):
    logger.info("scheduling jobs:")
    jobs = []
    for dt in DeviceType.objects.all().order_by("name"):
        # Check that some devices are available for this device-type
        if not available_devices.get(dt.name):
            continue
        with transaction.atomic():
            jobs.extend(
                schedule_jobs_for_device_type(logger, dt, available_devices[dt.name])
            )

    with transaction.atomic():
        # Transition multinode if needed
        jobs.extend(transition_multinode_jobs(logger))
    return jobs


def schedule_jobs_for_device_type(logger, dt, available_devices):
    logger.debug("- %s", dt.name)

    devices = dt.device_set.select_for_update()
    devices = devices.filter(state=Device.STATE_IDLE)
    devices = devices.filter(worker_host__state=Worker.STATE_ONLINE)
    devices = devices.filter(health__in=[Device.HEALTH_GOOD, Device.HEALTH_UNKNOWN])
    # Add a random sort: with N devices and num(jobs) < N, if we don't sort
    # randomly, the same devices will always be used while the others will
    # never be used.
    devices = devices.order_by("?")

    workers_limit = worker_summary()

    jobs = []
    for device in devices:
        # Check that the device had been marked available by
        # schedule_health_checks. In fact, it's possible that a device is made
        # IDLE between the two functions.
        if device.hostname not in available_devices:
            continue

        if (
            workers_limit[device.worker_host.hostname]["max"] > 0
            and workers_limit[device.worker_host.hostname]["busy"]
            >= workers_limit[device.worker_host.hostname]["max"]
        ):
            logger.debug(
                "SKIP %s due to %s having %d jobs (greater than %d)"
                % (
                    device.hostname,
                    device.worker_host,
                    workers_limit[device.worker_host.hostname]["busy"],
                    workers_limit[device.worker_host.hostname]["max"],
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
            device.save()
            logger.debug(
                "%s → %s (Invalid device configuration for %s)"
                % (prev_health_display, device.get_health_display(), device.hostname)
            )
            continue

        new_job = schedule_jobs_for_device(logger, device)
        if new_job is not None:
            jobs.append(new_job)
            workers_limit[device.worker_host.hostname]["busy"] += 1
    return jobs


def schedule_jobs_for_device(logger, device):
    jobs = TestJob.objects.filter(
        state__in=[TestJob.STATE_SUBMITTED, TestJob.STATE_SCHEDULING]
    )
    jobs = jobs.filter(actual_device__isnull=True)
    jobs = jobs.filter(requested_device_type__pk=device.device_type.pk)
    jobs = jobs.select_related("submitter")
    jobs = jobs.order_by("-state", "-priority", "submit_time", "target_group", "id")

    device_tags = set(device.tags.all())
    for job in jobs:
        if not device.can_submit(job.submitter):
            continue

        job_tags = set(job.tags.all())
        if not job_tags.issubset(device_tags):
            continue

        job_dict = yaml_safe_load(job.definition)
        if "protocols" in job_dict and "lava-vland" in job_dict["protocols"]:
            if not match_vlan_interface(device, job_dict):
                continue

        logger.debug(
            " -> %s (%s, %s)",
            device.hostname,
            device.get_state_display(),
            device.get_health_display(),
        )
        logger.debug("  |--> [%d] scheduling", job.id)
        if job.is_multinode:
            # TODO: keep track of the multinode jobs
            job.go_state_scheduling(device)
        else:
            job.go_state_scheduled(device)
        job.save()
        return job.id
    return None


def transition_multinode_jobs(logger):
    """
    Transition multinode jobs that are ready to be scheduled.
    A multinode is ready when all sub jobs are in STATE_SCHEDULING.
    """
    jobs = TestJob.objects.filter(state=TestJob.STATE_SCHEDULING)
    # Ordering by target_group is mandatory for distinct to work
    jobs = jobs.order_by("target_group", "id")
    jobs = jobs.distinct("target_group")

    new_jobs = []
    for job in jobs:
        sub_jobs = job.sub_jobs_list
        if not all(
            [
                j.state == TestJob.STATE_SCHEDULING or j.dynamic_connection
                for j in sub_jobs
            ]
        ):
            continue

        logger.debug("-> multinode [%d] scheduled", job.id)
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
            sub_job.go_state_scheduled()
            sub_job.save()
            new_jobs.append(sub_job.id)
    return new_jobs
