.. index:: connection

.. _connections:

Connections
###########

A ``connection`` is how LAVA handles talking to a device, for example
via an automated login session on a serial port on the device or
within a virtual machine hosted by a device. Some devices can support
multiple connections. LAVA can use more than one connection in a test
job, but the first connection is particularly important - this is
where initial control of booting will happen, and kernel messages will
normally go here.

The most common type of connection that LAVA will use is a serial
connection to the test device, but other connection methods are also
supported (such as SSH and USB). For a connection method to work, it
needs to be supported by software in LAVA, services within the
software running on the device and typically lab infrastructure too,
e.g. a serial console server.

As an example, many devices are capable of supporting SSH connections
as long as:

* the device can be configured to raise a usable network interface
* the device is booted into a suitable software environment which will
  run an ssh server

USB connections for Android support can be implemented inside test
shells using the :term:`LXC` support.

.. index:: connections - device configuration

.. _connections_in_device_configuration:

Connections in device configuration
***********************************

For the connections to a device to be made available for test usage,
they need to be declared in the device configuration, e.g.:

.. code-block:: yaml

  deploy:
    methods:
      tftp
      ssh

  boot:
    connections:
      - serial
      - ssh
    methods:
      qemu:
    prompts:
      - 'linaro-test'
      - 'root@debian:~#'

.. index:: connections - test job

.. _connections_in_test_jobs:

Connections in test jobs
************************

Connections are created in a test job using the ``boot`` action; it
must specify the connection ``method`` as a parameter:

.. code-block:: yaml

    - boot:
        method: qemu
        media: tmpfs
        connection: serial
        failure_retry: 2
        prompts:
          - 'root@debian:~#'

.. note:: :ref:`defaults` - although ``serial`` is the traditional
          (and previously default) way of connecting to LAVA devices,
          it is **not** assumed and must be explicitly specified in
          the test job YAML.

The connection created here will be used later by the ``test`` action
blocks defined in the test job, so they depend on the ``boot`` action
to define the connection. Even where test jobs may not actually cause
a test device to *boot* per se, LAVA needs the test job to include a
``boot`` action for this purpose.

For basic test jobs, this describes all the information that most test
writers will need to understand. However, there are several more
advanced connection options that may be useful, depending on the type
of device and the tests required.

.. index:: connections - namespaces

.. _connections_and_namespaces:

Connections and namespaces
**************************

Internally, LAVA uses a ``namespace`` structure to track dynamic data
inside a test job. One of the pieces of data tracked in a namespace is
the connection in use; this is how the connection created in the
``boot`` action block can be shared throughout the job in further
actions.

In a job definition where multiple deploy, boot and test actions are
specified, there must be a mechanism to describe how the actions are
connected. This is the primary purpose of a namespace; it is the way
to tie related actions together. This is important - consider how an
overlay created during a deploy action will be consumed by a test
action somewhere down the job definition, for example.

.. seealso:: :ref:`namespaces_with_lxc`.

In a simple job, it is often not necessary to even consider this use
of namespaces. If no other namespaces are defined explicitly in a test
job, LAVA will create an implicit namespace called ``common``. The
default primary serial connection created in the ``boot`` action block
will be stored in the ``common`` namespace, and the ``test`` action
block(s) will use it from there.

If more than one connection is desired in a test job, then the way to
control which connection is used in each action block is by explicitly
defining appropriate namespaces. Here's an example using ``serial``
and ``lxc`` connections with a Beaglebone device. Look for
``namespace: inside_lxc`` and ``namespace: testdevice`` in the action
blocks:

.. literalinclude:: examples/test-jobs/namespace-connections-example1.yaml
     :language: yaml
     :linenos:
     :lines: 31-90
     :emphasize-lines: 3, 14, 31, 40, 52


Download or view the complete example:
`examples/test-jobs/namespace-connections-example1.yaml
<examples/test-jobs/namespace-connections-example1.yaml>`_:

.. note:: It is not allowed to combine the ``common`` namespace with any others
   - it is special-cased. If you are defining more namespaces in your job, give
   them clear descriptive names that are unique within that job.

.. index:: multiple serial, multiple uart

.. _multiple_serial_support:

Multiple serial port support
****************************

.. _simple_job_flow:

Background
==========

On common test devices where LAVA interacts with the device using a
serial connection, there is typically a simple flow to the test job,
running through the action blocks defined in that test job:

* ``deploy`` block:

  * Set up job artifacts for the test job

* ``boot`` block:

  * Start the device
  * Connect to the serial port
  * Control the boot loader to boot the desired artifacts
  * Read kernel boot messages - the serial connection is the kernel
    console
  * Wait for the specified prompt to appear, and log in if needed

* ``test`` block:

  * Assume the device is waiting for input at a shell prompt
  * Send shell commands over the serial connection to run tests
  * Read back the results of those tests from that same serial
    connection

* (implicit) job cleanup block:

  * Disconnect from the serial port
  * Shutdown the device

Even in this simple setup, there is a potential problem. The single
serial connection is used for output both by the test shell **and**
the kernel. Ideally, this should not cause any problems, but in the
real world it is all too common for kernel log messages to be
interleaved with test output. This could be something simple and
expected (e.g. a test action bringing up a network interface will
cause the driver for that interface to announce link state), or it
could be something unexpected (e.g. the kernel reporting hardware
failure from an unrelated driver, or a malformed network packet). As
the kernel messages and the test shell output are interleaved on a
character-by-character basis, it often is impossible to parse
each. This can cause tests to fail in unexpected ways, or it can cause
LAVA to fail to parse test output and so log incomplete or incorrect
test results.

