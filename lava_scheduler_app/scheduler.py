# -*- coding: utf-8 -*-
#
# Copyright (C) 2017 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# This file is part of LAVA Dispatcher.
#
# LAVA Dispatcher is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# LAVA Dispatcher is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses>.

import datetime
import yaml

from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone

from lava_scheduler_app.dbutils import match_vlan_interface
from lava_scheduler_app.models import (
    DeviceType,
    Device,
    _create_pipeline_job,
    TestJob,
    Worker
)


def schedule(logger):
    available_devices = schedule_health_checks(logger)
    schedule_jobs(logger, available_devices)


def schedule_health_checks(logger):
    logger.info("scheduling health checks:")
    available_devices = {}
    hc_disabled = []
    for dt in DeviceType.objects.all().order_by("name"):
        if dt.disable_health_check:
            hc_disabled.append(dt.name)
            # Add all devices o that type to the list of available devices
            devices = dt.device_set.filter(state=Device.STATE_IDLE)
            devices = devices.filter(worker_host__state=Worker.STATE_ONLINE)
            devices = devices.filter(health__in=[Device.HEALTH_GOOD,
                                                 Device.HEALTH_UNKNOWN])
            devices = devices.order_by("hostname")
            available_devices[dt.name] = list(devices.values_list("hostname", flat=True))

        else:
            with transaction.atomic():
                available_devices[dt.name] = schedule_health_checks_for_device_type(logger, dt)

    # Print disabled device types
    if hc_disabled:
        logger.debug("-> disabled on: %s", ", ".join(hc_disabled))

    return available_devices


def schedule_health_checks_for_device_type(logger, dt):
    devices = dt.device_set.select_for_update()
    devices = devices.filter(state=Device.STATE_IDLE)
    devices = devices.filter(worker_host__state=Worker.STATE_ONLINE)
    devices = devices.filter(health__in=[Device.HEALTH_GOOD,
                                         Device.HEALTH_UNKNOWN,
                                         Device.HEALTH_LOOPING])
    devices = devices.order_by("hostname")

    print_header = True
    available_devices = []
    for device in devices:
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
            if dt.health_denominator == DeviceType.HEALTH_PER_JOB:
                start_time = device.last_health_report_job.start_time
                count = device.testjobs.filter(health_check=False,
                                               start_time__gte=start_time).count()

                scheduling = count > dt.health_frequency
            else:
                last_hc = device.last_health_report_job.end_time
                frequency = datetime.timedelta(hours=dt.health_frequency)
                now = timezone.now()

                scheduling = last_hc + frequency < now

        if not scheduling:
            available_devices.append(device.hostname)
            continue

        # log some information
        if print_header:
            logger.debug("- %s", dt.name)
            print_header = False

        logger.debug(" -> %s (%s, %s)", device.hostname,
                     device.get_state_display(),
                     device.get_health_display())
        logger.debug("  |--> scheduling health check")
        schedule_health_check(device, health_check)

    return available_devices


def schedule_health_check(device, definition):
    user = User.objects.get(username="lava-health")
    job = _create_pipeline_job(yaml.load(definition), user, [], device_type=device.device_type, orig=definition)
    job.health_check = True
    job.go_state_scheduled(device)
    job.save()


def schedule_jobs(logger, available_devices):
    logger.info("scheduling jobs:")
    for dt in DeviceType.objects.all().order_by("name"):
        # Check that some devices are available for this device-type
        if not available_devices.get(dt.name):
            continue
        with transaction.atomic():
            schedule_jobs_for_device_type(logger, dt, available_devices[dt.name])

    with transaction.atomic():
        # Transition multinode if needed
        transition_multinode_jobs(logger)


def schedule_jobs_for_device_type(logger, dt, available_devices):
    logger.debug("- %s", dt.name)

    devices = dt.device_set.select_for_update()
    devices = devices.filter(state=Device.STATE_IDLE)
    devices = devices.filter(worker_host__state=Worker.STATE_ONLINE)
    devices = devices.filter(health__in=[Device.HEALTH_GOOD,
                                         Device.HEALTH_UNKNOWN])
    devices = devices.order_by("is_public", "hostname")

    for device in devices:
        # Check that the device had been marked available by
        # schedule_health_checks. In fact, it's possible that a device is made
        # IDLE between the two functions.
        if device.hostname not in available_devices:
            continue
        schedule_jobs_for_device(logger, device)


def schedule_jobs_for_device(logger, device):
    jobs = TestJob.objects.filter(state__in=[TestJob.STATE_SUBMITTED,
                                             TestJob.STATE_SCHEDULING])
    jobs = jobs.filter(actual_device__isnull=True)
    jobs = jobs.filter(requested_device_type__pk=device.device_type.pk)
    jobs = jobs.order_by("-state", "-priority", "submit_time", "target_group", "id")

    for job in jobs:
        if not device.can_submit(job.submitter):
            continue

        device_tags = set(device.tags.all())
        job_tags = set(job.tags.all())
        if not job_tags.issubset(device_tags):
            continue

        job_dict = yaml.load(job.definition)
        if 'protocols' in job_dict and 'lava-vland' in job_dict['protocols']:
            if not match_vlan_interface(device, job_dict):
                continue

        logger.debug(" -> %s (%s, %s)", device.hostname,
                     device.get_state_display(),
                     device.get_health_display())
        logger.debug("  |--> [%d] scheduling", job.id)
        if job.is_multinode:
            # TODO: keep track of the multinode jobs
            job.go_state_scheduling(device)
        else:
            job.go_state_scheduled(device)
        job.save()
        break


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
        if not all([j.state == TestJob.STATE_SCHEDULING or j.dynamic_connection for j in sub_jobs]):
            continue

        logger.debug("-> multinode [%d] scheduled", job.id)
        # Inject the actual group hostnames into the roles for the dispatcher
        # to populate in the overlay.
        devices = {}
        for sub_job in sub_jobs:
            # build a list of all devices in this group
            if sub_job.dynamic_connection:
                continue
            definition = yaml.load(sub_job.definition)
            devices[str(sub_job.id)] = definition['protocols']['lava-multinode']['role']

        for sub_job in sub_jobs:
            # apply the complete list to all jobs in this group
            definition = yaml.load(sub_job.definition)
            definition['protocols']['lava-multinode']['roles'] = devices
            sub_job.definition = yaml.dump(definition)
            # transition the job and device
            sub_job.go_state_scheduled()
            sub_job.save()
