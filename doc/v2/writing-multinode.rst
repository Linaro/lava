.. _using_protocols:

Using Protocols
###############

Protocols are a way for the dispatcher to communicate with processes
using an established API to support actions running within the test
job. The protocol defines which API calls are available through the
LAVA interface and the Pipeline determines when the API call is made.

Not all protocols can be called from all actions. Not all protocols are
able to share data between actions.

.. _writing_multinode:

Writing MultiNode tests
***********************

LAVA supports running a single test across multiple devices, combining
groups of devices (of any type) within a group. Devices within the
same group can communicate with each other using the :ref:`multinode_api`.

The test definitions used in MultiNode tests do not have to differ from
single node tests, unless the tests need to support communication
between devices in the same group.

.. note:: when viewing MultiNode log files, the original YAML submitted
          to start the job is available as the MultiNode Definition.
          The other definition is the parsed content which was sent to
          each node within the MultiNode job to create one log file and
          one test job for each node. It is not usually useful to submit
          the definition of one node of a MultiNode job as a separate job.

.. _writing_multinode_protocol:

Writing jobs using the multinode protocol
*****************************************

The initial protocol available with the refactoring is Multinode. This
protocol defines the multinode group and also allows actions within the
Pipeline to make calls using the :ref:`multinode_api` outside of a
test definition.

The Multinode Protocol allows data to be shared between actions, including
data generated in one test shell definition being made available over the
protocol to a deploy or boot action of jobs with a different ``role``.

The Multinode Protocol can underpin the use of other tools without
necessarily needing a dedicated Protocol class to be written for those
tools. Using the Multinode Protocol is an extension of using the existing
:ref:`multinode_api` calls within a test definition. The use of the
protocol is an advanced use of LAVA and relies on the test writer
carefully planning how the job will work.

.. code-block:: yaml

        protocols:
          lava-multinode:
            action: umount-retry
            request: lava-sync
            messageID: test

This snippet would add a :ref:`lava_sync` call at the start of the
UmountRetry action:

Writing a MultiNode job file
****************************

The YAML job submission needs changes to combine the devices within the
protocol. Remove the current ``device_type`` line, if any, and specify
the LAVA multinode protocol roles.

.. code-block:: yaml

  protocols:
    lava-multinode:
      roles:
        client:
          device_type: qemu
          count: 1
          request: lava-start
          expect_role: server
        server:
          device_type: qemu
          count: 1
      timeout:
        minutes: 6

This example creates a group of three devices, two of the ``device_type``
panda and one of the ``device_type`` beaglebone-black. The :term:`role` is an
arbitrary label which can be used later in the testjob to determine which
tests are run on the devices and inside the test shell definition to
determine how the devices communicate.

This change is enough to run a Multi-Node test in LAVA. Each device will
use the same YAML file, running the tests independently on each device.

The next stage is to allow devices to run different tests according to
the ``role`` which the device will have during the test.

.. code-block:: yaml

    - deploy:
        timeout:
          minutes: 5
        to: tmpfs
        images:
            rootfs:
              image_arg: -drive format=raw,file={rootfs}
              url: http://images.validation.linaro.org/kvm-debian-wheezy.img.gz
              # url: file:///home/linaro/lava/kvm/kvm-debian-wheezy.img.gz
              compression: gz
        os: debian
        root_partition: 1
        role:
        - server

    - deploy:
        timeout:
          minutes: 5
        to: tmpfs
        images:
            rootfs:
              image_arg: -drive format=raw,file={rootfs}
              url: http://images.validation.linaro.org/kvm-debian-wheezy.img.gz
              # url: file:///home/linaro/lava/kvm/kvm-debian-wheezy.img.gz
              compression: gz
        os: debian
        root_partition: 1
        protocols:
          lava-multinode:
            api: lava-wait
            id: ipv4
            key: ipaddr
            timeout:
              minutes: 2
        role:
        - client

This will deploy the specified ``kvm-debian-wheezy.img.gz`` image on every
device in the group which is assigned the role ``server``. The second
deployment uses the protocol to make a call over the Multinode API
before the deploymet starts and will run on every device in
the group which is assigned the role ``client``.

Using MultiNode commands to synchronise devices
***********************************************

The most common requirement in a MultiNode test is that devices within
the group can be told to wait until another device in the group is
at a particular stage. This can be used to ensure that a device running
a server has had time to complete the boot and start the server before
the device running the client tries to make a connection to the server.
e.g. starting the server can involve installing the server and dependencies
and servers tend to have more dependencies than clients, so even if the
with similar devices, the only way to be sure that the server is ready
for client connections is to make every client in the group wait until
the server confirms that it is ready.

This is done using the :ref:`multinode_api` and :ref:`lava_wait`. The
YAML file specified for the role ``client`` causes the device to wait
until the YAML file specified for the role ``server`` uses
:ref:`lava_send` to signal that the server is ready.

The Multinode protocol provides support for using the Multinode API
outside of the test shell definition - any action block can now access
the protocol from within specific actions.

Each message sent using the MultiNode API uses a :term:`messageID` which
is a string, unique within the group. It is recommended to make these
strings descriptive using underscores instead of spaces. The messageID
will be included in the log files of the test.

In the YAML file to be used by devices with the role ``server``::

 run:
    steps:
        - apt-get install myserver
        - lava-send server_installed

In the YAML file to be used by devices with the role ``client``::

 run:
    steps:
        - lava-wait server_installed

This means that each device using the role ``client`` will wait until
**any** one device in the group sends a signal with the messageID of
``server_installed``. The assumption here is that the group only has
one device with the label ``server``.

If devices need to wait until all devices with a specified role send a
signal, the devices which need to wait need to use :ref:`lava_wait_all`.

If the expected messageID is never sent, the job will timeout when the
default timeout expires. See :ref:`timeouts`.

Using MultiNode commands to pass data between devices
*****************************************************

:ref:`lava_send` can be used to send data between devices. A device can
send data at any time, that data is then broadcast to all devices in the
same group. The data can be downloaded by any device in the group using
the messageID using :ref:`lava_wait` or :ref:`lava_wait_all`. Data is
sent as key value pairs.

.. note:: The message data is stored in a cache file which will be
   overwritten when the next synchronisation call is made. Ensure
   that your custom scripts make use of the data before the cache
   is cleared.

For example, if a device raises a network interface and wants to make
that data available to other devices in the group, the device can send
the IP address using ``lava-send``::

 run:
    steps:
       - lava-send ipv4 ip=$(./get_ip.sh)

The contents of ``get_ip.sh`` is operating system specific.

On the receiving device, the YAML includes a call to ``lava-wait``
or ``lava-wait-all`` with the same messageID::

 run:
    steps:
       - lava-wait ipv4
       - ipdata=$(cat /tmp/lava_multi_node_cache.txt | cut -d = -f 2)

.. note:: Although multiple key value pairs can be sent as a single message,
   the API is **not** intended for large amounts of data (messages larger
   than about 4Kb are considered large). Use other transfer protocols
   like ssh or wget to send large amounts of data between devices.

Helper tools in LAVA
====================

LAVA provides some helper routines for common data transfer tasks and
more can be added where appropriate. The main MultiNode API calls are
intended to support all POSIX systems but helper tools like
:ref:`lava_network` may be restricted to particular operating
systems or compatible shells due to a reliance on operating system
tools like ``ifconfig``.

Other MultiNode calls
=====================

It is also possible for devices to retrieve data about the group itself,
including the role or name of the current device as well as the names
and roles of other devices in the group. See :ref:`multinode_api` and
:ref:`multinode_use_cases` for more information.
