.. index:: device integration - adding new device-types

.. _adding_new_device_types:

Adding new device types
#######################

.. warning:: This is the most complex part of LAVA and it can be a lot
  of work (sometimes several months) to integrate a completely new
  device into LAVA. V2 offers a different and wider range of support to
  V1 but some devices will need new support to be written within
  ``lava-dispatcher``. **It is not always possible to automate a new
  device**, depending on how the device connects to LAVA, how the
  device is powered and whether the software on the device allows the
  device to be controlled remotely. However, do not be tempted into
  using this complexity as an excuse to fall into the trap of
  :ref:`simplistic testing <simplistic_testing_problems>`.

Experience is the hardest and the most expensive teacher of all. This
section is an attempt to gather a set of guidelines from the collective
experience of a range of developers based on a wide range of devices
and the attempts to integrate those devices into LAVA. **Not all such
integrations succeeded** and more than one attempt resulted in broken
hardware. Most labs will be asked to integrate prototype or
pre-production hardware which always bring their own unique mix of
unexpected errors, limitations and failure methods.

The integration process is different for every new device. Therefore,
this documentation can only provide hints about such devices, based on
experience within the LAVA software and lab teams. **Please** talk to
us **before** starting on the integration of a new device using the
:ref:`mailing_lists`. Include full details of the type of device, the
bootloader specifications, hardware support and anything you have done
so far to automate the device. Sometimes, the supplied bootloader
**must** be modified to allow automation. Some devices need electrical
modifications or specialized hardware to be automated.

Integrating a new device type will involve some level of development
work, the device type templates are more than configuration. Testing
new device type templates requires setting up a developer workflow and
running unit tests as well as running test jobs on a LAVA instance. If
the new device type involves a new boot or deployment method, there
will also need to be changes in the ``lava-dispatcher`` codebase. New
elements of the test job submissions and device configuration may also
need changes to the schema in ``lava-server``. Some new device types
will be a lot easier than others - for example U-Boot tends to have a
reasonably consistent interface across multiple devices, so changes for
a new U-Boot device could be as little as setting variables after
extending the ``base-uboot.jinja2`` template.

The LAVA developers encourage new device type templates to be
:ref:`contributed upstream <contribute_upstream>` as a :ref:`community
contribution <community_contributions>` to LAVA.

.. seealso:: :ref:`growing_your_lab`, including :ref:`lab_scaling`.
   Also :ref:`developing_device_type_templates`,
   :ref:`developing_new_classes` and
   :ref:`migrating_known_device_example`

.. index:: device integration - device requirements

.. _device_requirements:

Device Requirements
*******************

The LAVA software and lab teams have built up a set of guidelines
relating to the integration of new device-types. The further a device
deviates from one or more of these guidelines, the harder it will
become to automate such a device. Always remember that the way that the
device is supported **must** scale to large labs which already contain
a range of other devices, each with their own issues. It is **not**
acceptable to add a new device-type which is incompatible with devices
which are already supported or which imposes restrictions on how many
devices of any type can be used in any one lab.

The guidelines only consider a limited number of possible problems with
device integration. The guidelines are written using our experiences of
a variety of poorly behaving devices over years of development of
automation software like LAVA. Depending on local admins, some labs can
cope with hardware which does not comply with all guidelines,
particularly if the devices are not being used at scale. However, the
more devices are deployed in any lab, the more it will be necessary for
every device to fully comply or such labs will quickly deteriorate,
generating unreliable results.

These guidelines describe device behavior as a whole. This is a
combination of the device hardware and the firmware. Some devices
support replacing the firmware. Sometimes this can aid automation,
sometimes is can cause more problems and complexity.

Device integration issues are often invisible when testing with a
single device attached to a single developer machine, so the single
device implementation **must** be proven to be reliable and
reproducible before starting to add more devices. For best results,
**only ever change one thing at a time**.

It is not possible to automate every piece of hardware, there are a
number of critical limitations.

.. seealso:: :ref:`pipeline_device_requirements`

.. _integration_reproducibility:

Reproducibility
===============

Reproducibility is the ability to deploy exactly the same software to
the same board(s) and running exactly the same tests many times in a
row, getting exactly the same results each time.

For automation to work, all device functions which need to be used in
automation **must** always produce the same results on each device of a
specific device type, irrespective of any previous operations on that
device, given the same starting hardware configuration.

