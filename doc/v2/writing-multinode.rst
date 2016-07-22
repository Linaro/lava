.. _writing_multinode:

Writing MultiNode tests
#######################

LAVA supports running a single test across multiple devices (of any
type), combining those devices into a group. Devices within this
MultiNode group can communicate with each other using the
:ref:`multinode_api`.

The test definitions used in MultiNode tests typically do not have to
differ much from single-node tests, unless the tests need to support
communication between devices in the same group. In fact, the
recommended way to develop MultiNode tests is to start simple and
build up complexity one step at a time. That's what the examples here
will show.

.. note:: when viewing MultiNode log files, the original YAML
          submitted to start the job is available as the MultiNode
          Definition. The other definition is the parsed content which
          was sent to each node within the MultiNode job to create a
          separate log file and test job for each node. It is not
          likely to be useful to submit the definition of one node of
          a MultiNode job as a separate job.

Writing a MultiNode job file
****************************

.. _multinode_roles:

Define MultiNode roles
======================

Assuming that you have an already-working simple test job, the first
changes to make are in device selection.

* First of all, remove the ``device_type`` declaration in the job as
  that only works for single devices.

* Next, add configuration for the MultiNode protocol. This will tell
  LAVA how to select multiple devices for your test.

The MultiNode protocol defines **roles**. This example snippet creates
a group of three devices, two of the ``device_type`` panda in the
``client`` role and one of the ``device_type`` beaglebone-black in the
``server`` role.

.. include:: examples/test-jobs/first-multinode-job.yaml
     :code: yaml
     :start-after: # START-BLOCK-1
     :end-before: # END-BLOCK-1

.. note:: The :term:`role` is an arbitrary label - you may use
	  whatever descriptive names you like for the different roles,
	  so long as they are unique.

The role names defined here will be used later in the test job to
determine which tests are run on which devices, and also inside the
test shell definition to determine how the devices communicate with
each other.

After just these changes, your test job will be enough to run a simple
MultiNode test in LAVA. It will pick several devices for the test,
then run exactly the same set of actions on each device independently.

Using your MultiNode roles
==========================

The next thing to do is to modify the test job such that it may run
different actions on each different device. This is done using the
``roles`` that were defined earlier. Each action in the test
definition should now include the ``role`` field and one or more
label(s) to match those defined ``roles``.

Here we deploy (slightly) different software to the ``server`` and
``client`` machines; look for ``role: server`` and ``role: client`` in
the two deploy blocks. In this case, the software is the same in both
cases *except* for the supplied DTB:

.. include:: examples/test-jobs/first-multinode-job.yaml
     :code: yaml
     :start-after: # START-BLOCK-2
     :end-before: # END-BLOCK-2

Here we can use *the same* boot actions for all the devices:

.. include:: examples/test-jobs/first-multinode-job.yaml
     :code: yaml
     :start-after: # START-BLOCK-3
     :end-before: # END-BLOCK-3

Using MultiNode commands to synchronise devices
***********************************************

.. include:: examples/test-jobs/first-multinode-job.yaml
     :code: yaml
     :start-after: # START-TEST-BLOCK
     :end-before: # END-TEST-BLOCK

A very common requirement in a MultiNode test is that a device (or
devices) within the MultiNode group can be told to wait until another
device in the group is at a particular stage. This can be used to
ensure that a device running a server has had time to complete the
boot and start the server before the device running the client tries
to make a connection to the server, for example. The only way to be
sure that the server is ready for client connections is to make every
client in the group wait until the server confirms that it is ready.

This is done using the :ref:`multinode_api` and :ref:`lava_wait`. The
test definition specified for the role ``client`` causes the device to
wait until the test definition specified for the role ``server`` uses
:ref:`lava_send` to signal that the server is ready.

The Multinode protocol also provides support for using the Multinode
API outside of the test shell definition - any action block can now
access the protocol from within specific actions. This makes it
possible to even block deployment or boot on one group of machines
before others are fully up and running. There is a lot of flexibility
here to allow for a wide range of test scenarios.

Each message sent using the MultiNode API uses a :term:`messageID` which
is a string, unique within the group. It is recommended to make these
strings descriptive using underscores instead of spaces. The messageID
will be included in the log files of the test.

