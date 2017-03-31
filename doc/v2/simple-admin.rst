.. index:: simple administration, administration

.. _simple_admin:

Simple Administration
#####################

Requirements
************

You need to be familiar with these sections:

#. :ref:`installation`
#. :ref:`creating a pipeline worker <setting_up_pipeline_instance>`.
#. :ref:`adding_pipeline_devices_to_worker`
#. :ref:`create_superuser`
#. :ref:`logging_in` (as superuser)
#. :ref:`device_types` and :ref:`device_type_elements`
#. :ref:`first_devices`
#. :ref:`admin_backups`

.. seealso:: `Django documentation on the Django Admin
   Interface <http://www.djangobook.com/en/2.0/chapter06.html>`_

.. _simple_admin_outline:

Outline
*******

LAVA is complex and administering a LAVA instance can be an open-ended task
covering a wide range of skills.

* **Debian system administration**
* **Device integration**
* **Network configuration**
* **Writing tests**
* **Triage**
* **Python/Django knowledge** - for debugging

Debian system administration
****************************

At a simple level, LAVA requires a variety of Debian system administration
tasks, including:

* installing, upgrading and maintaining the installed packages and apt sources

* configuring services outside LAVA, including:

  * apache - LAVA provides an example apache configuration but many instances
    will need to adapt this for their own hosting requirements.

  * DHCP - Most :term:`devices <DUT>` will need networking support using DHCP.

  * configuration management - LAVA has a variety of configuration files and
    a number of other services and tools will also need to be configured, for
    example serial console services, TFTP services and authentication services.

    .. seealso:: :ref:`admin_backups`

  * email - LAVA can use email for notifications, if test writers include
    appropriate requests in the test job submissions. To send email, LAVA
    relies on the basic Django email support using a standard sendmail
    interface. Only the master needs to be configured to send email,
    notifications from workers are handled via the master.

Infrastructure
**************

LAVA instances will need some level of infrastructure, including:

* :abbr:`UPS (Uninterruptible Power Supply)`

* network switches

* remote power control hardware

* master and worker hardware

Many instances will also require specialised hardware to assist with the
automation of specific :term:`devices <DUT>`, including switchable USB hubs or
specialised relay boards.

.. _simple_admin_small:

Start small
***********

These rules may seem harsh or obvious or tedious. However, multiple people have
skipped one or more of these requirements and have learnt that these steps
provide valuable advice and assistance that can dramatically improve your
experience of LAVA. Everyone setting up LAVA, is **strongly** advised to follow
all of these rules.

#. **Start with a minimal LAVA install** with at most one or two devices - at
   this stage only QEMU devices should be considered. This provides the best
   platform for learning LAVA, before learning how to administer a LAVA
   instance.

#. **Use the worked examples** in the documentation which refer back to
   standard builds and proven test jobs. There will be enough to do in becoming
   familiar with how to fix problems and issues local to your own instance
   without adding the complexity of devices or kernel builds to which only you
   have access.

#. **Avoid rushing to your custom device** - device integration into *any*
   automated system is **hard**. It does not become any easier if you are
   trying to learn how to use the automation as well.

#. **Plan how to test**

   * use the examples and :term:`device types <device type>` which are
     **known** to work.

   * Read through all the worked examples before starting your planning, there
     are likely to be useful ways to do what you want to do and advice on
     **why** it is a bad idea to do some of the things you may have considered
     at the start.

   * plan out how to do the testing of other custom devices by looking for
     similar device support already available in other LAVA instances.

   * **Avoid shortcuts** - it may seem that you only want to *connect & test*
     but there are :ref:`known problems with overly simplistic approaches
     <simplistic_testing_problems>` and you are likely to need to use
     ``deploy`` actions and ``boot`` actions to be able to produce reliable
     results.

#. **Have at least one test instance**. A single instance of LAVA is never
   sufficient for any important testing. Everyone needs at least one test
   instance in a VM or on another machine to have confidence that
   administrative changes will not interfere with test jobs.

#. **Control your changes** - configuration, test job definitions, test shell
   definitions, :term:`device dictionaries <device dictionary>`, template
   changes and any code changes - all need to be in **version control**.

