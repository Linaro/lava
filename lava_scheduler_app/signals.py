import datetime
from django.conf import settings
from django.db.models.signals import post_init, post_save
import json
import os
import pwd
import threading
import uuid
import zmq
from zmq.utils.strtypes import b

from lava_scheduler_app.models import Device


# Thread local storage for zmq socket and context
thread_local = threading.local()


def device_init_handler(sender, **kwargs):
    # This function is called for every Device object created
    # Save the old status
    instance = kwargs["instance"]
    instance._old_status = instance.status


def device_post_handler(sender, **kwargs):
    # Called only when a Device is saved into the database
    instance = kwargs["instance"]

    # Send a signal if the status changed
    if instance.status != instance._old_status:
        # Update the status as some objects are save many times.
        # Even if an object is saved many time, we will send messages only when
        # the status change.
        instance._old_status = instance.status
        # Get back the thread local storage
        try:
            context = thread_local.context
            socket = thread_local.socket
            user = thread_local.user
        except AttributeError:
            # Create the context and socket
            thread_local.context = context = zmq.Context.instance()
            thread_local.socket = socket = context.socket(zmq.PUSH)
            thread_local.user = user = pwd.getpwuid(os.geteuid()).pw_name
            socket.connect(settings.INTERNAL_EVENT_SOCKET)

        # Create the message
        data = {
            "status": instance.STATUS_CHOICES[instance.status][1],
            "device": instance.hostname,
            "device_type": instance.device_type.name,
        }
        if instance.current_job:
            data["job"] = instance.current_job.display_id

        # The format is [topic, uuid, datetime, username, data as json]
        msg = [
            b(settings.EVENT_TOPIC + '.device'),
            str(uuid.uuid1()),
            datetime.datetime.utcnow().isoformat(),
            user,
            json.dumps(data)
        ]
        # Send the message in the non-blockng mode.
        # If the consumer (lava-publisher) is not active, the message will be lost.
        socket.send_multipart(msg, zmq.DONTWAIT)


post_init.connect(device_init_handler, sender=Device, weak=False, dispatch_uid="device_init_handler")
post_save.connect(device_post_handler, sender=Device, weak=False, dispatch_uid="device_post_handler")
