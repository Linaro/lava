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

Create your *qemu-arm01.conf* file:

::

    # /etc/lava-dispatcher/devices/qemu-arm01.conf
    device_type = qemu-arm

At this point the dispatcher should work. You can test it locally by creating
a minimal job file:

::

    # /tmp/qemu-arm.json
    {
      "timeout": 18000,
      "job_name": "qemu-arm-test",
      "device_type": "qemu-arm",
      "target": "qemu-arm01",
      "actions": [
        {
            "command": "deploy_linaro_kernel",
            "parameters": {
                "kernel": "http://images.validation.linaro.org/functional-test-images/qemu-arm/zImage-qemuarm.bin",
                "login_prompt": "login:",
                "rootfs": "http://images.validation.linaro.org/functional-test-images/qemu-arm/core-image-minimal-qemuarm.ext3",
                "username": "root"
            }
        },
        {
            "command": "boot_linaro_image",
            "parameters": {
                "test_image_prompt": "root@qemu-system-arm:~#"
            }
        }
      ]
    }

And execute the dispatcher with:

::

    lava-dispatch /tmp/qemu.json

Configure the Scheduler
-----------------------

Now that the dispatcher understand the QEMU device and can work with it, we
need to inform the LAVA scheduler about it. This is done from the admin panel
in the LAVA web app.

You'll first add a "qemu-arm" device type by going to a URL like::

 http://localhost/admin/lava_scheduler_app/devicetype/

That page will give you an option to add a device type. From the add device
type page, you need to give the name "qemu-arm". Don't touch any of the other
options for now.

After adding a device type you can add a device. From this page you'll want
to set the hostname to the same value you set for 'target' in the dispatch
config. Then select "qemu-arm" from the device type list.

Now when you view::

 http://localhost/scheduler/

You should see your new device type and be able to drill down to the device.

Submitting a QEMU Job
---------------------

The scheduler documentation includes instructions for :ref:`job_submission` to
LAVA. You can use the job file shown above as the basis for your new job.
