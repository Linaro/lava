.. _device_types:

Identifying device types
************************

When adding devices, there is a decision to be made about what qualifies
as a device type and what does not. A different type of device can
mean different things, including:

#. different hardware
#. different access methods (typically, bootloaders)

However, a slight or incremental change to hardware does not necessarily
mean that the updated device is a different device type, even if that
change adds a fix which makes significant functionality available. e.g.
if USB hotplug becomes available on revision C, that does not necessarily
affect whether revision C is a different device type to revision A and B.

Typically, the distinction between two device types comes down to whether
the two devices can be driven in the same way at bootloader level, from
initial power on.

Another example is a DTB. If a dtb is available for the device and is
a different binary to the dtb for the second device, consideration should
be given as to whether this merits the devices being two different
device types, unless all devices of the proposed type can boot all
dtbs available for that type.

Administrators are free to make their own choices about what qualifies
as a device type, some factors include:

**Interchangeable jobs**
  The device type has a single health check and this remains a requirement
  because it helps to illustrate where a device may need to be a different
  type.
**Interchangeable bootloaders**
  Some devices can update the bootloader and change between different
  bootloader types within a single job, even so, this may have significant
  costs in terms of job runtime (especially the amount of time required
  before the actual test can start after waiting for the bootloader to
  be updated) and in terms of the expected lifetime of the device (some
  bootloaders live on media which can only be written a limited number
  of times).
**Earlier bootloaders**
  Some devices may have a first or second stage bootloader which can then
  switch the location of the bootloader used during the test. This is often
  described as a chained bootloader and the decision comes down to whether
  the earlier bootloader can be interrupted (possibly via GPIO lines) and
  whether updating the next bootloader in the chain can be done without
  issues of reducing the lifetime of the media for that bootloader.
**Permanency**
  Once implemented, it can be problematic to change the decision made when
  the device is introduced. Separate device types can complicate queries
  and result reporting - combining two devices which eventually end up
  being different device types causes issues with a loss of history when
  the split is finally made.
**Equivalence**
  Different labs may make different decisions - if you are looking to work
  with an existing lab, follow their device type layout and ask about how
  a new device should be classified before committing to a decision in your
  own lab.
**Test requirements**
  Talk to the test writers and establish whether an apparent hardware
  difference is sufficient that the device needs to be a different type.
  Consider whether the test writer requirements are going to change over
  time - just because there is no current desire to test the experimental
  bootloader available on one device, does not mean that this will remain
  unused in a year.
**Scheduling**
  If two devices are the same device type, each device needs to be able
  to run any test job submitted for that device type. There is scope for
  enhancing the scheduler to know about differences between devices but
  this is best done using a :term:`device tag`. This also applies to
  :term:`health check` jobs - it is recommended to always test all of the
  supported boot methods of a device type during a health check - if that
  would mean slowly writing a new bootloader, testing, then slowly writing
  a second bootloader, it may be preferable to have two device types.
**LAVA support**
  There are some considerations which are constrained by LAVA support -
  for example the current dispatcher has a ``kvm`` device type but the
  :term:`pipeline` has made this unnecessary as the only difference
  between ``kvm`` and ``qemu`` device types were command line options.
  So the new dispatcher uses ``qemu`` for both and the architecture is
  specified in the device dictionary. ``qemu01`` could be ``x86_64``
  and ``qemu02`` could be ``mips``. It is suggested that such devices
  either include such details in the name or in the description of the
  device itself (which is editable by all owners of the device). If the
  only factor requiring two device types is LAVA support, please consider
  filing a bug so that this can be investigated.

.. note:: It is not a good idea to split device types arbitrarily - sooner
   or later there will be a requirement to look at the results of jobs
   across both types and having an unnecessary device type is confusing
   for test writers. Use a :term:`device tag` for small differences between
   devices of the same device type.

See also :ref:`device_type_metadata`.

.. _naming_device_types:

Choosing a name for a device type
=================================

There are some considerations for the names of a device-type in LAVA.

#. The name of the device type in the database will be used as part of
   the URL of the page covering details of that device type, so the name
   **must not** include characters that would be encoded in a URL. This
   includes whitespace, UTF-8 characters, brackets and other common
   punctuation characters.
#. Hyphens and underscores are supported.
#. In general, the name should represent the hardware in a way that uniquely
   separates that type from similar hardware, e.g. panda and panda-es or
   imx6q-wandboard instead of just 'wandboard'.
#. Each type has a description which can be used to provide lab-specific
   information, so the name does not have to include all details.
#. Check other LAVA instances, especially if your instance is likely to
   need to work with other instances with a single frontend (like kernelci.org)

.. index:: template mismatch

.. _template_mismatch:

.. # comment: prevent this in the submission API once V1 jobs are rejected.

Matching the template
---------------------

The name of a device type **must** match an available template in the form::

 /etc/lava-server/dispatcher-config/device-types/{{name}}.jinja2

The UI will raise an configuration error when viewed by the admin, if no matching
template is found.

Examples
========

* The ``panda`` and ``panda-es`` device types are separate in the Cambridge
  LAVA lab as, when originally introduced, there was an expectation that the
  hardware differences between the devices would be relevant to how the jobs
  were constructed. As it turned out, no such difference was actually
  exploited by the test writers.

* The ``mustang`` device can support U-Boot and UEFI bootloaders but not on
  the same machine. The bootloader can be changed but this is a custom
  process which may or may not be manageable during a test job. Whereas
  the :term:`pipeline` could distinguish between the two boot methods,

* UEFI menu and UEFI shell are usually the same device type as the initial
  state of the one bootloader can determine how the subsequent operations
  proceed.

* ``panda`` devices can support operating systems like Debian as well as
  supporting Android deployments using a single bootloader - U-Boot.

.. _device_type_elements:

Elements of a device type
=========================

**Name**
   - see :ref:`naming_device_types`. Needs to match the name of a
     jinja template in ``/etc/lava-server/dispatcher-config/device-types/``,
     without the ``.jinja2`` suffix.

**Has health check**
   - see :term:`health check`

**Display**
   Enabled by default - can be disabled to hide the data about the
   device type from the UI, without deleting the object and associated
   data. The device type remains accessible in the django administrative
   interface.

**Owners only**
   Disabled by default - enable to create a :term:`hidden device type`.

**Health check frequency**

   Each device type can run health checks at a specified frequency which
   can be based on time intervals or numbers of test jobs.

The device type also includes descriptive fields which would typically
be empty for emulated device types:

**Architecture name**
  e.g. ARMv7, ARMv8

**Processor name**
  e.g. AM335X

**CPU model name**
  e.g. OMAP 4430 / OMAP4460

**List of cores**
  The number of cores on the device and the type of CPUs.
  In the admin interface, cores can be added and the number of
  each core specified.
  e.g. 4 x Cortex-A9

**Bit count**
  e.g. 32 or 64