There is no way to automate a device which behaves unpredictably.

Example One
-----------

Some devices have a mode which boots one boot method on the first boot
and then a different boot method on the second boot without allowing
for failures or canceled boot operations. This alternating boot is
**not** suitable for automation because it would require the automation
to keep state and does not take account of test job failures and
cancellations.

Example Two
-----------

A device which supports jumpers or DIP switches **must** respect those
hardware settings no matter what software is deployed to the device,
including when that software is buggy, broken or written to the wrong
location. It **must not** be possible for test jobs to *brick* the
device, that is to prevent the device from being able to start the next
test job without admin intervention.

.. _integration_reliability:

Reliability
===========

Reliability is the ability to run a wide range of test jobs, stressing
different parts of the overall deployment, with a variety of tests and
**always** getting a ``Complete`` test job. There must be no
``JobError`` or ``InfrastructureError`` failures and there should be
limited variability in the time taken to run the test jobs to avoid the
need for excessive :ref:`timeouts`.

The same hardware configuration and infrastructure **must** always
behave in precisely the same way. The same commands and operations to
the device **must** always generate the same behavior.

* If a device does not always recognize a critical component, for
  example the network hardware, then that device cannot be automated.

* If a device drops the serial connection or resets the connection in
  some situations during image deployment, then the device is not
  sufficiently reliable to be integrated.

* If a device relies on USB, it is possible that errors in the device
  hardware or software can cause instability in the USB stack of the
  worker to which it is connected. (Unlike ethernet, USB is a direct
  metal to metal connection and cannot easily be electrically
  isolated.) This can potentially cause issues with unrelated devices
  on the same worker.

.. note:: Many reliability issues can be symptoms of infrastructure
   problems but many devices can also exacerbate these failures by
   behaving in ways which do not fully comply with the standards and
   expectations of the infrastructure. It is **essential** that
   reliability issues are debugged during the process of scaling up the
   number of devices and complexity of your LAVA lab. Do **not** wait
   to debug reliability problems until after you have many devices.
   Quite how many devices counts as too many will vary massively
   according to the complexity of the requirements for each device.
   Sometimes, the only way to tackle reliability problems is to scale
   back, take devices offline or disconnect entire groups of devices
   and infrastructure. Debug your reliability issues **before** putting
   such devices into a production lab to minimize the risk of scheduled
   downtime.

.. _integration_scriptable:

Scriptability
=============

The device **must** support deployment of files and booting of the
device without **any** need for a human to monitor or interact with the
process. The need to press buttons is undesirable but can be managed in
some cases by using relays. However, every extra layer of complexity
reduces the overall reliability of the automation process and the need
for buttons should be limited or eliminated wherever possible. If a
device uses on LEDs to indicate the success of failure of operations,
such LEDs **must only be indicative**. The device **must** support full
control of that process using **only** commands and operations which do
not rely on observation.

.. _integration_scalability:

Scalability
===========

.. seealso:: :ref:`growing_your_lab`

All methods used to automate a device **must** have minimal footprint
in terms of load on the workers, complexity of scripting support and
infrastructure requirements. This is a complex area and can trivially
impact on both reliability and reproducibility as well as making it
much more difficult to debug problems which do arise. Admins must also
consider the complexity of combining multiple different devices which
each require multiple layers of support.

Some devices may need:

* relays to work around buttons,

* specialized hardware to work around deployment limitations,

* complex scripting around power control,

* a need to use :term:`LXC` for automation.

Any one of these burdens will make debugging issues on the worker and
on the devices difficult. Any combination of these burdens make
debugging many times more difficult than any one burden alone.

.. caution:: **ALWAYS START SMALL** and move forward in **small
   steps**. Remember that many of the deployment methods and tools used
   with some devices have been developed and tested only on the
   single-developer, single-device model. Once a single device is
   working, scale up **slowly**, make **one change at a time** then run
   dozens, preferably hundreds, of tests before stepping up in scale.
   It can make a significant difference even scaling up from one device
   to two, let alone to four or ten. Even the best behaved devices will
   need care to scale up to dozens of devices. LAVA can work with
   hundreds of devices but the only way to know how to deploy hundreds
   of **your** devices is to build slowly from one to two and then
   four, ten and beyond. To use thousands of devices, it is usually
   best to consider a :term:`frontend` which pulls results from several
   :ref:`micro_instances`.

