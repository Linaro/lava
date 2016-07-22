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

Outline
*******

LAVA is complex and administering a LAVA instance can be an open-ended
task covering a wide range of skills.

* **Debian system administration**
* **Device integration**
* **Network configuration**
* **Writing tests**
* **Triage**
* **Python/Django knowledge** - for debugging

Start small
===========

These rules may seem harsh or obvious or tedious. However, multiple
people have skipped one or more of these requirements and have learnt
that these steps provide valuable advice and assistance that can
dramatically improve your experience of LAVA. Everyone setting up LAVA,
is **strongly** advised to follow all of these rules.

#. **Start with a minimal LAVA install** with at most one or two
   devices - at this stage only QEMU devices should be considered.
   This provides the best platform for learning LAVA, before learning how
   to administer a LAVA instance.

#. **Use the worked examples** in the documentation which
   refer back to standard builds and proven test jobs. There will be
   enough to do in becoming familiar with how to fix problems and issues
   local to your own instance without adding the complexity of devices
   or kernel builds to which only you have access.

#. **Avoid rushing to your custom device** - device integration into
   *any* automated system is **hard**. It does not become any easier if
   you are trying to learn how to use the automation as well.

#. **Plan how to test**

   * use the examples and :term:`device types <device type>`
     which are **known** to work.
   * Read through all the worked examples before starting your planning,
     there are likely to be useful ways to do what you want to do and
     advice on **why** it is a bad idea to do some of the things you may
     have considered at the start.
   * plan out how to do the testing of other custom devices by looking
     for similar device support already available in other LAVA instances.
   * **Avoid shortcuts** - it may seem that you only want to *connect & test*
     but there are
     :ref:`known problems with overly simplistic approaches <simplistic_testing_problems>`
     and you are likely to need to use ``deploy`` actions and ``boot``
     actions to be able to produce reliable results.

#. **Have at least one test instance**. A single instance of LAVA
   is never sufficient for any important testing. Everyone needs at least
   one test instance in a VM or on another machine to have confidence that
   administrative changes will not interfere with test jobs.

#. **Control your changes** - configuration, test job definitions,
   test shell definitions, :term:`device dictionaries <device dictionary>`,
   template changes and any code changes - all need to be in **version control**.

#. **Subscribe** to the :ref:`mailing_lists` where you will find
   others who have setup their own LAVA instances.

.. _simplistic_testing_problems:

Problems with simplistic testing
================================

#. '*connect & test*' seems simple enough - it doesn't seem as if you
   need to deploy a new kernel or rootfs every time, no need to power
   off or reboot between tests. *Just* connect and run stuff.  After
   all, you already have a way to manually deploy stuff to the board.
   The biggest problem with this method is :ref:`persistence` - LAVA
   keeps the LAVA components separated from each other but test
   frequently need to install support which will persist after the test,
   write files which can interfere with other tests or break the manual
   deployment in unexpected ways when things go wrong.

#. '*test everything at the same time*' - you've built an entire system
   and now you put the entire thing onto the device and do all the tests
   at the same time. There are numerous problems with this approach:

   #. **Breaking the basic scientific method** of test one
      thing at a time. The single system contains multiple components,
      like the kernel and the rootfs and the bootloader. Each one of
      those components can fail in ways which can only be picked up when
      some later component produces a completely misleading and unexpected
      error message.
   #. **Timing** - simply deploying the entire system for every single
      test job wastes inordinate amounts of time when you do finally
      identify that the problem is a configuration setting in the
      bootloader or a missing module for the kernel.
   #. **Reproducibility** - the larger the deployment, the more complex
      the boot and the tests become. Many LAVA devices are prototypes
      and development boards, not production servers. These devices **will**
      fail in unpredictable places from time to time. Testing a kernel
      build multiple times is much more likely to give you consistent
      averages for duration, performance and other measurements than if
      the kernel is only tested as part of a complete system.
   #. **Automated recovery** - deploying an entire system can go wrong,
      whether an interrupted copy or a broken build, the consequences can
      mean that the device simply does not boot any longer.

      * **Every component** involved in your test **must** allow for
        automated recovery. This means that the boot process must support
        being interrupted **before** that component starts to load. With
        a suitably configured bootloader, it is straightforward to test
        kernel builds with fully automated recovery on most devices.
        Deploying a new build of the bootloader **itself** is much more
        problematic. Few devices have the necessary management interfaces
        with support for secondary console access or additional network
        interfaces which respond very early in boot. It is possible to
        chainload some bootloaders, allowing the known working bootloader
        to be preserved.

   #. Finally, note that it is **not** possible to automate every
      test method. Some kinds of tests, some kinds of devices lack critical
      elements that block automation - these are not problems in LAVA, these
      are design limitations of the kind of test and the device itself.
      Your preferred test plan may be infeasible to automate and some
      level of compromise will be required.

Early admin stuff:

* recommendations on how to do admin:

  * start simple using our examples
  * build complexity slowly
  * only once you're confident, start adding novel devices

* where to find logs and debug information
* device configuration and templates
