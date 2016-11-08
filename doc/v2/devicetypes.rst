.. _device_types:

Device types
############

When adding devices, there is a decision to be made about what qualifies as a
device type and what does not. A different type of device can mean different
things, including:

#. different hardware.
#. different access methods (typically, bootloaders).
#. different test writer use cases, e.g. testing firmware or testing user space
   performance.

However, a slight or incremental change to hardware does not necessarily mean
that the updated device is a different device type. Even if a change adds
significant functionality, e.g. if USB hot-plug becomes available on revision
C, that does not necessarily mean that revision C is a different device type to
revision A and B.

Typically, the distinction between two device types comes down to whether the
two devices can be driven in the same way at bootloader level, from initial
power on.

Another example to consider is :term:`DTB` support. If there is more than one
DTB available for a particular family of devices, this will probably lead to
multiple different device types. Also consider whether all devices of the
proposed device type can boot all DTBs available for that type.

Administrators are free to make their own choices about what qualifies as a
device type. Some factors include:

**Interchangeable jobs**
  Does a single health check work for all devices of this type? It is
  recommended to always test all of the supported boot methods of a device type
  during a single health check test job.
**Interchangeable bootloaders**
  Some devices can change bootloader type within a single job, allowing a
  single device-type to meet the needs of a variety of different use cases.
  There are issues to consider here:

  * **Latency**
    Changing the bootloader on every test job may have significant costs in
    terms of job runtime. This is particularly noticeable in the length of
    time required before the actual test can start. In such cases, it may be
    worth considering a **sub-type** instead.

    .. seealso:: :ref:`sub_device_types`

  * **Lifetime of the device**
    Frequently writing a new bootloader may cause problems on some devices where
    the bootloader may be stored on media which can only be written a limited
    number of times.

**Multi-stage bootloaders**
  Some devices may have a first or second stage bootloader which can then load
  different higher level bootloaders. This is often described as a chained
  bootloader. Depending on the types of tests desired, some admins may choose
  to expose a choice of higher level bootloader or may choose to not allow
  interrupting the lower stage(s). For example, some test writers will want to
  test the firmware and some test writers will only want to interact with GRUB
  or later.
**Equivalence**
  Different labs may make different decisions - if you are looking to work with
  an existing lab, try to follow their device type layout and ask about how a
  new device should be classified before committing to a decision in your own
  lab.
**Test requirements**
  Talk to the test writers and establish whether an apparent hardware
  difference is sufficient that the device needs to be a different type.
  Consider whether the test writer requirements are going to change over time -
  just because there is no current desire to test the experimental bootloader
  available on one device, this does not mean that this will remain unused in a
  year.
**Scheduling**
  If two devices have the same device type, each device needs to be able to run
  any test job submitted for that device type. There is support for encoding
  small differences between devices within a single device type - see
  :term:`device tag`.
**LAVA support**
  There are some considerations which are constrained by LAVA support - for
  example the V1 dispatcher had a ``kvm`` device type but the improved device
  configuration design in V2 made this unnecessary. If the only factor
  requiring two device types is LAVA support, please :ref:`talk to us
  <getting_support>`.

Permanency
==========

Once a device type has been implemented, devices added and test jobs run, it
can be awkward to change the device type. Changing the device type later will
make it difficult for users to find test results across this and other devices
and may cause significant issues with data consistency.

Separate device types can also complicate queries and result reporting -
combining two devices which eventually end up being different device types
causes issues with a loss of history when the split is finally made.

It is not a good idea to split device types arbitrarily - sooner or later there
may be a requirement to look at the results of jobs across both types and
having an unnecessary device type is confusing for test writers. Use a
:term:`device tag` to describe small differences between devices of the same
device type.

.. seealso:: :ref:`device_type_metadata`.

.. _sub_device_types:

Device sub types
================

A balance needs to be drawn between test jobs which simply want to use a
known working build of the firmware and/or bootloader and those test jobs
where the latest build is relevant to the success or failure of the test
itself. Different test writers may have different requirements here.

