.. index:: MultiNode - writing multinode tests

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

.. note:: When viewing MultiNode log files, the original YAML
   submitted to start the job is available via the ``MultiNode
   Definition`` link. Internally, LAVA parses and splits up that
   MultiNode definition into multiple sub-definitions, one per node in
   the test. Each node will then see a separate logical test job (and
   therefore a separate log file) based on these sub-definitions. They
   can be viewed via the ``Definition`` link. It is unlikely to be
   useful to submit the definition of one node of a MultiNode job as a
   separate job, due to links between the jobs.

.. index:: MultiNode - writing test jobs

.. _writing_multinode_job_file:

Writing a MultiNode job file
****************************

Our first example is the simplest possible MultiNode test job - the
same job runs on two devices of the same type, without using any of
the synchronisation calls.

.. index:: MultiNode job context, MultiNode roles

.. _multinode_roles:

Defining MultiNode roles
========================

Starting with an already-working simple single-device test job, the
first changes to make are in device selection:

* Remove the ``device_type`` declaration in the job; that only works
  for single devices.

* Add configuration for the MultiNode protocol to tell LAVA how to
  select multiple devices for your test.

The MultiNode protocol defines the new concept of **roles**. This
example snippet creates a group of two ``qemu`` devices, one in the
``foo`` role and one in the ``bar`` role.

.. include:: examples/test-jobs/first-multinode-job.yaml
     :code: yaml
     :start-after: # START-PROTOCOLS-BLOCK
     :end-before: # END-PROTOCOLS-BLOCK

.. note:: The :term:`role` is an arbitrary label - you may use
   whatever descriptive names you like for the different roles in your
   test, so long as they are unique.

Using the job context in MultiNode
----------------------------------

The :term:`job context` can be included in the MultiNode :term:`role` and the
same variables will be used for all devices within the specified role. See the
example above for an example syntax.

The role names defined here will be used later in the test job to
determine which tests are run on which devices, and also inside the
test shell definition to determine how the devices communicate with
each other. After just these changes, your test job will be enough to
run a simple MultiNode test in LAVA. It will pick several devices for
the test, then run exactly the same set of actions on each device
independently.

.. index:: MultiNode - using roles

.. _using_multinode_roles:

Using MultiNode roles
=====================

The next thing to do is to modify the test job to use the roles that
you have defined. This first example runs the same actions on both of
the roles. Each action in the test definition should now include the
``role`` field and one or more label(s) to match those defined
``roles``.

Here we deploy the same software to the ``foo`` and
``bar`` machines by specifying each role in a list:

.. include:: examples/test-jobs/first-multinode-job.yaml
     :code: yaml
     :start-after: # START-DEPLOY-BLOCK
     :end-before: # END-DEPLOY-BLOCK

We also use the same boot actions for all the devices:

.. include:: examples/test-jobs/first-multinode-job.yaml
     :code: yaml
     :start-after: # START-BOOT-BLOCK
     :end-before: # END-BOOT-BLOCK

.. _running_multinode_tests:

Running tests in MultiNode
**************************

By default, tests in MultiNode jobs will be run independently. If that
is sufficient, the test action is very similar to that for a
single-node job:

.. include:: examples/test-jobs/first-multinode-job.yaml
     :code: yaml
     :start-after: # START-TEST-BLOCK
     :end-before: # END-TEST-BLOCK

That's your first MultiNode test job complete. It's quite simple to
follow, but it hasn't really done much yet. To see this in action, you
could try the complete example test job yourself:
`first-multinode-job.yaml
<examples/test-jobs/first-multinode-job.yaml>`_

.. _multinode_different_tests:

Running different tests on different devices
********************************************

As well as simply running the same tasks on similar devices, MultiNode
can also run different tests on the different devices in the test. To
configure this, use the ``role`` support to allocate different
``deploy``, ``boot`` and ``test`` actions to different roles.

This second example will use two ``panda`` devices and one
``beaglebone-black`` device. These devices need different files to
deploy and different commands to boot, and will most likely take
different lengths of time to boot all the way to a login prompt. If
you want to run this example test job yourself, you will need at least
one ``beaglebone-black`` device and at least two ``panda`` devices.

The example includes details of how to deploy to devices using
`U-Boot`_, but don't worry about those details. The important elements
from a MultiNode perspective are the uses of ``role`` here.

.. _`U-Boot`: http://www.denx.de/wiki/U-Boot

Allocating different device types to a group
============================================

This is a simple change from our first example, defining the two roles
of ``server`` and ``client``:

.. include:: examples/test-jobs/second-multinode-job.yaml
     :code: yaml
     :start-after: # START-PROTOCOLS-BLOCK
     :end-before: # END-PROTOCOLS-BLOCK

Splitting deployment actions between roles
==========================================

Now we're using different files in the deployment for each role. To
support that, we define two separate ``deploy`` action blocks, one for
the ``server`` machines and one for the ``client`` machines.

.. include:: examples/test-jobs/second-multinode-job.yaml
     :code: yaml
     :start-after: # START-DEPLOY-BLOCK
     :end-before: # END-DEPLOY-BLOCK

(Potentially) Splitting boot actions
====================================