#. **Control access to the dispatcher and devices** - device configuration
   details like the connection command and remote power commands can be viewed
   by **all users** who are able to submit to that device. In many cases, these
   details are sufficient to allow anyone with the necessary access to
   administer those devices, including modifying bootloader configuration. Only
   administrators should have access to **any** machine which itself has access
   to the serial console server and/or remote power control services.
   Typically, this will be controlled using SSH keys.

   .. seealso:: :ref:`power_commands`

#. **Subscribe** to the :ref:`mailing_lists` where you will find others who
   have setup their own LAVA instances. IRC is fine for quick queries but it is
   trivial to lose track of previous comments, examples and links when the
   channel gets busy. Mailing lists have public archives which are fully
   indexed by search engines. The archives will help you solve your current
   issue and help many others find answers for their own issues later.

.. index:: simple testing, simplistic, connect and test, existing builds

.. _simplistic_testing_problems:

Problems with simplistic testing
********************************

There are a number of common fallacies relating to automation. Check your test
ideas against these before starting to make your plans:

.. _connect_and_test:

Connect and test
================

Seems simple enough - it doesn't seem as if you need to deploy a new kernel or
rootfs every time, no need to power off or reboot between tests. *Just* connect
and run stuff.  After all, you already have a way to manually deploy stuff to
the board.

* The biggest problem with this method is :ref:`persistence` - LAVA keeps the
  LAVA components separated from each other but tests frequently need to
  install support which will persist after the test, write files which can
  interfere with other tests or break the manual deployment in unexpected ways
  when things go wrong.

* The second problem within this fallacy is simply the power drain of leaving
  the devices constantly powered on. In manual testing, you would apply power
  at the start of your day and power off at the end. In automated testing,
  these devices would be on all day, every day, because test jobs could be
  submitted at any time.

.. _ssh_vs_serial:

ssh instead of serial
=====================

This is an over-simplification which will lead to new and unusual bugs and is
only a short step on from *connect & test* with many of the same problems. A
core strength of LAVA is demonstrating differences between types of devices by
controlling the boot process. By the time the system has booted to the point
where ``sshd`` is running, many of those differences have been swallowed up in
the boot process.

``ssh`` can be useful within LAVA tests but using ``ssh`` to the exclusion of
serial means that the boot process is hidden from the logs, including any
errors and warnings. If the boot process results in a system which cannot start
``sshd`` or cannot expose ``ssh`` over the network, the admin has no way to
determine the cause of the failure. If the userspace tests fail, the test
writer cannot be sure that the boot process was not a partial cause of the
failure as the boot process messages are not visible. This leads to test
writers repeatedly submitting the same jobs and wasting a lot of time in triage
because critical information is hidden by the choice of using ``ssh`` instead
of serial.

Using ``ssh`` without a boot process at all has all the same problems as
:ref:`connect_and_test`.

Limiting all your tests to userspace without changing the running kernel is not
making the best use of LAVA. LAVA has a steep learning curve, but trying to cut
corners won't help you in the long run. If you see `ssh` as a shortcut, it is
probable that your use case may be better served by a different tool which does
not control the boot process, for example tools based on containers and virtual
machines.

.. note:: Using serial also requires some level of automated power control. The
   connection is made first, then power is applied and there is no allowance
   for manual intervention in applying power. LAVA is designed as a fully
   automated system where test jobs can run reliably without any manual
   operations.

.. seealso:: :ref:`what_is_lava_not`, :ref:`serial_connections` and
   :ref:`power_control_infrastructure`

.. _test_all_the_things:

test everything at the same time
================================

You've built an entire system and now you put the entire thing onto the device
and do all the tests at the same time. There are numerous problems with this
approach:

#. **Breaking the basic scientific method** of test one thing at a time. The
   single system contains multiple components, like the kernel and the rootfs
   and the bootloader. Each one of those components can fail in ways which can
   only be picked up when some later component produces a completely misleading
   and unexpected error message.

#. **Timing** - simply deploying the entire system for every single test job
   wastes inordinate amounts of time when you do finally identify that the
   problem is a configuration setting in the bootloader or a missing module for
   the kernel.

#. **Reproducibility** - the larger the deployment, the more complex the boot
   and the tests become. Many LAVA devices are prototypes and development
   boards, not production servers. These devices **will** fail in unpredictable
   places from time to time. Testing a kernel build multiple times is much more
   likely to give you consistent averages for duration, performance and other
   measurements than if the kernel is only tested as part of a complete system.