Over the years, the LAVA developers have worked to reduce the impact
of this problem, but it is fundamentally impossible to solve it while
kernel messages and test shell output are sharing the same
connection. It **is** possible to change the logging level of the
kernel to reduce the number or frequency of its messages, but often
those messages are critical information when debugging a fault so this
is not a good solution for everybody.

.. index:: kernel messages - interleaving, serial corruption

.. _isolating_kernel_messages:

Isolating kernel messages from test output
==========================================

The only reliable way to solve the problem with interleaving and
corrupted test shell output and kernel messages is to isolate them
physically, on different connections.

For some time, LAVA has had support for driving multiple connections
to a device independently, using :ref:`secondary connections
<secondary_connection>`. This can be a great solution for many test
requirements, but doesn't solve all problems for all people. It
depends on being able to start extra connections via the network
(typically SSH or telnet), so on test devices without functional
networking support it cannot work. It also requires tests to be
written using the :term:`MultiNode` protocol, which can add
considerable complexity to an otherwise simple test job.

As an alternative, many test devices include more than one hardware
serial port. Most such devices will use just one of those serial ports
for firmware, bootloader and kernel messages (a *primary
console*). Linux will then start a ``getty`` process (a serial login
program) on that primary console. If more serial ports are available,
connecting those ports and configuring the test OS to spawn more
``getty`` processes is an easy way to get more connections. These
extra connections are all independent from the primary, so it is safe
to run test shell commands on these without interleaving test output
with kernel message output.

LAVA supports using these multiple serial connections in a simple way,
avoiding the need for MultiNode complexity.

.. seealso:: :ref:`test_definition_kmsg` for a mitigation of the
   interleaving problem if multiple UART support is not available.

.. _extra_serial_ports_modify_test_image:

Changes needed in the test image
================================

In common with the ``ssh`` method, the use of multiple serial
connections involves some risks because the creation of the ``getty``
on the additional serial port(s) is managed by the kernel and rootfs
of the **test image**. When using multiple serial connections, always
test that the booted system raises the ``getty`` correctly and that
the ``login`` process works before committing to using this method.

.. index:: connections - adding extra serial ports

.. _adding_extra_serial_ports:

Adding extra serial ports to a test device
==========================================

There is one hard dependency here: if you want to use multiple serial
ports, your device must have them available! This can be a
problem. Some embedded devices may have many UARTs available, but not
all of them might be exposed for use. If you're testing x86 devices,
many computers may only have one serial port. This is not necessarily
an insurmountable problem. Although the firmware, bootloader and
kernel may only talk to the primary serial console for boot messages,
once you have a Linux kernel up and running it's normally easy to add
extra ports by simply plugging in a USB serial adapter. Configure the
test system to start a getty on ``/dev/ttyUSB0`` and connect
cables. Don't get carried away, though - adding more than one USB
serial adapter can lead to confusion on the device as to which
connection is which! If you have PCI ports, PCI serial cards are also
readily available.

Also consider the cost and complexity of extra cabling (and
dispatcher-side connections) when adding more serial connections. You
may benefit from daughter cards or mezzanine boards to expose multiple
serial connections over one cable.

.. index:: connections - configuring serial ports, device dictionary - connections

.. _configuring_serial_ports:

Configuring serial ports
========================

To configure LAVA to connect to one or more serial ports of a device, create a
list of ``connection_commands`` in the :ref:`device dictionary
<device_dictionary_connections>`. LAVA will use the command tagged with
``primary`` to open the connection early in test job startup (in the first
``boot`` action) , and will keep this connection open right until the end of
the test job.

In earlier versions of LAVA, only a single connection command could be used:

.. code-block:: jinja

 {% extends 'beaglebone-black.jinja2' %}
 {% set power_off_command = '/usr/bin/pduclient --daemon localhost --hostname pdu01 --command off --port 12' %}
 {% set hard_reset_command = '/usr/bin/pduclient --daemon localhost --hostname pdu01 --command reboot --port 12' %}
 {% set connection_command = 'telnet dispatcher01 7001' %}
 {% set power_on_command = '/usr/bin/pduclient --daemon localhost --hostname pdu01 --command on --port 12' %}

This has worked fine when just using a single serial connection but is now
deprecated to support working with more than one and other improvements in
connection handling. The ``connection_list`` is a more flexible way to
configure one or more serial ports:

.. code-block:: jinja

 {% extends 'beaglebone-black.jinja2' %}
 {% set power_off_command = '/usr/bin/pduclient --daemon localhost --hostname pdu01 --command off --port 12' %}
 {% set hard_reset_command = '/usr/bin/pduclient --daemon localhost --hostname pdu01 --command reboot --port 12' %}
 {% set power_on_command = '/usr/bin/pduclient --daemon localhost --hostname pdu01 --command on --port 12' %}
 {% set connection_list = ['uart0'] %}
 {% set connection_commands = {'uart0': 'telnet dispatcher01 7001'} %}
 {% set connection_tags = {'uart0': ['primary', 'telnet']} %}

``primary`` denotes the serial connection which will be started automatically
with each test job.

Other tags describe how LAVA should close the connection at the end of the
test job, possible values are ``telnet``, ``ssh``. If your connection command
does not use ``telnet`` or ``ssh``, the connection will be forcibly closed
using ``kill -9``.

Or with two serial connections:

.. code-block:: jinja

 {% extends 'beaglebone-black.jinja2' %}
 {% set power_off_command = '/usr/bin/pduclient --daemon localhost --hostname pdu01 --command off --port 12' %}
 {% set hard_reset_command = '/usr/bin/pduclient --daemon localhost --hostname pdu01 --command reboot --port 12' %}
 {% set power_on_command = '/usr/bin/pduclient --daemon localhost --hostname pdu01 --command on --port 12' %}
 {% set connection_list = ['uart0', 'uart1'] %}
 {% set connection_commands = {'uart0': 'telnet dispatcher01 7001', 'uart1': 'telnet dispatcher01 7002'} %}
 {% set connection_tags = {'uart0': ['primary', 'telnet'], 'uart1': ['telnet']} %}

This defines two serial ports (labeled ``uart0`` and ``uart``), then
describes how to connect to each one. Finally, it sets a ``tag`` of
``primary`` on ``uart0`` - this tells LAVA that ``uart0`` is the
primary connection, the one used for boot and kernel messages. This
makes ``uart0`` exactly equivalent to the single serial connection
defined in the previous example. In future, more connection tags might
be added with extra meaning.

LAVA now (as of writing in October 2017) supports either of these
methods to configure serial ports, but at some point in the future the
older ``connection_command`` method may be deprecated. **The two
methods may not be mixed in the same device dictionary - either define
a single ``connection_command`` or use the new list of connections.**

.. index:: connections - using multiple serial ports, second uart

.. _using_multiple_serial_ports:

Using multiple serial ports
***************************

For a typical device with multiple serial ports, we can extend our
:ref:`simple job flow <simple_job_flow>` above (changes in **bold**):

* ``deploy`` block:

  * Set up job artifacts for the test job

* first ``boot`` block:

  * Start the device
  * Connect to the **primary** serial port, **creating an explicit
    namespace for later actions to use it**
  * Control the boot loader to boot the desired artifacts
  * Read kernel boot messages - the **primary** serial connection is
    the kernel console
  * Wait for the specified prompt to appear, and log in if needed

* (optional) first  ``test`` block:

  * Tests to run using the **primary** serial port, **via the
    namespace created for it**. *(This is likely to be empty, in which
    case you can just leave this test block out altogether)*

* **second** ``boot`` block:

  * **Start a new connection to a non-primary serial port, and create
    a new namespace for it**
  * Wait for the specified prompt to appear **on the non-primary
    serial port**, and log in if needed

* second ``test`` block:

  * Assume the device is waiting for input at a shell prompt
  * Send shell commands over the **non-primary** serial connection to
    run tests
  * read back the results of those tests on the **non-primary** serial
    connection
  * **in the background, listen to the existing serial port
    connection for kernel messages (feedback)**

* (implicit) job cleanup:

  * disconnect from the serial ports
  * shutdown the device

.. note:: To use the extra serial port here, the operating system
          image on the test device will also need to be configured to
          start a ``getty`` on the extra serial port. This can be done
          in the image as it is prepared, or alternatively it could be
          started by logging in using the test action on the primary
          console. That latter approach might seem to be the obvious
          path, but **again** beware of serial corruption causing
          problems. The period during and immediately after boot is
	  when kernel messages are most likely to be intermingled with
	  attempts to control a device on the primary console.

.. index:: connections - multiple serial ports example

.. _multiple_serial_ports_example1:

Example job 1: Simple beaglebone-black job with a second serial port
====================================================================

Here's a simple test job on a common board, a Beaglebone Black. The
board only exposes one serial port for easy use, so we've added a USB
serial adapter as a second port.

Download or view the complete example:
`examples/test-jobs/bbb-2serial.yaml
<examples/test-jobs/bbb-2serial.yaml>`_:

#. :ref:`multiple_serial_ports_example1_boot_device`

#. :ref:`multiple_serial_ports_example1_boot_connection`

#. :ref:`multiple_serial_ports_example1_test_connection`

.. _multiple_serial_ports_example1_boot_device:

Deploy and boot the device
--------------------------

This is using a simple Debian Stretch nfs rootfs and initramfs. The
rootfs is easy to generate using standard tools; the only change in
there is to define the second serial console on
/dev/ttyUSB0. `Remember <extra_serial_ports_modify_test_image>`_ that
a similar change will likely be needed in any test image you want to
test this way. Note the explicit namespace ``bbb`` defined in the
``deploy`` action, and created in the ``boot`` action:

.. literalinclude:: examples/test-jobs/bbb-2serial.yaml
     :language: yaml
     :linenos:
     :lines: 23-53
     :emphasize-lines: 2,21,25-26

A ``boot`` action would typically include an ``auto_login`` section,
but in this test we're not going to be doing any testing using the
primary serial connection. Hence, we just add a ``prompts`` section
looking for ``login:`` to check when this boot is complete.

.. _multiple_serial_ports_example1_boot_connection:

Create the connection to the second serial port
-----------------------------------------------

Next, we use a second ``boot`` action block to create a new connection
**in a new namespace** called ``isolation``. We're using the
``new_connection`` method, using the ``uart1`` connection defined in
the device dictionary. As we're going to be using this new connection
for testing, we now run ``auto_login`` here.

.. literalinclude:: examples/test-jobs/bbb-2serial.yaml
     :language: yaml
     :linenos:
     :lines: 55-69
     :emphasize-lines: 2-3

.. _multiple_serial_ports_example1_test_connection:

Tell the test shell to use the new connection
---------------------------------------------

Finally, we start our tests.

* The **namespace** of the ``test`` action **matches** the ``bbb``
  namespace used in the ``deploy`` and ``boot`` actions of the
  device. This ensures that the test shell has access to the dynamic
  data created by the correct deployment action to be able to know
  what rootfs is in use, and where to find the test shell files on
  that rootfs.