Every LAVA lab is different. Planning is essential. When there is any
expectation that the lab will grow to support a lot of devices, take
care at the earliest initial stages to plan for the infrastructure that
can cope with the expected scale (and then add a bit again). It can be
very expensive (in time and money) to replace the initial
infrastructure like :abbr:`UPS (Uninterruptible Power Supply)` or
network switches or :term:`PDU`.

.. index:: device integration - power

.. _integration_power:

Power
=====

Devices **MUST** support automated resets either by the removal of all
power supplied to the :term:`DUT` or a full reboot or other reset which
clears all previous state of the DUT.

**Every** boot **must** reliably start, without interaction, directly
from the first application of power without the limitation of needing
to press buttons or requiring other interaction. Relays and other
arrangements can be used at the cost of increasing the overall
complexity of the solution, so should be avoided wherever possible.

Devices which have internal batteries become difficult to reliably
automate, unless the battery can be permanently removed. Forced reboots
become impossible without electrical modification of the device to
temporarily take the battery out of circuit. This means that it is much
easier to cause the device to go offline because of a broken kernel
build or broken image.

Battery charging can be an issue - devices may not behave normally when
held in ``fastboot`` mode or with a broken kernel build or image
deployed to the system. This can cause the device to fail to keep
charge in the battery or fail to recharge the battery, despite having
power available.

.. caution:: **Serial power leaks**
   some devices are capable of drawing power over the serial line used
   to control the device, despite the actual power supply being
   disconnected. Sometimes this requires a period of time to discharge
   capacitors on the board (fixable by adding a ``sleep`` in the
   :ref:`power_off_command <power_commands>`). Sometimes this power
   leak can cause the device to ``latch`` into a particular bootloader
   mode or other state which prevents the automation from proceeding.

.. index:: device integration - reset

.. _integration_reset:

Reset
=====

For a lot of devices, simply cycling power is sufficient for a full
reset. If the device supports reset by other means, for example when a
serial connection is made, then these resets **must** completely reset
the device so as to clear all buffers from previous test runs or
deployments, **including** when such test runs or deployments failed in
unexpected ways.

.. note:: It is recommended for all devices that admins disable ability
   of the device to automatically boot anything, but rather simply drop
   to the bootloader prompt.

.. index:: device integration - networking

.. _integration_networking:

Networking
==========

.. to be expanded as more specific content is added.

**Ethernet** - all devices using ethernet interfaces in LAVA **must**
have a unique MAC address on each interface. The MAC address **must**
be persistent across reboots. No assumptions should be made about fixed
IP addresses, address ranges or pre-defined routes. If more than one
interface is available, the boot process **must** be configurable to
always use the same interface every time the device is booted.

**WiFi** - is not currently supported as a method of booting devices.

.. index:: device integration - serial console

.. _integration_serial:

Serial console
==============

.. to be expanded as more specific content is added.

LAVA expects to automate devices by interacting with the serial port
immediately after power is applied to the device. The bootloader
**must** interact with the serial port. If a serial port is not
available on the device, suitable additional hardware **must** be
provided before integration can begin. All messages about the boot
process must be visible using the serial port and the serial port
should remain usable for the duration of all test jobs on the device.

.. OS what OSes are you expecting to run as test jobs? How will that
   change your integration requirements? testing of firmware - what
   software is to be tested? Does it have a :term:`BMC`?

.. index:: device integration - integration process

.. _integration_process:

Integration process
*******************

To add support for a new :term:`device type`, a certain amount of
development and testing **will** be required.

For some new device types, only a new :ref:`device type jinja2 template
<developing_device_type_templates>` will be required. Every new
template requires testing and a certain amount of debugging. Device
type templates need to be considered as code, not only configuration.
Some familiarity with how to :ref:`debug a LAVA instance
<admin_triage>` will be necessary.

For other device types, :ref:`new dispatcher Action classes
<adding_new_classes>` and new or modified :ref:`strategy classes
<using_strategy_classes>` will be needed. This typically involves a lot
of development time - make sure that you :ref:`contribute_upstream` so
that your local changes do not break when you next upgrade your LAVA
instance(s).

In addition, every new device type will need to be tested on a local
LAVA instance, so an amount of LAVA administration work will be
necessary.