#. **Automated recovery** - deploying an entire system can go wrong, whether an
   interrupted copy or a broken build, the consequences can mean that the
   device simply does not boot any longer.

   * **Every component** involved in your test **must** allow for automated
     recovery. This means that the boot process must support being interrupted
     **before** that component starts to load. With a suitably configured
     bootloader, it is straightforward to test kernel builds with fully
     automated recovery on most devices. Deploying a new build of the
     bootloader **itself** is much more problematic. Few devices have the
     necessary management interfaces with support for secondary console access
     or additional network interfaces which respond very early in boot. It is
     possible to chainload some bootloaders, allowing the known working
     bootloader to be preserved.

.. _existing_builds:

I already have builds
=====================

This may be true, however, automation puts extra demands on what those builds
are capable of supporting. When testing manually, there are any number of times
when a human will decide that something needs to be entered, tweaked, modified,
removed or ignored which the automated system needs to be able to understand.
Examples include:

* ``/etc/resolv.conf`` - it is common for many build tools to generate or copy
  a working ``/etc/resolv.conf`` based on the system within which the build
  tool is executed. This is a frequent cause of test jobs failing due to being
  unable to lookup web addresses using :abbr:`DNS (Domain Name System)`. It is
  also common for an automated system to be in a different network subnet to
  the build tool, again causing the test job to be unable to use DNS due to the
  wrong data in ``/etc/resolv.conf``.

* **Customised tools** - using non-standard build tools or putting custom
  scripts, binaries and programs into a root filesystem is a common reason for
  test jobs to fail when users migrate to updated builds.

* **Comparability** - LAVA has various ways to :ref:`support <getting_support>`
  local admins but to make sense of logs or bug reports, the test job needs to
  be comparable to one already known to work elsewhere.

Make use of the :ref:`standard files <providing_gold_standard_files>` for known
working device types. These files come with details of how to rebuild the
files, logs of the each build and checksums to be sure the download is correct.

.. _automate_everything:

Automation can do everything
============================

It is **not** possible to automate every test method. Some kinds of tests and
some kinds of devices lack critical elements that do not work well with
automation. These are not problems in LAVA, these are design limitations of the
kind of test and the device itself. Your preferred test plan may be infeasible
to automate and some level of compromise will be required.

.. _all_users_are_admins:

Users are all admins too
========================

This will come back to bite! However, there are other ways in which this can
occur even after administrators have restricted users to limited access. Test
jobs (including hacking sessions) have full access to the device as root.
Users, therefore, can modify the device during a test job and it depends on the
device hardware support and device configuration as to what may happen next.
Some devices store bootloader configuration in files which are accessible from
userspace after boot. Some devices lack a management interface that can
intervene when a device fails to boot. Put these two together and admins can
face a situation where a test job has corrupted, overridden or modified the
bootloader configuration such that the device no longer boots without
intervention. Some operating systems require a debug setting to be enabled
before the device will be visible to the automation (e.g. the Android Debug
Bridge). It is trivial for a user to mistakenly deploy a default or production
system which does not have this modification.

Administrators need to be mindful of the situations from which users can
(mistakenly or otherwise) modify the device configuration such that the device
is unable to boot without intervention when the next job starts. This is one of
the key reasons for :term:`health checks <health check>` to run sufficiently
often that the impact on other users is minimised.

.. index:: administrator

.. _lava_admin_roles:

Roles of LAVA administrators
****************************

The ongoing roles of administrators include:

* monitor the number of devices which are online

* identify the reasons for health check failures

* communicate with users when a test job has made the device unbootable (i.e.
  *bricked*)

* recover devices which have gone offline

* restrict command line access to the dispatcher(s) and device(s) to only other
  administrators. This includes access to the serial console server and the
  remote power control service. Ideally, users must not have any access to the
  same subnet as the dispatchers and devices, **except** for the purposes of
  accessing devices during :ref:`hacking_session`. This may involve port
  forwarding or firewall configuration and is **not** part of the LAVA software
  support.

* to keep the instance at a sufficiently high level of reliability that
  :ref:`continuous_integration` produces results which are themselves reliable
  and useful to the developers. To deliver this reliability, administrators do
  need to sometimes prevent users from making mistakes which are likely to take
  devices offline.