In the test definition to be used by devices with the role
``server``:

.. include:: examples/test-jobs/first-multinode-job.yaml
     :code: yaml
     :start-after: # START-TEST-SERVER-BLOCK
     :end-before: # END-TEST-SERVER-BLOCK

.. include:: examples/test-jobs/first-multinode-job.yaml
     :code: yaml
     :start-after: # START-TEST-CLIENT-BLOCK
     :end-before: # END-TEST-CLIENT-BLOCK

# explain inline.

.. include:: examples/test-jobs/first-multinode-job.yaml
     :code: yaml
     :start-after: # START-TEST-SERVER-INLINE-BLOCK
     :end-before: # END-TEST-SERVER-INLINE-BLOCK

In the test definition for the ``client`` devices:

.. include:: examples/test-jobs/first-multinode-job.yaml
     :code: yaml
     :start-after: # START-TEST-CLIENT-INLINE-BLOCK
     :end-before: # END-TEST-CLIENT-INLINE-BLOCK

This means that each device using the role ``client`` will wait until
**any** one device in the group sends a signal with the messageID of
``server_installed``. The assumption here is that the group only has
one device with the label ``server``.

If devices need to wait until *all* devices with a specified role send
a signal, the devices which need to wait should instead use
:ref:`lava_wait_all`.

If the expected messageID is never sent, the job will timeout when the
default timeout expires. See :ref:`timeouts`.

Using MultiNode commands to pass data between devices
*****************************************************

:ref:`lava_send` can be used to send data between devices. A device
can send data at any time, and that data will be broadcast to all
devices in the MultiNode group. The data can be downloaded by any
device in the group using the messageID using :ref:`lava_wait` or
:ref:`lava_wait_all`. Data is sent as key-value pairs.

.. note:: The message data is stored in a cache file which will be
   overwritten when the next synchronisation call is made. Ensure that
   your scripts make use of (or copy aside) any MultiNode cache data
   before calling any other MultiNode API helpers that may clear the
   cache.

For example, if a device raises a network interface and wants to make
data about that network connection available to other devices in the
group, the device can send the IP address using ``lava-send``::

 run:
    steps:
       - lava-send ipv4 ip=$(./get_ip.sh)

The contents of ``get_ip.sh`` is operating system specific.

On the receiving device, the test definition would include a call to
``lava-wait`` or ``lava-wait-all`` with the same messageID::

 run:
    steps:
       - lava-wait ipv4
       - ipdata=$(cat /tmp/lava_multi_node_cache.txt | cut -d = -f 2)

.. note:: Although multiple key value pairs can be sent as a single message,
   the API is **not** intended for large amounts of data (messages larger
   than about 4KB are considered large). Use other transfer protocols
   like ssh or wget to send large amounts of data between devices.

Helper tools in LAVA
====================

LAVA provides some helper routines for common data transfer tasks and
more can be added where appropriate. The main MultiNode API calls are
intended to work on all POSIX systems, but some of the helper tools
like :ref:`lava_network` may be restricted to particular operating
systems or compatible shells due to a reliance on operating system
tools like ``ifconfig``.

Other MultiNode calls
=====================

It is also possible for devices to retrieve data about the group itself,
including the role or name of the current device as well as the names
and roles of other devices in the group. See :ref:`multinode_api` and
:ref:`multinode_use_cases` for more information.

.. _writing_multinode_protocol:

Writing jobs using the MultiNode protocol
*****************************************

The MultiNode protocol defines the MultiNode group and also allows
actions within the job Pipeline to make calls using the
:ref:`multinode_api` outside of a test definition.

The MultiNode protocol allows data to be shared between actions,
including data generated in one test shell definition being made
available over the protocol to a deploy or boot action of jobs with a
different ``role``.

The Multinode protocol can underpin the use of other tools without
necessarily needing a dedicated protocol class to be written for those
tools. Using the Multinode protocol is an extension of using the
existing :ref:`multinode_api` calls within a test definition. The use
of the protocol is an advanced use of LAVA and relies on the test
writer carefully planning how the job will work.



This snippet would add a :ref:`lava_sync` call at the start of the
UmountRetry action:

.. code-block:: yaml

  protocols:
    lava-multinode:
      action: umount-retry
      request: lava-sync
      messageID: test
