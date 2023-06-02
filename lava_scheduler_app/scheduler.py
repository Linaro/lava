# Copyright (C) 2018 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import datetime
from dataclasses import dataclass

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from lava_common.yaml import yaml_safe_dump, yaml_safe_load
from lava_scheduler_app.dbutils import match_vlan_interface
from lava_scheduler_app.models import (
    Device,
    DeviceType,
    TestJob,
    Worker,
    _create_pipeline_job,
)


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


def worker_summary():
    query = Worker.objects.all()
    query = query.values("hostname", "job_limit")
    query = query.annotate(
        busy=Count(
            "device",
            filter=Q(device__state__in=(Device.STATE_RESERVED, Device.STATE_RUNNING)),
        )
    )
    ret = {w["hostname"]: WorkerSummary(w["job_limit"], w["busy"]) for w in query}
    return ret


def check_queue_timeout(logger):
    logger.info("Check queue timeouts:")
    jobs = TestJob.objects.filter(
        state=TestJob.STATE_SUBMITTED, queue_timeout__isnull=False
    )
    for testjob in jobs:
        now = timezone.now()
        queue_timeout_delta = datetime.timedelta(seconds=testjob.queue_timeout)
        canceling = testjob.submit_time + queue_timeout_delta < now
        if canceling:
            logger.debug("  |--> [%d] canceling", testjob.id)
            if testjob.is_multinode:
                for job in testjob.sub_jobs_list:
                    job.go_state_canceling()
                    job.save()
            else:
                testjob.go_state_canceling()
                testjob.save()
    logger.info("done")


def schedule(logger, available_dt, workers):
    available_devices = schedule_health_checks(logger, available_dt, workers)
    schedule_jobs(logger, available_devices, workers)
    check_queue_timeout(logger)


def schedule_health_checks(logger, available_dt, workers):
    logger.info("scheduling health checks:")
    available_devices = {}
    hc_disabled = []

    query = DeviceType.objects.filter(display=True)
    if available_dt:
        query = query.filter(name__in=available_dt)

    for dt in query.order_by("name"):
        if dt.disable_health_check:
            hc_disabled.append(dt.name)
            # Add all devices of that type to the list of available devices
            devices = filter_devices(dt.device_set, workers)
            devices = devices.filter(
                health__in=[Device.HEALTH_GOOD, Device.HEALTH_UNKNOWN]
            )
            devices = devices.order_by("hostname")
            available_devices[dt.name] = list(
                devices.values_list("hostname", flat=True)
            )

        else:
            with transaction.atomic():
                available_devices[dt.name] = schedule_health_checks_for_device_type(
                    logger, dt, workers
                )

    # Print disabled device types
    if hc_disabled:
        logger.debug("-> disabled on: %s", ", ".join(hc_disabled))

    logger.info("done")
    return available_devices


def schedule_health_checks_for_device_type(logger, dt, workers):
    devices = dt.device_set.select_for_update()
    devices = filter_devices(devices, workers)
    devices = devices.filter(
        health__in=[Device.HEALTH_GOOD, Device.HEALTH_UNKNOWN, Device.HEALTH_LOOPING]
    )
    devices = devices.order_by("hostname")

    workers_limit = worker_summary()

    print_header = True
    available_devices = []
    for device in devices:
        if workers_limit[device.worker_host.hostname].overused():
            logger.debug(
                "SKIP healthcheck for %s due to %s having %d jobs (greater than %d)"
                % (
                    device.hostname,
                    device.worker_host,
                    workers_limit[device.worker_host.hostname].busy,
                    workers_limit[device.worker_host.hostname].limit,
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
            schedule_health_check(device, health_check)
            workers_limit[device.worker_host.hostname].busy += 1
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

    return available_devices


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


def schedule_jobs(logger, available_devices, workers):
    logger.info("scheduling jobs:")
    dts = list(available_devices.keys())
    for dt in DeviceType.objects.filter(name__in=dts).order_by("name"):
        with transaction.atomic():
            schedule_jobs_for_device_type(
                logger, dt, available_devices[dt.name], workers
            )

    with transaction.atomic():
        # Transition multinode if needed
        transition_multinode_jobs(logger)

    logger.info("done")


def schedule_jobs_for_device_type(logger, dt, available_devices, workers):
    devices = dt.device_set.select_for_update()
    devices = filter_devices(devices, workers)
    devices = devices.filter(health__in=[Device.HEALTH_GOOD, Device.HEALTH_UNKNOWN])
    # Add a random sort: with N devices and num(jobs) < N, if we don't sort
    # randomly, the same devices will always be used while the others will
    # never be used.
    devices = devices.order_by("?")

    workers_limit = worker_summary()

    print_header = True
    for device in devices:
        # Check that the device had been marked available by
        # schedule_health_checks. In fact, it's possible that a device is made
        # IDLE between the two functions.
        # If that the case, we can miss an health-check. Better to only
        # consider devices in available_devices.
        if device.hostname not in available_devices:
            continue

        if workers_limit[device.worker_host.hostname].overused():
            logger.debug(
                "SKIP %s due to %s having %d jobs (greater than %d)"
                % (
                    device.hostname,
                    device.worker_host,
                    workers_limit[device.worker_host.hostname].busy,
                    workers_limit[device.worker_host.hostname].limit,
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

        if schedule_jobs_for_device(logger, device, print_header) is not None:
            print_header = False
            workers_limit[device.worker_host.hostname].busy += 1


def schedule_jobs_for_device(logger, device, print_header):
    jobs = TestJob.objects.filter(state=TestJob.STATE_SUBMITTED)
    jobs = jobs.filter(actual_device__isnull=True)
    jobs = jobs.filter(requested_device_type__pk=device.device_type.pk)
    jobs = jobs.select_related("submitter")
    jobs = jobs.order_by("-priority", "submit_time", "sub_id", "id")

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

        if print_header:
            logger.debug("- %s", device.device_type.name)

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
            logger.debug("--> %d", sub_job.id)