* prepare and routinely test backups and disaster recovery support. Many lab
  admin teams use ``salt`` or ``ansible`` or other configuration management
  software. Always ensure you have a fast way of deploying a replacement worker
  or master in case of hardware failure.

  .. seealso:: :ref:`admin_backups` for details of what to backup and test.

.. index:: best admin practices, best practices

.. _best_admin_practices:

Best practice
*************

.. seealso:: :ref:`admin_backups`

* Before you upgrade the server or dispatcher, run the standard test jobs and a
  few carefully chosen stable jobs of your own as a set of *functional tests* -
  just as the LAVA team do upstream.

* Keep all the servers and dispatchers *regularly updated* with regard to
  security updates and bug fixes. The more often you run the upgrades, the
  fewer packages will be involved in each upgrade and so the easier it will be
  to spot that one particular upgrade may be misbehaving.

* Repeat your functional tests after all upgrades.

* Use :term:`health checks <health check>` and tweak the frequency so that busy
  devices run health checks often enough to catch problems early.

* Add standard investigative tools. You may choose to use `nagios`_ and / or
  `munin`_ or other similar tools.

* Use configuration management. Various LAVA instances use `salt`_ or `puppet`_
  or `ansible`_. Test out various tools and make your own choice.

.. _`nagios`: https://www.nagios.org/about/
.. _`munin`: http://munin-monitoring.org/
.. _`salt`: https://saltstack.com/community/
.. _`puppet`: https://github.com/puppetlabs/puppet
.. _`ansible`: https://www.ansible.com/

.. index:: admin triage, triage, admin debug, administration roles

.. _admin_triage:

Triage
******

When you come across problems with your LAVA instance, there are some basic
information sources, methods and tools which will help you identify the
problem(s).

Problems affecting test jobs
============================

Administrators may be asked to help with debugging test jobs or may need to
use test jobs to investigate some administration problems, especially health
checks.

* Start with the :ref:`triage guidelines <debugging_test_failures>` if the
  problem shows up in test jobs.
* Check the :ref:`failure_comments` for information on exactly what happened.
* Specific :ref:`lava_failure_messages` may relate directly to an admin issue.
* Try to reproduce the failure with smaller and less complex test jobs, where
  possible.

Some failure comments in test jobs are directly related to administrative
problems.

.. _admin_test_power_fail:

Power up failures
-----------------

* If the device dictionary contains errors, it is possible that the test job
  is trying to turn on power to or read serial input from the wrong ports. This
  will show up as a timeout when trying to connect to the device.

  .. note:: Either the PDU command or the connection command could be wrong. If
     the device previously operated normally, check the details of the power on
     and connection commands in previous jobs. Also, try running the ``power
     on`` command followed by the ``connection command`` manually (as root) on
     the relevant worker.

  * If the ports are correct, check that the specified PDU port is actually
    delivering power when the state of the port is reported as ``ON`` and
    switching off power when reporting ``OFF``. It is possible for individual
    relays in a PDU to fail, reporting a certain state but failing to switch
    the relay when the state is reported as changing. Once a PDU starts to fail
    in this way, the PDU should be replaced as other ports may soon fail in the
    same manner. (Checking the light or LED on the PDU port may be
    insufficient. Try connecting a fail safe device to the port, like a desk
    light etc. This may indicate whether the board itself has a hardware
    problem.)

  * If the command itself is wrong or returns non-zero, the test job will
    report an Infrastructure Error

* If the connection is refused, it is possible that the device node does not
  (yet) exist on the worker. e.g. check the ``ser2net`` configuration and the
  specified device node for the port being used.

* Check whether the device needs specialised support to avoid issues with
  power reset buttons or other hardware modes where the device does not start
  to boot as soon as power is applied. Check that any such support is actually
  working.

.. index:: compatibility

.. _compatibility_failures:

Compatibility failures
----------------------

.. code-block:: none

 Dispatcher unable to meet job compatibility requirement.

The master uses the ``lava-dispatcher`` code on the server to calculate a
compatibility number - the highest integer in the strategy classes used for
that job. The worker also calculates the number and unless these match, the job
is failed.

