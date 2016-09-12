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

.. seealso:: `Django documentation on the Django Admin
   Interface <http://www.djangobook.com/en/2.0/chapter06.html>`_

.. _simple_admiin_outline:

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

#. **connect & test** seems simple enough - it doesn't seem as if you need to
   deploy a new kernel or rootfs every time, no need to power off or reboot
   between tests. *Just* connect and run stuff.  After all, you already have a
   way to manually deploy stuff to the board.

   * The biggest problem with this method is :ref:`persistence` - LAVA keeps
     the LAVA components separated from each other but tests frequently need to
     install support which will persist after the test, write files which can
     interfere with other tests or break the manual deployment in unexpected
     ways when things go wrong.

   * The second problem within this fallacy is simply the power drain of
     leaving the devices constantly powered on. In manual testing, you would
     apply power at the start of your day and power off at the end. In
     automated testing, these devices would be on all day, every day, because
     test jobs could be submitted at any time.

#. **test everything at the same time** - you've built an entire system and now
   you put the entire thing onto the device and do all the tests at the same
   time. There are numerous problems with this approach:

   #. **Breaking the basic scientific method** of test one thing at a time. The
      single system contains multiple components, like the kernel and the
      rootfs and the bootloader. Each one of those components can fail in ways
      which can only be picked up when some later component produces a
      completely misleading and unexpected error message.

   #. **Timing** - simply deploying the entire system for every single test job
      wastes inordinate amounts of time when you do finally identify that the
      problem is a configuration setting in the bootloader or a missing module
      for the kernel.

   #. **Reproducibility** - the larger the deployment, the more complex the
      boot and the tests become. Many LAVA devices are prototypes and
      development boards, not production servers. These devices **will** fail
      in unpredictable places from time to time. Testing a kernel build
      multiple times is much more likely to give you consistent averages for
      duration, performance and other measurements than if the kernel is only
      tested as part of a complete system.

   #. **Automated recovery** - deploying an entire system can go wrong, whether
      an interrupted copy or a broken build, the consequences can mean that the
      device simply does not boot any longer.

      * **Every component** involved in your test **must** allow for automated
        recovery. This means that the boot process must support being
        interrupted **before** that component starts to load. With a suitably
        configured bootloader, it is straightforward to test kernel builds with
        fully automated recovery on most devices. Deploying a new build of the
        bootloader **itself** is much more problematic. Few devices have the
        necessary management interfaces with support for secondary console
        access or additional network interfaces which respond very early in
        boot. It is possible to chainload some bootloaders, allowing the known
        working bootloader to be preserved.

#. **I already have builds** - this may be true, however, automation puts extra
   demands on what those builds are capable of supporting. When testing
   manually, there are any number of times when a human will decide that
   something needs to be entered, tweaked, modified, removed or ignored which
   the automated system needs to be able to understand. Examples include:

   * ``/etc/resolv.conf`` - it is common for many build tools to generate or
     copy a working ``/etc/resolv.conf`` based on the system within which the
     build tool is executed. This is a frequent cause of test jobs failing due
     to being unable to lookup web addresses using :abbr:`DNS (Domain Name
     System)`. It is also common for an automated system to be in a different
     network subnet to the build tool, again causing the test job to be unable
     to use DNS due to the wrong data in ``/etc/resolv.conf``.

   * **Customised tools** - using non-standard build tools or putting custom
     scripts, binaries and programs into a root filesystem is a common reason
     for test jobs to fail when users migrate to updated builds.

   * **Comparability** - LAVA has various ways to :ref:`support
     <getting_support>` local admins but to make sense of logs or bug reports,
     the test job needs to be comparable to one already known to work
     elsewhere.

   Make use of the :ref:`standard files <providing_gold_standard_files>` for
   known working device types. These files come with details of how to rebuild
   the files, logs of the each build and checksums to be sure the download is
   correct.

#. **Automation can do everything** - it is **not** possible to automate every
   test method. Some kinds of tests and some kinds of devices lack critical
   elements that block automation. These are not problems in LAVA, these are
   design limitations of the kind of test and the device itself. Your preferred
   test plan may be infeasible to automate and some level of compromise will be
   required.

#. **Users are all admins too** - this will come back to bite! However, there
   are other ways in which this can occur even after administrators have
   restricted users to limited access. Test jobs (including hacking sessions)
   have full access to the device as root. Users, therefore, can modify the
   device during a test job and it depends on the device hardware support and
   device configuration as to what may happen next. Some devices store
   bootloader configuration in files which are accessible from userspace after
   boot. Some devices lack a management interface that can intervene when a
   device fails to boot. Put these two together and admins can face a situation
   where a test job has corrupted, overridden or modified the bootloader
   configuration such that the device no longer boots without intervention.
   Some operating systems require a debug setting to be enabled before the
   device will be visible to the automation (e.g. the Android Debug Bridge). It
   is trivial for a user to mistakenly deploy a default or production system
   which does not have this modification.

   Administrators need to be mindful of the situations from which users can
   (mistakenly or otherwise) modify the device configuration such that the
   device is unable to booting without intervention when the next job starts.
   This is one of the key reasons for :term:`health checks <health check>` to
   run sufficiently often that the impact on other users is minimised.

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

.. index:: best admin practices, best practices

.. _best_admin_practices:

Best practice
*************

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

.. index:: admin triage, triage, debug, admin debug, administration

.. _admin_triage:

Triage
******

When you come across problems with your LAVA instance, there are some basic
information sources, methods and tools which will help you identify the
problem(s).

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
   :ref:`migrating_known_device_example` and :ref:`developer_guide`.

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

TestJob data
------------

* **slave logs** are normally transmitted to the master but will also appear in
  ``/tmp/lava-dispatcher/slave/`` in directories named from the job ID. Logs
  include:

  * ``err`` - captures any errors during processing,

  * ``job.yaml`` - the test job configuration as sent from the master

  * ``device.yaml`` - the device configuration as sent from the master

  * ``logs/results.yaml`` - the results of the test job, as transmitted to the
    master. Useful for debugging issues with result handling or metadata
    generation.

  * The Lava Test Shell Overlay, if the test job used Lava Test Shell. This
    file is a tarball of the lava scripts and the test definitions which the
    dispatcher makes available to the test job at runtime. The overlay is named
    according to the level in the pipeline at which it was created (to allow
    for test jobs which would use multiple test actions). For example:
    ``overlay-1.3.4.tar.gz``.

* **job validation** - the master retains a copy of the output from the
  validation of the testjob. Currently, this validation occurs on the master
  but may move to the slave in future. The logs is stored on the master as the
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
    type: bootz
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


.. toctree::
   :hidden:
   :maxdepth: 1

   lava-tool-issues.rst