* The ``test`` action also has ``connection-namespace`` defined to
  ``isolation`` - this tells it to use the connection tracked in the
  ``isolation`` namespace, rather than the default connection in the
  ``bbb`` namespace. **This is the key part of the isolation, running
  tests on the second serial port.**

.. literalinclude:: examples/test-jobs/bbb-2serial.yaml
     :language: yaml
     :linenos:
     :lines: 70-79
     :emphasize-lines: 1,3

Download or view the complete example:
`examples/test-jobs/bbb-2serial.yaml
<examples/test-jobs/bbb-2serial.yaml>`_:

.. index:: connections - multiple serial ports example

.. _multiple_serial_ports_example2:

Example job 2: A more complicated setup including LXC
=====================================================

Here's a more complicated example job, including the use of LXC for
deployment. This was the first real-world use case for the multiple
serial port support, running Linux kernel functional testing on a
HiKey 6220. The HiKey 6220 hardware includes an extra serial port, but
deploying to the board is more involved - we use fastboot in an LXC
container, which means we have *another* namespace to track in the
test job. Let's unpick the test job.

#. :ref:`multiple_serial_ports_example2_define_container`

#. :ref:`multiple_serial_ports_example2_boot_container`

#. :ref:`multiple_serial_ports_example2_boot_device`

#. :ref:`multiple_serial_ports_example2_boot_connection`

#. :ref:`multiple_serial_ports_example2_test_connection`

Download or view the complete example:
`examples/test-jobs/multiple-serial-ports-lxc.yaml
<examples/test-jobs/multiple-serial-ports-lxc.yaml>`_:

.. _multiple_serial_ports_example2_define_container:

Define the container
--------------------

The distribution and suite of the container, as well as the name, are defined
using the ``lava-lxc`` protocol block.

.. literalinclude:: examples/test-jobs/multiple-serial-ports-lxc.yaml
     :language: yaml
     :linenos:
     :lines: 20-25

.. _multiple_serial_ports_example2_boot_container:

Deploy and boot the container
-----------------------------

The deploy and boot step for the LXC set the timeouts and prompts for this
container. Note the name of the ``namespace`` used in these actions.

The connection to the LXC is defined within the ``tlxc`` namespace and the
connection is created in the ``boot`` action. In the case of LXC support, this
is done by running ``lxc-attach`` on the dispatcher instead of a connection
command from the device configuration.

.. literalinclude:: examples/test-jobs/multiple-serial-ports-lxc.yaml
     :language: yaml
     :linenos:
     :lines: 27-44
     :emphasize-lines: 3, 11

.. seealso:: :ref:`boot_connection_namespace` and :ref:`namespaces_with_lxc`

.. _multiple_serial_ports_example2_boot_device:

Use the container to deploy and boot the device
-----------------------------------------------

Next, the dispatcher runs commands inside that LXC container to download and
deploy an OE image to a HiKey 6220 board, then boot it. This example uses the
``hikey-oe`` namespace. The details of how the HiKey 6220 is deployed and
booted are not relevant to how the multiple serial support operates, but do
take note of the ``namespace`` used to ``boot`` the device. The ``boot``
operation is responsible for creating the connection (in this case by running
a connection command specified in the device configuration).

.. literalinclude:: examples/test-jobs/multiple-serial-ports-lxc.yaml
     :language: yaml
     :linenos:
     :lines: 46-87
     :emphasize-lines: 2, 27

.. _multiple_serial_ports_example2_boot_connection:

Create the connection to the second serial port
-----------------------------------------------

As with making the connection to the LXC and making the connection to the
primary :term:`UART` of the HiKey 6220 :term:`DUT`, making the connection to
the second or additional serial ports involves a ``boot`` action. The action
**must** create a new namespace to store the connection to the second serial
port. (Any subsequent connections to other serial ports would similarly require
a unique namespace for each connection.) This namespace will be used later to
isolate a test shell from the primary connection used for the deployment and
boot actions of the device.

.. literalinclude:: examples/test-jobs/multiple-serial-ports-lxc.yaml
     :language: yaml
     :linenos:
     :lines: 89-103
     :emphasize-lines: 4

.. _multiple_serial_ports_example2_test_connection:

Tell the test shell to use the new connection
---------------------------------------------

This is where it all comes together.

* The **namespace** of the test shell **matches** the namespace of the
  **deployment and boot actions of the device**. This ensures that the test
  shell has access to the dynamic data created by the correct deployment action
  to be able to know what rootfs is in use and where to find the test shell
  files on that rootfs.

  In this example, the test shell needs a **namespace** of ``hikey-oe``

  .. seealso:: :ref:`multiple_serial_ports_example2_boot_device`

* The **connection-namespace** of the same test shell **matches** the namespace
  of the **boot action of the second serial port**. This ensures that the test
  shell communicates with the :term:`DUT` over the isolated connection instead
  of the connection which is stored in the main namespace.

  In this example, the test shell needs a **connection-namespace** of
  ``isolation``

  .. seealso:: :ref:`multiple_serial_ports_example2_boot_connection`

.. literalinclude:: examples/test-jobs/multiple-serial-ports-lxc.yaml
     :language: yaml
     :linenos:
     :lines: 105-113
     :emphasize-lines: 1-2

Download or view the complete example:
`examples/test-jobs/multiple-serial-ports-lxc.yaml
<examples/test-jobs/multiple-serial-ports-lxc.yaml>`_:

.. index:: connections - limitations with multiple serial ports

.. _multiple_serial_ports_limitations:

Limitations with multiple serial ports
**************************************

The method described here is reasonably simple to configure and use,
but it is does have limitations. While LAVA will read from multiple
connections (almost) in parallel this way, it will only write to one
of them at once. The others will all be read-only. This may well suit
your needs, but if not then there is another option - using MultiNode
with :ref:`secondary connections <secondary_connection>`. This is more
powerful, but much more complex to describe in a test job.

.. index:: secondary connections - concepts

.. _secondary_connection:

Secondary Connection
********************

Secondary Connections are a way to have two simultaneous connections
to the same physical device, equivalent to two logins. Each connection
needs to be supported by a distinct TestJob, so a MultiNode group
needs to be created so that the output of each connection can be
viewed as the output of a single TestJob, just as if you had two
terminals. The second connection does not have to use the same
connection method as the current connection and many devices can only
support secondary connections over a network interface, for example
SSH or telnet.

A Secondary Connection has a deploy step and the device is already
providing output over the primary connection (typically serial) before
the secondary connection is established. This is closer to having the
machine on your desk. The TestJob supplies the kernel and rootfs or
image to boot the device and can optionally use the secondary
connection to push other files to the device (for example, an ``ssh``
secondary connection would use ``scp``).

A Secondary Connection can have control over the daemon via the
deployment using the primary connection. The client connection is
still made by the dispatcher.

Secondary Connections require authorization to be configured, so the
deployment must specify the authorization method. This allows the
overlay for this deployment to contain a token (e.g. the ssh public
key) which will allow the connection to be made. The token will be
added to the overlay tarball alongside the directories containing the
test definitions.

.. code-block:: yaml

    - deploy:
        to: tmpfs
        authorize: ssh
        kernel:
          url: http://....
        nfsrootfs:
          url: http://...
        dtb:
          url: http://....

Certain deployment Actions (like SSH) will also copy the token to a particular
location (e.g. ``/root/.ssh/authorized_keys``) but test writers can also add a
run step which enables authorization for a different user, if the test requires
this.

.. note:: The ``/root/.ssh/authorized_keys`` file will be replaced when the
   LAVA overlay is unpacked, if it exists in the test image already. This is a
   security precaution (so that test images can be shared easily without
   allowing unexpected access). Hacking sessions append to this file after the
   overlay has been unpacked.

Deployment can also include delivering the LAVA overlay files, including the
LAVA test shell support scripts and the test definitions specified by the
submitter, to the **host** device to be executed over the secondary connection.
So for SSH, the secondary connection typically has a test action defined and
uses :file:`scp` to put the overlay into place before connecting using
:file:`ssh` and executing the tests. The creation of the overlay is part of the
deployment, the delivery of the overlay is part of the boot process of the
secondary connection, i.e. deploy is passive, boot is active. To support this,
use the MultiNode protocol on the host to declare the IP address of the host
and communicate that to the guest as part of the guest deployment. Then the
guest uses the data to copy the files and make the connection as part of the
boot action. See :ref:`writing_secondary_connection_jobs`.

.. note:: A failure to connect to a :ref:`primary_remote_connection`
  would be an :ref:`infrastructure_error_exception`. A failure to
  connect to a :ref:`secondary_connection` is a
  :ref:`test_error_exception`.

.. _host_role:

Considerations with a secondary connection
==========================================

#. The number of host devices
#. Which secondary connections connect to which host device

In LAVA, this is handled using the MultiNode :term:`role` using the following
rules:

#. All connections declare a ``host_role`` which is the ``role`` label for the
   host device for that connection. e.g. if the connection has a declared role
   of ``client`` and declares a ``host_role`` of ``host``, then every
   ``client`` connection will be expected to be able to connect to the ``host``
   device.

#. The TestJob for each connection with the same ``role`` will be started on a
   single dispatcher which is local to the device with the ``role`` matching
   the specified ``host_role``.

#. There is no guarantee that a connection will be possible to any other device
   in the MultiNode group other than devices assigned to a ``role`` which
   matches the ``host_role`` requirement of the connection.

.. note:: The ``count`` of any ``role`` acting as the ``host_role`` **must** be
   set to 1. Multiple roles can be defined, each set as a ``host_role`` by at
   least one of the other roles, if more than one device in the MultiNode group
   needs to host secondary connections in the one submission. Multiple
   connections can be made to devices of any one ``host_role``.

This allows for devices to be hosted in private networks where only a local
dispatcher can access the device, without requiring that all devices are
accessible (as root) from all dispatchers as that would require all devices to
be publicly accessible.

Secondary connections are affected by :ref:`security` issues due to
the requirements of automation.

The device providing a Secondary Connection is running a TestJob and the
deployment will be erased when the job completes.

.. note:: Avoid confusing ``host_role`` with :ref:`expect_role <lava_start>`.
   ``host_role`` is used by the scheduler to ensure that the job assignment
   operates correctly and does not affect the dispatcher or delayed start
   support. The two values may often have the same value with secondary
   connections but do not mean the same thing.

.. note:: Avoid using constrained resources (like ``dpkg`` or ``apt``) from
   multiple tests (unless you take care with synchronization calls to ensure
   that each operation happens independently). Check through the test
   definitions for installation steps or direct calls to ``apt`` and change the
   test definitions.

Connections and hacking sessions
================================

A hacking session using a :ref:`secondary_connection` is the only situation
where the client is configurable by the user **and** the daemon can be
controlled by the test image. It is possible to adjust the hacking session test
definitions to use different commands and options - as long as both daemon and
client use compatible options. As such, a hacking session user retains security
over their private keys at the cost of the loss of automation.

