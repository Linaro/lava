# Copyright (C) 2011-2018 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import datetime
import logging
import uuid
from contextvars import ContextVar
from functools import wraps
from json import dumps as json_dumps

import zmq
from django.conf import settings
from django.db import transaction
from django.db.models.signals import post_init, post_save, pre_delete

from lava_scheduler_app.models import Device, TestJob, Worker
from lava_scheduler_app.tasks import async_send_notifications


# Wrapper to except every exception and only log them
# If signal handlers are raising, this is breaking many important stuffs
def log_exception(func):
    @wraps(func)
    def function_wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            logger = logging.getLogger("lava-scheduler")
            logger.error("Unable to execute signal '%s', ignoring", func.__name__)
            logger.exception(exc)

    return function_wrapper


zmq_context: ContextVar[zmq.Context] = ContextVar("zmq_context")
zmq_socket: ContextVar[zmq.Socket] = ContextVar("zmq_socket")


def send_event(topic, user, data):
    # Get back the thread local storage
    try:
        context = zmq_context.get()
        socket = zmq_socket.get()
    except LookupError:
        # Create the context and socket
        context = zmq.Context.instance()
        socket = context.socket(zmq.PUSH)
        socket.connect(settings.INTERNAL_EVENT_SOCKET)

        zmq_context.set(context)
        zmq_socket.set(socket)

    try:
        # The format is [topic, uuid, datetime, username, data as json]
        msg = [
            (settings.EVENT_TOPIC + topic).encode(),
            str(uuid.uuid1()).encode(),
            datetime.datetime.utcnow().isoformat().encode(),
            user.encode(),
            json_dumps(data).encode(),
        ]
        # Send the message in the non-blockng mode.
        # If the consumer (lava-publisher) is not active, the message will be lost.
        socket.send_multipart(msg, zmq.DONTWAIT)
    except (TypeError, ValueError, zmq.ZMQError):
        # The event can't be send, just skip it
        print("Unable to send the zmq event %s" % (settings.EVENT_TOPIC + topic))


@log_exception
def device_init_handler(sender, **kwargs):
    # This function is called for every Device object created
    # Save the old states
    instance = kwargs["instance"]
    instance._old_health = instance.health
    instance._old_state = instance.state


@log_exception
def device_post_handler(sender, **kwargs):
    # Called only when a Device is saved into the database
    instance = kwargs["instance"]

    # Send a signal if the state or health changed
    if (instance.health != instance._old_health) or (
        instance.state != instance._old_state
    ):
        # Update the states as some objects are save many times.
        # Even if an object is saved many time, we will send messages only when
        # the state change.
        instance._old_health = instance.health
        instance._old_state = instance.state

        # Create the message
        data = {
            "health": instance.get_health_display(),
            "state": instance.get_state_display(),
            "device": instance.hostname,
            "device_type": instance.device_type.name,
            "worker": None,
        }
        current_job = instance.current_job()
        if current_job is not None:
            data["job"] = current_job.display_id
            if instance.health == instance.HEALTH_RETIRED:
                current_job.cancel(current_job.submitter)
        if instance.worker_host is not None:
            data["worker"] = instance.worker_host.hostname

        # Send the event
        send_event(".device", "lavaserver", data)


@log_exception
def testjob_init_handler(sender, **kwargs):
    # This function is called for every testJob object created
    # Save the old states
    instance = kwargs["instance"]
    instance._old_health = instance.health
    instance._old_state = instance.state


@log_exception
def testjob_notifications(sender, **kwargs):
    job = kwargs["instance"]
    # If it's a new TestJob, no need to send notifications.
    if not job.id:
        return

    # Only notify when the state changed
    if job._old_state == job.state:
        return
    if job.state not in [TestJob.STATE_RUNNING, TestJob.STATE_FINISHED]:
        return

    async_send_notifications.delay(job.id, job.state, job.health, job._old_health)


@log_exception
def testjob_post_handler(sender, **kwargs):
    # Called only when a Device is saved into the database
    instance = kwargs["instance"]

    # Send a signal if the state or health changed
    if (
        (instance.health != instance._old_health)
        or (instance.state != instance._old_state)
        or instance.state == TestJob.STATE_SUBMITTED
    ):
        # Update the states as some objects are save many times.
        # Even if an object is saved many time, we will send messages only when
        # the states change.
        instance._old_health = instance.health
        instance._old_state = instance.state

        # Create the message
        data = {
            "health": instance.get_health_display(),
            "state": instance.get_state_display(),
            "job": instance.id,
            "description": instance.description,
            "priority": instance.priority,
            "submit_time": instance.submit_time.isoformat(),
            "submitter": str(instance.submitter),
            "health_check": instance.health_check,
        }
        if instance.is_multinode:
            data["sub_id"] = instance.sub_id
        if instance.actual_device:
            data["device"] = instance.actual_device.hostname
            if instance.actual_device.worker_host:
                data["worker"] = instance.actual_device.worker_host.hostname
        if instance.requested_device_type:
            data["device_type"] = instance.requested_device_type.name
        if instance.start_time:
            data["start_time"] = instance.start_time.isoformat()
        if instance.end_time:
            data["end_time"] = instance.end_time.isoformat()

        # Send the event
        send_event(".testjob", str(instance.submitter), data)


@log_exception
def testjob_pre_delete_handler(sender, **kwargs):
    instance = kwargs["instance"]
    with transaction.atomic():
        instance.go_state_finished(TestJob.HEALTH_CANCELED, True)


@log_exception
def worker_init_handler(sender, **kwargs):
    # This function is called for every testJob object created
    # Save the old states
    instance = kwargs["instance"]
    instance._old_health = instance.health
    instance._old_state = instance.state


@log_exception
def worker_post_handler(sender, **kwargs):
    # Called only when a Worker is saved into the database
    instance = kwargs["instance"]

    if (instance.health != instance._old_health) or (
        instance.state != instance._old_state
    ):
        # Update the states as some objects are save many times.
        # Even if an object is saved many time, we will send messages only when
        # the state change.
        instance._old_health = instance.health
        instance._old_state = instance.state

        # Create the message
        data = {
            "hostname": instance.hostname,
            "health": instance.get_health_display(),
            "state": instance.get_state_display(),
        }

        # Send the event
        send_event(".worker", "lavaserver", data)


pre_delete.connect(
    testjob_pre_delete_handler,
    sender=TestJob,
    weak=False,
    dispatch_uid="testjob_pre_delete_handler",
)
# This handler is used for the notification and the events
post_init.connect(
    testjob_init_handler,
    sender=TestJob,
    weak=False,
    dispatch_uid="testjob_init_handler",
)
post_save.connect(
    testjob_notifications,
    sender=TestJob,
    weak=False,
    dispatch_uid="testjob_notifications",
)

# Only activate these signals when EVENT_NOTIFICATION is in use
if settings.EVENT_NOTIFICATION:
    post_init.connect(
        device_init_handler,
        sender=Device,
        weak=False,
        dispatch_uid="device_init_handler",
    )
    post_save.connect(
        device_post_handler,
        sender=Device,
        weak=False,
        dispatch_uid="device_post_handler",
    )
    post_save.connect(
        testjob_post_handler,
        sender=TestJob,
        weak=False,
        dispatch_uid="testjob_post_handler",
    )
    post_init.connect(
        worker_init_handler,
        sender=Worker,
        weak=False,
        dispatch_uid="worker_init_handler",
    )
    post_save.connect(
        worker_post_handler,
        sender=Worker,
        weak=False,
        dispatch_uid="worker_post_handler",
    )
