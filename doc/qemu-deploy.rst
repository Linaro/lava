Deploying a QEMU Device
=======================

Adding a QEMU device to LAVA is an easy way to make sure things work without
having to worry about connecting to a physical device and setting up a master
image. This page outlines the steps required to add a new QEMU device to your
LAVA deployment and make it able to accept job requests.

For an alternative with less overhead than QEMU, see `Adding a KVM Device`_.

.. _`Adding a KVM Device`: kvm-deploy.html

Install QEMU
------------

Install the *qemu-system* package on the server::

   # sudo apt-get install qemu-system

Configure the Dispatcher
------------------------

Create your *qemu01.conf* file:

::

    # If the lava-dispatcher directory exists but not the devices directory,
    # create a directory for the devices.
    # mkdir /srv/lava/instances/<INST>/etc/lava-dispatcher/devices/
    # /srv/lava/instances/<INST>/etc/lava-dispatcher/devices/qemu01.conf
    device_type = qemu

You'll need to download an image to test with. The Linaro download servers
have some click-through licensing logic that makes downloading from the
dispatcher difficult, so its easiest to first download an image locally
using your browser. You can download a QEMU image `here`_ to your /tmp
directory.

.. _here: http://releases.linaro.org/images/12.03/oneiric/nano/beagle-nano.img.gz

At this point the dispatcher should work. You can test it locally by creating
a minimal job file:

::

    # /tmp/qemu.json
    {
      "timeout": 18000,
      "job_name": "qemu-test",
      "device_type": "qemu",
      "target": "qemu01",
      "actions": [
        {
          "command": "deploy_linaro_image",
          "parameters": {
            "image": "file:///tmp/beagle-nano.img.gz"
            }
        },
        {
          "command": "boot_linaro_image"
        }
      ]
    }

And execute the dispatcher with:

::

    . /srv/lava/instances/<INST>/bin/activate
    lava-dispatch /tmp/qemu.json

Configure the Scheduler
-----------------------

Now that the dispatcher understand the QEMU device and can work with it, we
need to inform the LAVA scheduler about it. This is done from the admin panel
in the LAVA web app.

You'll first add a "qemu" device type by going to a URL like:
 http://localhost/admin/lava_scheduler_app/devicetype/

That page will give you an option to add a device type. From the add device
type page, you need to give the name "qemu". Don't touch any of the other
options for now.

After adding a device type you can add a device. From this page you'll want
to set the hostname to the same value you set for 'target' in the dispatch
config. Then select "qemu" from the device type list.

Now when you view:
 http://localhost/scheduler/

You should see your new device type and be able to drill down to the device.

Submitting a QEMU Job
---------------------

The scheduler documentation includes instructions for `submitting a job`_ to
LAVA. You can use the job file shown above as the basis for your new job.

.. _submitting a job: http://lava-scheduler.readthedocs.org/en/latest/usage.html#submitting-jobs