Hacking sessions can be used with secondary connections, depending on
the use case.

.. _using_secondary_connections:

Using secondary connections with VM groups
******************************************

One example of the use of a secondary connection is to launch a VM on a device
already running a test image. This allows the test writer to control both the
kernel on the bare metal and the kernel in the VM as well as having a
connection on the host machine and the guest virtual machine.

The implementation of VMGroups created a role for a delayed start MultiNode
job. This would allow one job to operate over serial, publish the IP address,
start an SSH server and signal the second job that a connection is ready to be
established. This may be useful for situations where a debugging shell needs to
be opened around a virtualization boundary.

There is an option for downloading or preparing the guest VM image on the host
device within a test shell, prior to the VM delayed start. Alternatively, a
deploy stage can be used which would copy a downloaded image from the
dispatcher to the host device.

Each connection is a different job in a MultiNode group so that the output of
each connection is tracked separately and can be monitored separately.

Sequence
========

#. The host device is deployed with a test image and booted.

#. LAVA then manages the download of the files necessary to create
   the secondary connection.

   * e.g. for QEMU, this would be a bootable image file

#. LAVA also creates a suitable overlay containing the test definitions to be
   run inside the virtual machine.

#. The test image **must** start whatever servers are required to provide the
   secondary connections, e.g. ssh. It does not matter whether this is done
   using install steps in the test definition or pre-existing packages in the
   test image or manual setup. The server **must** be configured to allow the
   (insecure) LAVA automation SSH private key to log in as authorized - this
   key is available in the
   ``/usr/lib/python3/dist-packages/lava_dispatcher/device/dynamic_vm_keys``
   directory when lava-dispatcher is installed or in the lava-dispatcher `git
   tree
   <https://git.lavasoftware.org/lava/lava/tree/master/lava_dispatcher/dynamic_vm_keys>`_.

#. The test image on the host device starts a test definition over the existing
   (typically serial) connection. At this point, the image file and overlay for
   the guest VM are available **on the host** for the host device test
   definition to inspect, although only the image file should actually be
   modified.

#. The test definition includes a signal to the LAVA :ref:`multinode_api` which
   allows the VM to start. The signal includes an identifier for which VM to
   start, if there is more than one.

#. The second job in the MultiNode group waits until the signal is received
   from the coordinator. Upon receipt of the signal, the ``lava dispatch``
   process running the second job will initiate the secondary connection to the
   host device, e.g. over SSH, using the specified private key. The connection
   is used to run a set of commands in the test image running on the host
   device. It is a TestError if any of these commands fail. The last of these
   commands **must** hold the connection open for as long as the test writer
   needs to execute the task inside the VM. Once those tasks are complete, the
   test definition running in the test image on the host device signals that
   the VM has completed.

The test writer is given full control over the commands issued inside the test
image on the host device, including those commands which are responsible for
launching the VM. The test writer is also responsible for making the
**overlay** available inside the VM. This could be by passing arguments to the
commands to mount the overlay alongside the VM or by unpacking the overlay
inside the VM image before calling QEMU. If set in the job definition, the test
writer can ask LAVA to unpack the overlay inside the image file for the VM and
this will be done on the host device before the host device boots the test
image - however, this will require an extra boot of the host device, e.g. using
the dynamic master support.

Basic use cases
===============

Prebuilt files can be downloaded, kernel, ramdisk, dtb, rootfs or complete
image. These will be downloaded to the host device and the paths to these files
substituted into the commands issued to start the VM, in the same way as with
bootloader like u-boot. This provides support for tests within the VM using
standard, packaged tools. To simplify these tests further, it is recommended to
use NFS for the root filesystem of the host device boot - it leads to a quicker
deployment as the files for the VM can be downloaded directly to the NFS share
by the dispatcher. Deployments of the host device system to secondary media,
e.g. SATA, require additional steps and the job will take longer to get to a
point where the VM can be started.

The final launch of the VM will occur using a shell script (which will then be
preserved in the results alongside the overlay), containing the parsed
commands.

Advanced use cases
==================

It is possible to use a test shell to build files to be used when launching the
VM. This allows for a test shell to operate on the host device, building,
downloading or compiling whatever files are necessary for the operation of the
VM, directly controlled by the test shell.

To avoid confusion and duplication, LAVA does not support downloading some
files via the dispatcher and some via the test shell. If there are files needed
for the test job which are not to be built or generated within the test shell,
the test shell will need to use ``wget`` or ``curl`` or some other tool present
in the test image to obtain the files. This also means that LAVA is not able to
verify that such URLs are correct during the validation of the job, so test
writers need to be aware that LAVA will not be able to fail a job early if the
URL is incorrect as would happen in the basic use case.

Any overlay containing the test definitions and LAVA test scripts which are to
be executed inside the VM after the VM has booted still needs to be downloaded
from the dispatcher. The URL of this overlay (a single tarball containing all
files in a self-contained directory) will be injected into the test shell files
on the host device, in a similar way to how the :ref:`multinode_api` provides
dynamic data from other devices in the group.

The test writer is responsible for extracting this tarball so that it is
present or is bind mounted into the root directory of the VM so that the
scripts can be launched immediately after login.

The test shell needs to create the final shell script, just as the basic use
case does. This allows the dispatcher running the VM to connect to the host
device and use a common interface to launch the VM in each use case.

LAVA initiates and controls the connection to the VM, using this script, so
that all output is tracked in the MultiNode job assigned to the VM.

Sample job definition for the VM job
------------------------------------