It is **strongly** recommended that everyone who starts work to
integrate a new device type into LAVA is already familiar with
administering their own LAVA instance and has submitted dozens of LAVA
test jobs on at least two different device types already known to work
in LAVA V2. In most cases, a development instance will be needed as
well, so some familiarity with installing and upgrading a LAVA instance
is also recommended.

This means that developers adding new device types should already be
familiar with:

* :ref:`development_pre_requisites`

* :ref:`device_type_templates`

* :ref:`developing_device_type_templates`

* :ref:`testing_pipeline_code`

* :ref:`Administrator triage <admin_triage>`

* :ref:`admin_debug_information`

* :ref:`create_device_dictionary`

* :ref:`test_developer`

* :ref:`debian_installation`

* :ref:`setting_up_pipeline_instance`

* :ref:`using_gold_standard_files`

* :ref:`debugging_test_failures`

* :ref:`debugging_v2`

* :ref:`unit_tests`

* :ref:`hidden_assumptions`

In addition, some device types will require the developer to also be
familiar with:

* :ref:`adding_new_classes`

* :ref:`using_strategy_classes`

* :ref:`contribute_upstream` - maintaining new dispatcher classes
  without upstream support is **not** recommended. LAVA development
  moves relatively quickly.

* :ref:`pipeline_schema` - if your new device type needs changes to the
  test job submission schema.

* :ref:`deploy_using_lxc`

* :ref:`lava_lxc_protocol_android`

* :ref:`debugging_multinode`

.. caution:: Before going any further, **please** talk to us using the
   :ref:`mailing_lists`. Do **not** rush into integration. It is
   tempting to ask a lot of questions on :ref:`support_irc` but other
   conversations will overlap and pasting logs can become a burden. Use
   the mailing list and attach all the relevant data.

.. _integration_similarity:

Find a similar existing device type
***********************************

There are a number of places to check for similar types of device which
are already supported in LAVA V2.

#. https://master.lavasoftware.org/scheduler/

#. https://staging.validation.linaro.org/scheduler/

#. https://validation.linaro.org/scheduler/

#. https://lng.validation.linaro.org/scheduler/

#. https://git.lavasoftware.org/lava/lava/tree/master/lava_scheduler_app/tests/device-types

Check for:

* similar bootloader

* similar deployment type

* similar deployment or boot process

* similar sequence of boot steps

If you do not find something similar, we strongly recommend that you
**stop here** and :ref:`talk to us <mailing_lists>` before doing
anything else. Be clear about exactly what kind of device you are
trying to integrate. Include details of exactly how the device
currently boots and exactly how new files are deployed to the device.
Do not resort to :ref:`simplistic testing
<simplistic_testing_problems>`.

.. caution:: Do not be tempted to re-use the existing support for
  something which is not actually using that support. Just because
  your custom system looks like U-Boot or fastboot does **not**
  mean you should mangle the existing support to fit. If you need
  something which is similar but not the same, write a new set of
  classes and templates. By all means, use that existing code as a
  starting point.

  Avoid sharing method-specific syntax with a similar but different
  method. U-Boot or fastboot parameters and options remain specific to
  U-Boot or fastboot respectively. While this might look like a quick
  and easy way to add support, it is very likely that future changes
  to the support you're abusing might break your tests without
  warning.

.. _integration_extend_template:

Extend from an existing device type template
********************************************

All new device type templates need to ``extend 'base.jinja2'`` but
there are also other base templates which simplify the process for
certain bootloaders. For example, all new U-Boot device type templates
should ``extend 'base-uboot.jinja2``. Many new fastboot device type
templates can ``extend 'base-fastboot.jinja2``. Avoid directly
extending any of the templates which do not have the ``base`` prefix -
instead copy the existing template for your new device type. When this
template is :ref:`contributed upstream <contribute_upstream>`, a new
``base`` template can be considered as part of the review process.

.. _integration_unit_test:

Extend the template unit tests
******************************

.. seealso:: :ref:`testing_new_devicetype_templates`,
   :ref:`debugging configuration files <debugging_configuration>`
   and setting character delays due to :ref:`input_speeds`.

All device type template files in
``tests/lava_scheduler_app/devices`` will be checked for simple
YAML validity by the ``test_all_templates`` unit test. However, a
dedicated unit test is recommended for all but the simplest of new
device type templates. At the very least, having a unit test for your
new device type template will assist in debugging why the test job does
not run to completion. The full device configuration can be output as
part of running the unit test by changing the ``debug`` value to
``True`` at the top of the ``TestTemplates`` class in
``test_templates.py``.

