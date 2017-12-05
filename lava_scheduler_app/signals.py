from __future__ import unicode_literals

import datetime
from django.conf import settings
from django.db.models.signals import post_init, post_save
import json
import threading
import uuid
import zmq
from zmq.utils.strtypes import b

from lava_scheduler_app.models import Device, TestJob, Worker


# Thread local storage for zmq socket and context
thread_local = threading.local()


def send_event(topic, user, data):
    # Get back the thread local storage
    try:
        context = thread_local.context
        socket = thread_local.socket
    except AttributeError:
        # Create the context and socket
        thread_local.context = context = zmq.Context.instance()
        thread_local.socket = socket = context.socket(zmq.PUSH)
        socket.connect(settings.INTERNAL_EVENT_SOCKET)

    try:
        # The format is [topic, uuid, datetime, username, data as json]
        msg = [
            b(settings.EVENT_TOPIC + topic),
            b(str(uuid.uuid1())),
            b(datetime.datetime.utcnow().isoformat()),
            b(user),
            b(json.dumps(data))
        ]
        # Send the message in the non-blockng mode.
        # If the consumer (lava-publisher) is not active, the message will be lost.
        socket.send_multipart(msg, zmq.DONTWAIT)
    except (TypeError, ValueError, zmq.ZMQError):
        # The event can't be send, just skip it
        print("Unable to send the zmq event %s" % (settings.EVENT_TOPIC + topic))


def device_init_handler(sender, **kwargs):
    # This function is called for every Device object created
    # Save the old states
    instance = kwargs["instance"]
    instance._old_health = instance.health
    instance._old_state = instance.state


def device_post_handler(sender, **kwargs):
    # Called only when a Device is saved into the database
    instance = kwargs["instance"]

    # Send a signal if the state or health changed
    if (instance.health != instance._old_health) or (instance.state != instance._old_state):
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
            "pipeline": instance.is_pipeline,
        }
        current_job = instance.current_job()
        if current_job is not None:
            data["job"] = current_job.display_id

        # Send the event
        send_event(".device", "lavaserver", data)


def testjob_init_handler(sender, **kwargs):
    # This function is called for every testJob object created
    # Save the old states
    instance = kwargs["instance"]
    instance._old_health = instance.health
    instance._old_state = instance.state


def testjob_post_handler(sender, **kwargs):
    # Called only when a Device is saved into the database
    instance = kwargs["instance"]

    # Send a signal if the state or health changed
    if (instance.health != instance._old_health) or (instance.state != instance._old_state):
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
            "visibility": instance.get_visibility_display(),
            "pipeline": instance.is_pipeline,
        }
        if instance.is_multinode:
            data['sub_id'] = instance.sub_id
        if instance.health_check:
            data['health_check'] = True
        if instance.actual_device:
            data["device"] = instance.actual_device.hostname
        if instance.requested_device_type:
            data['device_type'] = instance.requested_device_type.name
        if instance.start_time:
            data["start_time"] = instance.start_time.isoformat()
        if instance.end_time:
            data["end_time"] = instance.end_time.isoformat()

        # Send the event
        send_event(".testjob", str(instance.submitter), data)


def worker_init_handler(sender, **kwargs):
    # This function is called for every testJob object created
    # Save the old states
    instance = kwargs["instance"]
    instance._old_health = instance.health
    instance._old_state = instance.state


def worker_post_handler(sender, **kwargs):
    # Called only when a Worker is saved into the database
    instance = kwargs["instance"]

    if (instance.health != instance._old_health) or (instance.state != instance._old_state):
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


post_init.connect(device_init_handler, sender=Device, weak=False, dispatch_uid="device_init_handler")
post_save.connect(device_post_handler, sender=Device, weak=False, dispatch_uid="device_post_handler")
post_init.connect(testjob_init_handler, sender=TestJob, weak=False, dispatch_uid="testjob_init_handler")
post_save.connect(testjob_post_handler, sender=TestJob, weak=False, dispatch_uid="testjob_post_handler")
post_init.connect(worker_init_handler, sender=Worker, weak=False, dispatch_uid="worker_init_handler")
post_save.connect(worker_post_handler, sender=Worker, weak=False, dispatch_uid="worker_post_handler")
