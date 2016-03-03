.. _deploy_kvm:

Deploying a KVM (x86_64) Device
===============================

.. warning:: This chapter discusses a model of device support
   which is being superceded by the :term:`pipeline` model.

Adding a KVM device to LAVA is an easy way to make sure things work without
having to worry about connecting to a physical device and setting up a master
image. This page outlines the steps required to add a new KVM device to your
LAVA deployment and make it able to accept job requests.

Obtain an image
---------------

A variety of `pre-built images`_ are available for download::

 http://images.validation.linaro.org/kvm/

.. _`pre-built images`: http://images.validation.linaro.org/kvm/

Building KVM images for LAVA
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If the prebuilt images are not suitable, new images can be built using
`vmdebootstrap`_. See also :ref:`deploy_linaro_image`.

.. note:: image building tools are constantly developing and this
   guide can easily become out of date, so you will need to read the
   manpages for the tools and update the instructions appropiately.

::

 sudo apt install vmdebootstrap

.. _`vmdebootstrap`: http://packages.qa.debian.org/v/vmdebootstrap.html

The default distribution is Debian stable.

Example invocation::

 $ sudo vmdebootstrap --image=myimage.img --verbose --serial-console --enable-dhcp

To run the test image, use the ``--owner=$(whoami)`` option to
``vmdebootstrap`` or make sure it is writeable::

 $ sudo chmod a+w ./myimage.img

Execute using qemu, e.g. on amd64 using qemu-system-x86_64::

 $ qemu-system-x86_64 ./myimage.img

Newer versions of qemu will complain about the format, so check the
manpage and use something like::

 $ qemu-system-x86_64 -m 1024 -enable-kvm -drive format=raw,file=./myimage.img

See ``man 1 vmdebootstrap`` and ``man qemu-system`` for more information.

Adding a KVM device to LAVA
============================

You can use the :ref:`admin_helpers` support::

 $ sudo /usr/share/lava-server/add_device.py kvm kvm01

* Add the ``root_part = 1`` line to the device configuration
* Configure :ref:`kvm_networking`

Configure the dispatcher manually
---------------------------------

Create your *kvm01.conf* file with the following content::

    device_type = kvm
    root_part = 1

Sample job file (replace ``file:///path/to/kvm.img`` with the actual
location where you placed the image you created in the previous step)::

    {
      "timeout": 18000,
      "job_name": "kvm-test",
      "device_type": "kvm",
      "target": "kvm01",
      "actions": [
        {
          "command": "deploy_linaro_image",
          "parameters": {
            "image": "file:///path/to/kvm.img"
            }
        },
        {
          "command": "boot_linaro_image"
        }
      ]
    }

To test, you can execute the dispatcher directly with the following
command as ``root``::

 lava-dispatch /tmp/kvm.json

.. _kvm_networking:

Optional: networking configuration
----------------------------------

By default, LAVA ``kvm`` devices will use ``virtio`` networking, which
is a lot faster than the QEMU default at the time of writing this. But
the default configuration also uses NAT, which makes the virtual
machines unacessible from other hosts in your local network.

Setting up a TAP device for KVM networking is a way to both make
networking faster *and* make the virtual machines available from other
nodes in the network.

This requires some extra configuration, and that's why it's not the
default. It goes like this:

Device configuration file(``kvmXX.conf``)::

    device_type = kvm
    root_part = 1
    kvm_networking_options = -net nic,model=virtio -net tap

Then add a bridge interface to the networking configuration
(``/etc/network/interfaces``). Example::

    auto eth0
    iface eth0 inet manual

    auto br0
        iface br0 inet dhcp
        bridge_ports eth0
        bridge_stp off
        bridge_fd 0
        bridge_maxwait 0

Please note the above are examples, as we do not want to duplicate the
QEMU documentation. Make sure you consult the official QEMU
documentation for detailed instructions on how to create a proper TAP
interface setup.

Configuring the scheduler manually
----------------------------------

Now that the dispatcher understand the KVM device and can work with it, we
need to inform the LAVA scheduler about it. This is done from the admin panel
in the LAVA web app.

You'll first add a "kvm" device type by going to a URL like::

 http://localhost/admin/lava_scheduler_app/devicetype/

That page will give you an option to add a device type. From the add device
type page, you need to give the name "kvm". Don't touch any of the other
options for now.

After adding a device type you can add a device. From this page you'll want
to set the hostname to the same value you set for 'target' in the dispatch
config. Then select "kvm" from the device type list.

Now when you view::

 http://localhost/scheduler/

You should see your new device type and be able to drill down to the device.

Submitting a KVM Job
====================

The scheduler documentation includes instructions for :ref:`job_submission` to
LAVA. You can use the job file shown above as the basis for your new job.