.. code-block:: yaml

 # second half of a new-style VM group job
 # each connection is a different job
 # even if only one physical device is actually powered up.
 device_type: kvm-arm
 job_name: wandboard-qemu
 timeouts:
   job:
     minutes: 15
   action:
     minutes: 5
 priority: medium
 target_group: asd243fdgdfhgf-45645hgf
 group_size: 2
 parameters:
   # the test definition on the host device manages how
   # the overlay is applied to the VM image.
   overlay: manual  # use automatic for LAVA to do the overlay
 # An ID appended to the signal to start this VM to distinguish
 # it from any other VMs which may start later or when this one
 # completes.
 vm_id: gdb_session

 actions:

  - boot:
     # as kvm-arm, this happens in a test image via
     # the other half of this MultiNode job
     timeout:
       minutes: 3
     # alternative to u-boot
     connection: ssh
     method: vm
     # any way to launch a vm
     commands:
       # full access to the commands to run on the other device
       - qemu-system-arm -hda {IMAGE}
     type: qemu
     prompts:
       - 'linaro-test'
       - 'root@debian:~#'

  - test:
     name: kvm-basic-singlenode
     timeout:
       minutes: 5
     definitions:
         - repository: git://git.linaro.org/lava-team/lava-functional-tests.git
           from: git
           path: lava-test-shell/smoke-tests-basic.yaml
           name: smoke-tests

.. index:: primary remote connection

.. _primary_remote_connection:

Primary remote connection
=========================

When a test device does not have support at all for a primary serial
connection, there is another, more limited way of using it in LAVA -
the Primary Remote Connection. For this to work, the test device must
boot automatically and start a remote login daemon (e.g. sshd) with
configured authentication. The TestJob for a primary remote connection
then skips the deploy stage and uses a simple boot method which just
establishes the connection. A device providing a primary remote
connection in LAVA only provides access to that connection via a
single submitted TestJob at a time. A MultiNode job can make multiple
connections, but other jobs will see the device as busy and not be
able to start their connections.

.. warning:: Primary remote connections can raise issues of
   :ref:`persistence` - the test writer is solely responsible for
   deleting any sensitive data copied, prepared or downloaded using a
   primary remote connection. Do not leave sensitive data for the next
   TestJob to find. Wherever possible, use primary remote connections
   with ``schroot`` support so that each job is kept within a
   :ref:`temporary chroot <disposable_chroot>`, thereby also allowing
   more than one primary (schroot) remote connection on a single
   machine.

It is not necessarily required that a device offering a primary remote
connection is permanently powered on. The only connections being made
to the device are done via the scheduler, which ensures that only one
TestJob can use any one device at a time. Depending on how long it
takes to boot the device, it is feasible to have a device offering
primary remote connections which is powered down between jobs.

A Primary Remote Connection is established by the dispatcher, and is
therefore constrained in the options which are available to the client
requesting the connection, The TestJob has **no** control over the
arguments passed to the connection.

Primary remote connections are affected by :ref:`security` issues due
to the requirements of automation.

.. _primary_remote_connection_devices:

Devices supporting Primary Remote Connections
*********************************************

A device offering a primary remote connection needs a particular
configuration in the device dictionary table:

#. Only primary remote connection deployment methods defined in the
   ``deploy_methods`` parameter, e,g, ``ssh``.

#. Support in the device_type template to replace the list of deployment
   methods with the list supplied in the ``deploy_methods`` parameter.

#. No ``serial`` connection support in the ``boot`` connections list.

#. No ``methods`` in the boot parameters.

#. No :ref:`power_commands` can be used in the :term:`device dictionary`.

This prevents other jobs being submitted which would cause the device
to be rebooted or have a different deployment prepared. This can be
further enhanced with :term:`device tag` support.

Hacking sessions can also be supported with primary remote
connections, depending on the use case.

.. warning:: Remember that in addition to issues related to the
  :ref:`persistence` of a primary remote connection device, hacking
  sessions on primary remote connections also have all of the issues
  of a shared access device - do not copy, prepare or download
  sensitive data when using a shared access device.

.. _ssh_as_the_primary_remote_connection:

SSH as the primary remote connection
====================================

Certain devices can support SSH as the primary remote connection - the
filesystems on such devices are not erased at the end of a TestJob and
provide :ref:`persistence` for certain tasks. These devices declare
this support in the device configuration:

.. code-block:: yaml

  deploy:
    # primary remote connection device has only connections as deployment methods
    methods:
      ssh
  boot:
    connections:  # not serial
      - ssh

TestJobs then use SSH as a boot method which simply acts as a login to
establish a connection:

.. code-block:: yaml

    - deploy:
        to: ssh
        os: debian

    - boot:
        method: ssh
        connection: ssh
        failure_retry: 2
        prompts:
          - 'linaro-test'
          - 'root@debian:~#'

The ``deploy`` action in this case simply prepares the LAVA overlay containing
the test shell definitions and copies those to a pre-determined location on the
device. This location will be removed at the end of the TestJob. The ``os``
parameter is specified so that any LAVA overlay scripts are able to pick up the
correct shell, package manager and other deployment data items in order to run
the lava test shell definitions.

.. _security:

Security
========

A primary SSH connection from the dispatcher needs to be controlled through the
device configuration, allowing the use of a private SSH key which is at least
hidden from test writers. (:ref:`essential_components`).