Add your new device-type template to
``tests/lava_scheduler_app/devices``. Edit
``tests/lava_scheduler_app/test_templates.py`` and add a new unit test
for your device-type based on one of the existing test functions.
Create a dummy device dictionary as a ``data`` string and ensure that
the combination of the template and the dictionary creates a valid
device. This can be as simple as:

.. code-block:: python

    def test_pixel_template(self):
        self.assertTrue(self.validate_data('staging-pixel-01', """{% extends 'pixel.jinja2' %}
 {% set adb_serial_number = 'FDAC1231DAD' %}
 {% set fastboot_serial_number = 'FDAC1231DAD' %}
 {% set device_info = [{'board_id': 'FDAC1231DAD'}] %}
 """))

In many cases, some of the default values in the base template will
need to be altered for your new device-type. For example:

.. code-block:: jinja

 {% set boot_character_delay = 150 %}

If the value may also need to be extended for some devices of this
device type, you should provide the new value as a default in the
template so that a device dictionary can set an override:

.. code-block:: jinja

 {% set baud_rate = baud_rate | default(115200) %}

.. note:: When setting updated values for defaults in the base
   template, ensure that the line setting the new value is **above**
   the start of the important ``body`` block which will contain the
   output of that value.

   .. code-block:: jinja

    {% extends 'base.jinja2' %}
    {% set boot_character_delay = 150 %}
    {% set console_device = console_device | default('ttyAMA0') %}
    {% set baud_rate = baud_rate | default(115200) %}

    {% set base_nfsroot_args = nfsroot_args | default(base_nfsroot_args) -%}
    {% set kernel_args = kernel_args | default('acpi=force') %}

    {% block body %}

Every time you make a change to the new template in
``lava_scheduler_app/tests/device-types``, re-run the specific unit
test for your new device type. For example, a new unit test function
defined as ``test_foobar_template`` can be run without running the rest
of the unit tests:

.. code-block:: shell

 $ python3 -m unittest -vcf tests.lava_scheduler_app.test_templates.TestTemplates.test_foobar_template

Remember that device type templates are not just configuration files -
the templates are processed as source code at runtime and can use
various types of logic to substitute the correct variables and omit
other variables. **Always** make your changes in
``lava_scheduler_app/tests/device-types`` and **always** run the unit
test to ensure that changes to the template continue to produce a valid
device configuration after each change.

Only when the unit test passes should the new device type template be
copied to ``/etc/lava-server/dispatcher-config/device-types/``. If the
scheduler tries to assign a test job to a device using this template, a
check will be made to ensure that the output of the template and the
device dictionary is valid. If that check fails, the test job will not
start and the failure will be logged:

.. code-block:: none

 [WARNING] [lava-master] [9] Refusing to reserve for broken V2 device intel-smecher

This message indicates that test job ID ``9`` will never start to run
until the device dictionary and the device type template for the device
``intel-smecher`` are fixed so that the output is valid. It is common
for the rendering of new device type templates to cause subtle YAML
syntax errors. It is also common for the output to be valid YAML but
not valid device configuration. The unit test **must** check for a
valid device configuration, not simply valid YAML. In addition,
whenever it is imperative that a certain value is overridden in the
device type template compared to the base template, the unit test
**must** check that this value has been correctly set in the generated
pipeline. Check the other unit tests in the ``test_*_templates.py``
files to see how this is done. e.g. for QEMU from
``test_qemu_templates.py``

.. code-block:: python

    def test_qemu_installer(self):
        data = """{% extends 'qemu.jinja2' %}
 {% set mac_addr = 'DE:AD:BE:EF:28:01' %}
 {% set memory = 512 %}"""
        job_ctx = {'arch': 'amd64'}
        template_dict = prepare_jinja_template('staging-qemu-01', data, job_ctx=job_ctx, raw=False)
        self.assertEqual(
            'c',
            template_dict['actions']['boot']['methods']['qemu']['parameters']['boot_options']['boot_order']
        )

.. note:: This section only covers the unit tests in the
   ``lava_scheduler_app`` directories in the LAVA codebase. If your
   device integration process requires changes in the
   ``lava_dispatcher`` directory, a set of unit tests will also be
   required there to ensure that the new code operates correctly.