The compatilibilty check allows the master to detect if the worker is running
older software, allowing the job to fail early. Compatibility is changed when
existing support is removed, rather than when new code is added. Admins remain
responsible for ensuring that if a new device needs new functionality, the
worker will need to be running updated code.

.. seealso:: :ref:`missing_method_failures` and
   :ref:`python_traceback_failures`. Also the :ref:`developer documentation
   <compatibility_developer>` for more information on how developers set the
   compatibility for test jobs.

.. index:: multinode admin debug

.. _multinode_admin_debug:

Checking for MultiNode issues
-----------------------------

* Check the contents of ``/etc/lava-coordinator/lava-coordinator.conf`` on the
  worker. If you have multiple workers, all workers must have coordinator
  configuration pointing at a single lava-coordinator which serves all workers
  on that instance (you can also have one coordinator for multiple instances).

* Check the output of the ``lava-coordinator`` logs in
  ``/var/log/lava-coordinator.log``.

* Run the status check script provided by ``lava-coordinator``:

  .. code-block:: shell

   $ /usr/share/lava-coordinator/status.py
   status check complete. No errors

* Use the :ref:`example test jobs <running_multinode_tests>` to distinguish
  between adminstration errors and test job errors. Simplify and make your test
  conditions portable. MultiNode is necessarily complex and can be hard to
  debug.

  * Use QEMU to allow the test job to be submitted to other instances.
  * Use anonymous git repositories for test definitions that just show the
    problem, without needing to access internal resources
  * Use :ref:`inline test definitions <inline_test_definitions>` so that the
    steps can be seen directly in the test job submission. This makes it easier
    to tweak and test as well as making it easier for others to help in the
    work.

.. _admin_debug_information:

Where to find debug information
===============================

index:: jinja2 template administration

.. _jinja_template_triage:

Jinja2 Templates
----------------

LAVA uses `Jinja2`_ to allow devices to be configured using common data blocks,
inheritance and the device-specific :term:`device dictionary`. Templates are
developed as part of ``lava-server`` with supporting unit tests::

 lava-server/lava_scheduler_app/tests/device-types/

Building a new package using the :ref:`developer scripts
<developer_build_version>` will cause the updated templates to be installed
into::

 /etc/lava-server/dispatcher-config/device-types/

The jinja2 templates support conditional logic, iteration and default arguments
and are considered as part of the codebase of ``lava-server``. Changing the
templates can adversely affect other test jobs on the instance. All changes
should be made first as a :ref:`developer <developer_jinja2_support>`. New
templates should be accompanied by new unit tests for that template.

.. note:: Although these are configuration files and package updates will
   respect any changes you make, please :ref:`talk to us <getting_support>`
   about changes to existing templates maintained within the ``lava-server``
   package.

.. _Jinja2: http://jinja.pocoo.org/docs/dev/

.. seealso:: :ref:`overriding_device_configuration`,
   :ref:`migrating_known_device_example`, :ref:`developer_guide`
   and :ref:`template_mismatch`.

.. index:: admin log files

Log files
---------

* **lava-master** - controls all V2 test jobs after devices have been assigned.
  Logs are created on the master::

    /var/log/lava-server/lava-master.log

* **lava-scheduler** - controls how all devices are assigned. Control will be
  handed over to ``lava-master`` once V1 code is removed. Logs are created on
  the master::

    /var/log/lava-server/lava-scheduler.log

* **lava-slave** - controls the operation of the test job on the slave.
  Includes details of the test results recorded and job exit codes. Logs are
  created on the slave::

    /var/log/lava-dispatcher/lava-slave.log

* **apache** - includes XML-RPC logs::

   /var/log/apache2/lava-server.log

* **gunicorn** - details of the :abbr:`WSGI (Web Server Gateway Interface)`
  operation for django::

   /var/log/lava-server/gunicorn.log

TestJob data
------------

* **slave logs** are transmitted to the master - temporary files used by the
  testjob are deleted when the test job ends.

* **job validation** - the master retains the output from the validation of the
  testjob performed by the slave. The logs is stored on the master as the
  ``lavaserver`` user - so for job ID 4321::

   $ sudo su lavaserver
   $ ls /var/lib/lava-server/default/media/job-output/job-4321/description.yaml

* **other testjob data** - also stored in the same location on the  master
  are the complete log file (``output.yaml``) and the logs for each specific
  action within the job in a directory tree below the ``pipeline`` directory.