The key is declared as a path on the dispatcher, so is device-specific. Devices
on the same dispatcher can share the same key or may have a unique key - all
keys still need to not have any passphrase - as long as all devices supported
by the SSH host have the relevant keys configured as authorized for login as
root. [#admin1]_

.. [#admin1] Securing such private keys when the admin process is managed in a
   public VCS is left as an exercise for the admin teams.

LAVA provides a default (completely insecure) private key which can be used for
these connections. This key is installed within lava-dispatcher and is readable
by anyone inspecting the lava-dispatcher codebase in git. (This has not been
changed in the refactoring.)

It is conceivable that a test image could be suitably configured before being
submitted to LAVA, with a private key included inside a second job which
deploys normally and executes the connection **instead** of running a test
definition. However, anyone with access to the test image would still be able
to obtain the private key. Keys generated on a per job basis would still be
open for the lifetime of the test job itself, up to the job timeout specified.
While this could provide test writers with the ability to control the options
and commands used to create the connection, any additional security is minimal
and support for this has not been implemented, yet.

See also the :ref:`host_role` for information on how access to devices is
managed.

.. index:: persistence

.. _persistence:

Persistence
===========

Devices supporting primary SSH connections have persistent deployments and this
has implications, some positive, some negative - depending on your use case.

#. **Fixed OS** - the operating system (OS) you get is the OS of the device and
   this **must not** be changed or upgraded.

#. **Package interference** - if another user installs a conflicting package,
   your test can **fail**.

#. **Process interference** - another process could restart (or crash) a daemon
   upon which your test relies, so your test will **fail**.

#. **Contention** - another job could obtain a lock on a constrained resource,
   e.g. ``dpkg`` or ``apt``, causing your test to **fail**.

#. **Reusable scripts** - scripts and utilities your test leaves behind can be
   reused (or can interfere) with subsequent tests.

#. **Lack of reproducibility** - an artifact from a previous test can make it
   impossible to rely on the results of a subsequent test, leading to wasted
   effort with false positives and false negatives.

#. **Maintenance** - using persistent filesystems in a test action results in
   the overlay files being left in that filesystem. Depending on the size of
   the test definition repositories, this could result in an inevitable
   increase in used storage becoming a problem on the machine hosting the
   persistent location. Changes made by the test action can also require
   intermittent maintenance of the persistent location.

Only use persistent deployments when essential and **always** take great care
to avoid interfering with other tests. Users who deliberately or frequently
interfere with other tests can have their submit privilege revoked.

See :ref:`disposable_chroot` for a solution to some of these issues but the
choice of operating system (and the versions of that OS available) within the
chroot is down to the lab admins, not the test writer. The principal way to get
full control over the deployment is to use a :ref:`secondary_connection`.

.. _disposable_chroot:

Disposable chroot deployments
*****************************

Some devices can support mechanisms like `LVM snapshots`_ which allow for a
self-contained environment to be unpacked for a single session and then
discarded at the end of the session. These deployments do not suffer the same
entanglement issues as simple SSH deployments and can provide multiple
environments, not just the OS installed on the SSH host system.

This support is similar to how distributions can offer "porter boxes" which
allow upstream teams and community developers to debug platform issues in a
native environment. It also allows tests to be run on a different operating
system or different release of an operating system. Unlike distribution "porter
boxes", however, LAVA does not allow more than one TestJob to have access to
any one device at the same time.

A device supporting disposable chroots will typically follow the
configuration of :ref:`primary_remote_connection_devices`. The device
will show as busy whenever a job is active, but although it **is**
possible to use a secondary connection as well, the deployment methods
of the device would have to disallow access to the media upon which
the chroots are installed or deployed or upon which the software to
manage the chroots is installed. e.g. a device offering disposable
chroots on SATA could offer ramdisk or NFS tests.

LAVA support for disposable chroots is implemented via ``schroot`` (forming the
replacement for the dummy-schroot device in the old dispatcher).

Typical device configuration:

.. code-block:: yaml

  deploy:
    # list of deployment methods which this device supports
    methods:
      ssh:
      schroot:
        - unstable
        - trusty
        - jessie
  boot:
    connections:
      - ssh

Optional device configuration allowing secondary connections:

.. code-block:: yaml

  deploy:
    # list of deployment methods which this device supports
    methods:
      tftp:
      ssh:
      schroot:
        - unstable
        - trusty
        - jessie
  boot:
    connections:
      - serial
      - ssh

The test job YAML would simply specify:

.. code-block:: yaml

    - deploy:
        to: ssh
        chroot: unstable
        os: debian

    - boot:
        method: ssh
        connection: ssh
        failure_retry: 2
        prompts:
          - 'linaro-test'
          - 'root@debian:~#'

.. note:: The OS still needs to be specified, LAVA :ref:`does not guess
   <keep_dispatcher_dumb>` based on the chroot name. There is nothing to stop
   an schroot being `named` ``testing`` but actually being upgraded or replaced
   with something else.

The deployment of an schroot involves unpacking the schroot into a logical
volume with LVM. It is an :ref:`infrastructure_error_exception` if this step
fails, for example if the volume group has insufficient available space.

``schroot`` also supports directories and tarballs but LVM is recommended as it
avoids problems of :ref:`persistence`. See the `schroot man page
<http://manpages.debian.org/cgi-bin/man.cgi?query=schroot&apropos=0&sektion=0&manpath=Debian+unstable+sid&format=html&locale=en>`_
for more information on ``schroot``. A common way to create an ``schroot`` is
to use tools packaged with `sbuild`_ or you can `use debootstrap
<https://wiki.debian.org/Schroot>`_.

.. _LVM Snapshots: https://debian-administration.org/article/410/A_simple_introduction_to_working_with_LVM
.. _schroot: https://tracker.debian.org/pkg/schroot
.. _sbuild: https://tracker.debian.org/pkg/sbuild