To cover different boot commands we could now have two different
``boot`` action blocks. But in this case our devices behave in the
same way in terms of bootup, so we can just use a single ``boot``
block and list both ``client`` and ``server``.

.. include:: examples/test-jobs/second-multinode-job.yaml
     :code: yaml
     :start-after: # START-BOOT-BLOCK
     :end-before: # END-BOOT-BLOCK

.. _using_multinode_synchronisation:

Using MultiNode commands to synchronise devices
***********************************************

A very common requirement in a MultiNode test is that a device (or
devices) within the MultiNode group must wait until another device in
the group reaches a particular stage. This can be used to ensure that
a device running a server has had time to complete the boot and start
the server before the device running the client tries to make a
connection to the server, for example. The only way to be sure that
the server is ready for client connections is to make every client in
the group wait until the server confirms that it is ready.

Continuing with the same ``panda`` and ``beaglebone-black`` example,
let's look at synchronising devices within a MultiNode group.

Controlling synchronisation from the test shell
===============================================

Synchronisation is done using the :ref:`multinode_api`, specifically
the :ref:`lava_send` and :ref:`lava_wait` calls.

.. seealso:: :ref:`multinode_further_features`

Continuing our example, we have two different versions of the ``test``
action block. In the version for the ``server`` role, the machine will
do some work (in this case, install and start the Apache web server)
and then tell the clients that the server is ready using
:ref:`lava_send`:

.. include:: examples/test-jobs/second-multinode-job.yaml
     :code: yaml
     :start-after: # START-TEST-SERVER-BLOCK
     :end-before: # END-TEST-SERVER-BLOCK

.. note:: It is recommended to use :term:`inline` definitions for the
   calls to the synchronisation helpers. This makes it much easier to
   debug when a synchronisation call times out and will allow the
   *flow* of the MultiNode job to be summarised in the UI.

The test definition specified for the ``client`` role causes the
client devices to wait until the test definition specified for the
``server`` role uses :ref:`lava_send` to signal that the server is
ready.

.. include:: examples/test-jobs/second-multinode-job.yaml
     :code: yaml
     :start-after: # START-TEST-CLIENT-BLOCK
     :end-before: # END-TEST-CLIENT-BLOCK

This means that each device using the role ``client`` will wait until
**any** one device in the group sends a signal with the messageID of
``server_installed``. The assumption here is that the group only has
one device with the label ``server``.

The second MultiNode example is now complete. To run this yourself,
you can see the complete example test job: `second-multinode-job.yaml
<examples/test-jobs/second-multinode-job.yaml>`_

HERE. Remember, you'll need specific hardware devices for this to
work.

Controlling synchronisation from the dispatcher
===============================================

The MultiNode protocol *also* provides support for using the MultiNode
API outside of the test shell definition; any action block can access
the protocol from within specific actions. This makes it possible to
even block deployment or boot on one group of machines until others
are fully up and running, for example. There is a lot of flexibility
here to allow for a massive range of possible test scenarios.

.. seealso:: :ref:`writing_multinode_protocol` for more information on
   how to call the MultiNode API outside the test shell.

.. _multinode_further_features:

Using the MultiNode API - further features
******************************************

As demonstrated earlier, tests can use :ref:`lava_wait` to cause a
device to wait on a single message from any other device in the
MultiNode group. It is also possible to wait for *all* other devices
in the MultiNode group send a signal - use :ref:`lava_wait_all`
instead.

Each message sent using the MultiNode API uses a :term:`messageID`,
which is a string that must be unique within the group. It is
recommended to make these strings descriptive to help track job
progress and debug problems. Be careful to use underscores instead of
spaces in the name. The messageID will be included in the log files of
the test.

.. warning:: When using :ref:`lava_wait` and :ref:`lava_wait_all`, the
   device will wait until the expected messageID is received. If that
   messageID does not arrive, the job will simply wait forever and
   timeout when the default timeout expires. See :ref:`timeouts`.

.. _multinode_data_between_devices:

Using MultiNode commands to pass data between devices
=====================================================

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

.. note:: Although multiple key value pairs can be sent as a single
   message, the API is **not** intended for large amounts of
   data. There is a message size limit of 4KiB, including protocol
   overhead. Use other transfer methods like ssh or wget if you need
   to send larger amounts of data between devices.

.. _multinode_helper_tools:

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

It is also possible for devices to retrieve data about the group
itself, including the role or name of the current device as well as
the names and roles of other devices in the group. See
:ref:`multinode_api` for more information.

.. _writing_multinode_protocol:

Writing jobs using the MultiNode protocol
*****************************************

The MultiNode protocol defines the MultiNode group and also allows
actions within the job pipeline to make calls using the
:ref:`multinode_api` outside of a test definition.

The MultiNode protocol allows data to be shared between actions,
including data generated in a test shell definition for one role being
made available for use by a different role in its deploy or boot
action.

The MultiNode protocol can underpin the use of other tools without
necessarily needing a dedicated protocol class to be written for those
tools. Using the MultiNode protocol is an extension of using the
existing :ref:`multinode_api` calls within a test definition. The use
of the protocol is an advanced use of LAVA and relies on the test
writer carefully planning how the job will work. See
`_delayed_start_multinode` for an example of how to use this.

.. FIXME: write the advanced example for this section