An example of sub-types could be ``juno-uboot`` compared to ``juno-firmware``.
Consider the principle of *test one thing at a time* - let userspace test jobs
run without needing to change the bootloader and let bootloader test jobs have
the ability to update by separating the device-type into two sub-types.

Think about device integration here. You need to be able to interrupt the boot
process at a level below whatever you are exposing to test writers. For
example, to offer test writers the ability to modify and test the firmware, the
platform **must** offer a way to replace the firmware in an automatable manner.

.. _naming_device_types:

Choosing a name for a device type
=================================

There are some considerations for the names of a device-type in LAVA.

#. The name of the device type in the database will be used as part of the URL
   of the page covering details of that device type, so the name **must not**
   include characters that would be encoded in a URL. This includes whitespace,
   UTF-8 characters, brackets and other common punctuation characters.

#. Hyphens and underscores are supported.

#. In general, the name should represent the hardware in a way that uniquely
   separates that type from similar hardware, e.g. panda and panda-es or
   imx6q-wandboard instead of just 'wandboard'.

#. Each type has a description which can be used to provide lab-specific
   information, so the name does not have to include all details.

#. Check other LAVA instances, especially if your instance is likely to need to
   work with other instances with a single frontend (like kernelci.org)

#. Choose a sensible, descriptive name that will make sense to test writers.
   For example, ``panda`` or ``panda-es`` instead of ``panda1`` or ``panda2``.

.. index:: template mismatch

.. _template_mismatch:

Matching the template
---------------------

.. # comment: prevent this in the submission API once V1 jobs are rejected.

The name of a device type **must** match an available template. On the master,
device-type templates are configured using :term:`jinja2` files in the
directory::

 /etc/lava-server/dispatcher-config/device-types/

When creating a new device type, it is recommended to add the new template
file first.

.. index:: device type examples

.. _example_device_types:

Example device-types
====================

* The ``panda`` and ``panda-es`` device types are separate in the Cambridge
  LAVA lab. When originally introduced, there was an expectation that the
  hardware differences between the devices would be relevant to how the jobs
  were constructed. As it turned out, no such difference was actually exploited
  by the test writers.

* The ``mustang`` device type can support both U-Boot and UEFI bootloaders but
  not on the same machine at the same time. The bootloader can be changed, but
  this is a custom process which is not manageable during a test job. In the
  Cambridge lab, ``mustang`` implies U-Boot and a separate sub device-type
  called ``mustang-uefi`` is available for test jobs needing UEFI.

* ``panda`` devices can support operating systems like Debian as well as
  supporting Android deployments using the same bootloader in both cases -
  U-Boot. Therefore only one device type was needed here.

.. _device_type_elements:

Database elements for a device type
===================================

The device type exists as a django database object which can be modified using
the :ref:`django admin interface<django_admin_interface>`. The following fields
are supported:

Name - the name of the device type
   See :ref:`naming_device_types`. Needs to match the name of a jinja
   template in ``/etc/lava-server/dispatcher-config/device-types/``,
   without the ``.jinja2`` suffix.

Health check job - the YAML test job submission for a health check
   See :term:`health check`

Display - should this device type be displayed in the GUI or not?
   Enabled by default - device type display can be disabled to hide the data
   about the device type from the UI, without deleting the object and
   associated data. The device type remains accessible in the django
   administrative interface.

Owners only - device type is only visible to owners of devices of this type
   Disabled by default - enable to create a :term:`hidden device type`.

Health check frequency - how often to run health checks
   Each device type can run health checks at a specified frequency which can be
   based on time intervals or numbers of test jobs.

Descriptive fields
------------------

The device type database also includes some optional fields which may be
completed by the admin to provide information for test writers:

**Architecture name**
  e.g. ARMv7, ARMv8

**Processor name**
  e.g. AM335X

**CPU model name**
  e.g. OMAP 4430 / OMAP4460

**List of cores**
  The number of cores on the device and the type of CPUs. In the admin
  interface, cores can be added and the number of each core specified. e.g. 4 x
  Cortex-A9

**Bit count**
  e.g. 32 or 64