.. index:: override device

.. _overriding_device_configuration:

Overriding device configuration
*******************************

Some device configuration can be overridden without making changes to the
:ref:`jinja_template_triage`. This does require some understanding of how
template engines like jinja2 operate.

* Values hard-coded into the jinja2 template cannot be overridden. The
  template would need to be modified and re-tested.

* Variables in the jinja2 template typically have a default value.

* Variables in the jinja2 template can be override the default in the
  following sequence:

  #. by the next template
  #. by the device dictionary or, if neither of those set the variable
  #. by the :term:`job context`.

To identify which variables can be overridden, check the template for
placeholders. A commonly set value for QEMU device types is the amount of
memory (on the dispatcher) which QEMU will be allowed to use for each test job:

.. code-block:: jinja

    - -m {{ memory|default(512) }}

Most administrators will need to set the ``memory`` constraint in the
:term:`device dictionary` so that test jobs cannot allocate all the available
memory and cause the dispatcher to struggle to provide services to other test
jobs. An example device dictionary to override the default (and also prevent
test jobs from setting a different value) would be:

.. code-block:: jinja

 {% extends 'qemu.jinja2' %}
 {% set memory = 1024 %}

Admins need to balance the memory constraint against the number of other
devices on the same dispatcher. There are occassions when multiple test jobs
can start at the same time, so admins may also want to limit the number of
emulated devices on any one dispatcher to the number of cores on that
dispatcher and set the amount of memory so that with all devices in use there
remains some memory available for the system itself.

Most administrators will **not** set the ``arch`` variable of a QEMU device so
that test writers can use the one device to run test jobs using a variety of
architectures by setting the architecture in the :term:`job context`. The QEMU
template has conditional logic for this support:

.. code-block:: jinja

 {% if arch == 'arm64' or arch == 'aarch64' %}
            qemu-system-aarch64
 {% elif arch == 'arm' %}
            qemu-system-arm
 {% elif arch == 'amd64' %}
            qemu-system-x86_64
 {% elif arch == 'i386' %}
            qemu-system-x86
 {% endif %}

.. note:: Limiting QEMU to specific architectures on dispatchers which are not
   able to safely emulate an x86_64 machine due to limited memory or number of
   cores is an advanced admin task. :term:`Device tags <device tag>` will be
   needed to ensure that test jobs are properly scheduled.

.. index:: override constant

.. _overriding_constants:

Overriding device constants
===========================

The dispatcher uses a variety of constants and some of these can be overridden
in the test job definition.

.. FIXME: add links to the dispatcher actions which support overrides

A common override used when operating devices on your desk or when a
:term:`PDU` is not available, allows the dispatcher to recognise a soft reboot.
This uses the ``shutdown-message`` parameter support in the ``u-boot`` boot
action:

.. code-block:: yaml

 - boot:
    method: u-boot
    commands: ramdisk
    parameters:
      shutdown-message: "reboot: Restarting system"
    prompts:
    - 'linaro-test'
    timeout:
      minutes: 2

.. index:: add device admin

.. _admin_adding_devices:

Adding more devices
*******************

.. note:: If you are considering using MultiNode in your Test Plan, now is the
   time to ensure that MultiNode jobs can run successfully on your instance.

Once you have a couple of QEMU devices running and you are happy with how to
maintain, debug and test using those devices, start adding **known working**
devices. These are devices which already have templates in::

 /etc/lava-server/dispatcher-config/device-types/

The majority of the known device types are low-cost ARM developer boards which
are readily available. Even if you are not going to use these boards for your
main testing, you are **recommended** to obtain a couple of these devices as
these will make it substantially easier to learn how to administer LAVA for any
devices other than emulators.

Physical hardware like these dev-boards have hardware requirements like:

* serial console servers
* remote power control
* network infrastructure
* uninterruptible power supplies
* shelving
* cables
* removable media

Understanding how all of those bits fit together to make a functioning LAVA
instance is much easier when you use devices which are known to work in LAVA.

Early admin stuff:

* recommendations on how to do admin:

  * start simple using our examples
  * build complexity slowly
  * only once you're confident, start adding novel devices

* where to find logs and debug information
* device configuration and templates
* getting a number of cheap ARMv7 development boards
