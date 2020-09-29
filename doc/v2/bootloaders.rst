.. index:: bootloader testing with recovery, firmware testing with recovery

.. _bootloader_testing_recovery:

Bootloader/Firmware Testing and Recovery
########################################

LAVA supports deploying new bootloader/firmware builds with recovery
from broken builds on boards which meet full bootloader automation
criteria. When using LAVA as a part of :ref:`continuous_integration`,
it is expected that some of the bootloader builds will fail due to new
bugs or regressions, just as with any other software being tested.

.. note:: For the purposes of this documentation, LAVA does not make
   any distinction between firmware and bootloader on the boards that
   it supports. Support depends simply on the ability to recover the
   board after a deployment of a broken build.

A reliable, effective and low-operational-cost automation methodology
requires automated recovery without any manual intervention. [#f1]_ In
an environment where there is a mixed user pool, a board needs to be
available for the next test job in the queue, using a known working
bootloader build, as soon as the recovery from the previous test job is
complete.

Recovery should be a conditional element of every bootloader test job
using a second deploy and boot action. LAVA has support for fixing up a
broken bootloader build by running a :term:`health check` test job to
deploy a known working build, as long as the breakage can be reliably
detected. The bootloader deployment and recovery test job should raise
an infrastructure error to automatically trigger a health check.

Bootloader testing on boards which do not provide for automated
recovery cannot be supported by automation.

.. [#f1] A smaller number of boards support automated installation of a
   bootloader but don’t support automated recovery. In an environment
   where failures are expected, introducing manual recovery steps in an
   otherwise automated testing environment should be considered very
   carefully.

.. index:: recovery mode

.. _recovery_mode:

What is recovery mode?
**********************

Recovery mode is a hardware feature which allows boards to be
`unbricked <https://en.wikipedia.org/wiki/Brick_(electronics)>`_ after
a serious system error or a failed update of the bootloader, kernel or
operating system. Recovery mode is not necessarily the same as the
methods used to deploy firmware to a bare metal device during
manufacture.

* Recovery mode needs to implement a way to write a new
  bootloader build which must be fully usable even if the bootloader is
  absent or invalid, i.e. without any attempt to execute the current
  bootloader.

* Recovery mode must be able to write a new bootloader to the
  board directly after applying power to the device and then allow the
  board to execute the new bootloader to continue operation upon
  leaving recovery mode.

.. seealso:: :ref:`bootloader_execution`

.. index:: bootloader recovery criteria

.. _bootloader_recovery_criteria:

Bootloader recovery criteria
****************************

Juno, HiKey 6220 and X15 GPEVM are the only boards capable of supporting
bootloader testing and recovery out of the hundreds of boards which
have been integrated into LAVA over the years.

.. note:: Of the supported boards, the HiKey 6220 has noticeable
   limitations. It is possible to workaround some difficulties on some
   boards but this will limit the usefulness and scope of any
   bootloader testing on those boards.

   .. seealso:: :ref:`limits_of_hikey_6220`

The difficulties cover a number of areas:

Reliability
===========

All aspects of bootloader testing and recovery need to be reliable
for :ref:`CI <continuous_integration>` to operate:

* Entering and leaving recovery mode

* Appearance of interfaces to transfer data within recovery mode

* Transfer of data during recovery

* Stability of the hardware during recovery (considering that the
  files being transferred - and executed - are untested, may contain
  invalid sequences or be corrupted during the build).

Uniqueness
==========

Automation relies on being able to identify one board out of hundreds,
some of which will be in the same or very similar states to the one
board in use for this test job.

* Every board needs to expose a distinct identifier across all
  interfaces.

  .. important:: The HiKey 6220 cannot do this in recovery mode and is
     therefore restricted to only one board for each worker. This
     dramatically reduces the availability of bootloader testing and
     recovery using this board.

     .. seealso:: :ref:`limits_of_hikey_6220`

* All identifiers must be independent of the software deployed on the
  device. If identifiers change when firmware is updated, the board
  will effectively disappear underneath the automation.

* All identifiers must be stable across reboots and test jobs.

Scalability
===========

**Keep Things Simple**. Every item below adds to the complexity of the
final test jobs and failure rates will rise, in a non-linear manner,
with each increase in complexity.

* Jumpers require relays which require software control interfaces

* Relays will eventually fail after a finite number of operations.

* Recovery mode devices which appear or disappear after a hardware
  timeout will be a cause of intermittent failures.

* Hardware modifications cause deviations from the original or final
  product, potentially invalidating some results.

* Not all automation admin teams have the necessary hardware experience
  to make modifications to a board.

* Custom hardware peripherals can interfere with board hardware or
  software causing intermittent failures or non-standard behavior.

* Security requirements of a production / consumer device are typically
  incompatible with automation requirements. Access to recovery mode
  may be removed to prevent consumer access to protected content.
  Nonetheless, try to get as much of the recovery mode support
  available out-of-the-box as possible to manage the failure rate.

* The further the automation infrastructure diverges from the
  manufacturer infrastructure, the harder it will be to triage and fix
  the problems with the bootloader. This is a particular problem for
  intermittent failures.

  If the manufacturer has a custom rig used to deploy the original
  firmware, a copy of such a rig may be a significant advantage when
  automating bootloader testing and recovery. The lack of such a rig
  has blocked bootloader testing and recovery on several boards.

.. _recovery_deployment:

Deployment
==========

Automation must always be able to interrupt the boot process at a stage
**lower** than the stage being tested. This is why a BMC is so useful,
provided that the operation of the BMC is stable, reliable and
deterministic.

.. seealso:: `HKG18-TR10 - Best practices for getting devices in
   LAVA (slides)
   <https://www.slideshare.net/linaroorg/hkg18tr10-best-practices-for-getting-devices-in-lava>`_
   Video also available: https://youtu.be/jHyanD1II90

.. _barriers_to_automated_recovery:

Comparison of barriers to bootloader testing and recovery
*********************************************************

LAVA has a low tolerance for failure so that issues can be detected
early, avoiding a **false positive** where a test passes because an
error was not detected. Developers will need reliable result data from
the automated bootloader testing and recovery to avoid wasting time on
spurious **false negative** reports which mis-report a failure as being
caused by the code when it was due to the automation infrastructure.
The hardest problems to solve are intermittent faults in a complex
stack Every requirement which is not fully supported adds complexity to
the final automation and risks increasing the failure rate.

+------------------------------------------+-----------------+------+-----------------+
| Requirement                              | HiKey 6220 BL   | Juno | X15 GPEVM BL    |
+==========================================+=================+======+=================+
| Interrupt boot before bootloader [#f2]_  | Yes             | Yes  | Yes             |
+------------------------------------------+-----------------+------+-----------------+
| Presence of a recovery mode [#f3]_       | Yes             | Yes  | Yes             |
+------------------------------------------+-----------------+------+-----------------+
| Automated access to recovery [#f4]_      | Needs relays    | Yes  | Needs relays    |
+------------------------------------------+-----------------+------+-----------------+
| Writing data in recovery mode [#f5]_     | Dynamic USB TTY | Yes  | Dynamic USB TTY |
+------------------------------------------+-----------------+------+-----------------+
| Unique identification in recovery [#f6]_ | **NO**          | Yes  | Yes             |
+------------------------------------------+-----------------+------+-----------------+
| Stable operation in recovery             | Yes             | Yes  | Yes             |
+------------------------------------------+-----------------+------+-----------------+

.. [#f2] See :ref:`recovery_deployment` - most boards in LAVA cannot
   provide this support.

.. [#f3] See :ref:`recovery_mode`

.. [#f4] Consumer devices need to be protected from accidentally entering
   recovery mode, so manufacturers put constraints on how recovery mode
   is accessed. For example, having to press multiple buttons at the
   same time or in a specific order or hold down until something shows
   on the screen. For recovery mode to be used in automation, access to
   recovery mode must be as simple as possible - complexity always
   increases the failure rate.

   HiKey 6220 and X15 GPEVM have jumpers to select recovery mode which is
   easier to automate than buttons but still requires external hardware which
   then needs additional software to be written to automate the control
   of the board. Attaching relays to jumpers is very different to
   soldering connections onto a DIP switch. Many lab admin teams do not
   include a hardware engineer.

.. [#f5] The use of dynamic devices like ``/dev/ttyUSB*`` requires
   unique identification in recovery mode.

.. [#f6] The HiKey 6220 dynamic USB TTY device does not have a unique
   identifier on the host. If board-01 is already in recovery mode and
   board-02 enters recovery mode whilst connected to the same host,
   board-01 becomes inaccessible. This limits the use of recovery mode
   to one board per host.

Defensive testing
=================

Avoid creating a burden on all boards to support bootloader testing and
recovery from only some test jobs. Once intermittent errors occur with
boards which need some level of custom support for recovery mode, it
will be much harder to investigate if the failure cannot be tested on
boards which do not have recovery mode support. It would be better to
have two :term:`device types <device type>`, one with recovery mode
support and one without, whenever there is any doubt about the
reliability of the recovery mode support.

.. _bootloader_execution:

Problems with bootloader execution
**********************************

Some boards can support replacing the bootloader within a test job but
still rely on the current bootloader to execute to allow the board to
boot to a stage where that functionality is available. For example, it
is possible to write new U-Boot files to many U-Boot devices once
booted into a ramdisk from within a test job. Alternatively,
``fastboot`` devices support writing a new fastboot binary at the same
stage as writing a new kernel or system image. This **does not qualify
as recovery mode** because those same files must be executed before the
board can boot to the stage where new files can be written.

Two serious failures are possible:

* the new files fail to execute in the ways required by the automation,
  requiring manual intervention

* the new files contain a failure not executed by the automation,
  potentially requiring a product recall

Therefore, the bootloader files must undergo manual testing before
being made available and this dramatically limits the opportunity for
CI on those bootloader files.

For example, ``fastboot`` mode is not recovery mode for two reasons:

* the ``fastboot`` binary can be overwritten (by ``fastboot``) within
  normal operation of a test job and therefore rendered corrupt or
  missing,

* every ``fastboot`` binary needs to be executed to write a
  replacement of itself.

Similarly, `ADB
<https://en.wikipedia.org/wiki/Android_software_development#ADB>`_
cannot provide recovery mode support because it relies on the board
being booted into userspace and userspace must be configured to allow
access.

.. _bootloader_file_storage:

Problems with bootloader storage
********************************

It remains possible for any test job to corrupt any filesystem to which
the test job kernel has access. Boards which host the bootloader files
on a partition of the primary storage media are particularly vulnerable
to bricking through this method. Many U-Boot devices suffer from this
problem and LAVA uses TFTP on most of these devices to limit the number
of failures.

.. _full_system_images:

Problems with full system images
********************************

Some boards host the bootloader files on the same storage medium as the
kernel and/or operating system and then expect to write a full system
image to that storage. The best way to manage such boards is to use a
:term:`BMC`. If that is not available, ensure that the bootloader build
used in the system images is **never** changed until it has been
tested and the update has been approved by the lab admins. i.e. treat
the bootloader part of the system image build in exactly the same way
as a firmware or bootloader update on any other board which lacks
bootloader testing and recovery support.

It is not recommended to allow full system images to change more than
one component of the image in a single test job.

.. important:: A primary objective of CI and LAVA is to find breakages
   in places which developers did not expect to be present, whether
   those are new bugs or regressions. Every change in every element of
   the device and the entire software stack needs to be tested in
   isolation. Only change that one element at a time, keeping all other
   components identical to other test jobs. Every part of a board and
   every part of the software stack must be considered as untested and
   unreliable until proven otherwise.

   Not all testing needs to happen in LAVA or even in automation. Not
   all test operations can be supported in automation.

.. _hikey_6220_recovery:

HiKey 6220
**********

This board provides jumpers which can be bridged and connected to
relays to change the boot order when power is applied. Custom software
is needed to select recovery mode boot by setting the correct jumpers.
Once in recovery mode, the board offers a USB TTY device which can be
used to deploy the firmware using custom software from the
manufacturer. Once the firmware is transferred, the board comes up in
``fastboot`` mode and the rest of the boot files can be transferred
over the USB OTG port.

.. seealso:: :ref:`limits_of_hikey_6220` and
   :ref:`bootloader_recovery_criteria`

The HiKey 6220 uses a combined deployment of UEFI firmware and a
fastboot client which is then executed to deploy the boot and system
images.

If the firmware fails, the board can be switched back to recovery mode
without needing to interact with the device and a known working build
can be deployed instead (using a health check or a second deploy stage
of the test job itself). By using the control of the jumpers, the board
can be forced into recovery mode without any need to interact with the
bootloader.

An example test job for the hikey 6220 using recovery mode includes
three deploy actions: recovery, fastboot, and operating system
(OpenEmbedded or AOSP). This is to ensure that the firmware is tested
in a wide range of modes after being deployed. (Specifically, the test
ensures that the firmware continues to allow changes to the partition
tables without affecting serial numbers or other device behavior.)
This example is used as a health check, deploying a known good build of
the firmware, so can be used to recover from a broken build.

Recovery deployment
===================

.. literalinclude:: examples/test-jobs/hi6220-hikey-bl.yaml
     :language: yaml
     :linenos:
     :lines: 46-51
     :emphasize-lines: 4

AOSP deployment
===============

.. literalinclude:: examples/test-jobs/hi6220-hikey-bl.yaml
     :language: yaml
     :linenos:
     :lines: 92-96
     :emphasize-lines: 4

OpenEmbedded deployment
=======================

.. literalinclude:: examples/test-jobs/hi6220-hikey-bl.yaml
     :language: yaml
     :linenos:
     :lines: 145-151
     :emphasize-lines: 4

`Download / view complete hikey
<examples/test-jobs/hi6220-hikey-bl.yaml>`_ complete test job YAML.

.. _limits_of_hikey_6220:

Limits of HiKey 6220 recovery
=============================

There are limits on how the HiKey 6220 operates in recovery mode:

.. seealso:: :ref:`barriers_to_automated_recovery`

#. Requires external hardware (switchable USB hub, relays for the
   jumpers and custom serial hardware or cables.)

#. Transfers over a hardware USB TTY device which does not identify
   itself uniquely to the worker. Only one board can be attached to
   any one worker.

#. Fastboot method requires the use of :term:`LXC` or a custom
   :ref:`Docker image <lava_docker_images>`

   .. seealso:: :ref:`deploy_using_lxc`

#. There is no support for a recovery firmware image to be kept on the
   board alongside the test software. Admins need to identify a known
   working build which can be used in health checks.

#. At times, the firmware software itself has not supported a smooth
   rollback to previous versions. This takes the device offline as soon
   as a health check tries to deploy the previously known working
   version. Admins then need to establish a new known working version
   before bootloader testing can continue.

These limits mean that boards with the necessary jumper support must be
isolated from boards without jumper support. Despite the HiKey only
supporting UEFI and not U-Boot or another bootloader, the recovery mode
cannot be used for all test jobs due to these limits.

.. _juno_recovery:

Juno
****

The Juno board provides a :term:`BMC` which allows LAVA to deploy a new
build of bootloader without interacting with the current bootloader.
Juno also supports testing two different deployments, :ref:`U-Boot
<integrating_uboot>` bootloader and :ref:`UEFI <integrating_uefi>`
firmware.

The BMC is accessible before the bootloader is executed, so if the
test job determines that the bootloader has failed, a known working
build can be deployed to recover the board.

Recovery deployment
===================

.. literalinclude:: examples/test-jobs/juno-recovery.yaml
     :language: yaml
     :linenos:
     :lines: 33-37
     :emphasize-lines: 5

U-Boot boot action
==================

.. literalinclude:: examples/test-jobs/juno-recovery.yaml
     :language: yaml
     :linenos:
     :lines: 52-56
     :emphasize-lines: 4

`Download / view complete juno
<examples/test-jobs/juno-recovery.yaml>`_ test job YAML.

The Juno can support either U-Boot or UEFI. The BMC on Juno is
sufficiently reliable that all test jobs use recovery deployments to
ensure that the test job starts with a known bootloader. (Test jobs
would otherwise fail when sending U-Boot commands if the previous test
job deployed UEFI firmware and vice versa.)

X15 GPEVM
*********

Most of the TI boards provide means to load bootloader using
serial interface. This is the case for X15 GPEVM. As compared to
other X15 family boards, GPEVM is wired to provide jumpers to switch
boot mode. The only HW modification required is populating J5 in order
to avoid board powering down before bootloader is loaded to memory and
started.

In order to start board in recovery mode, the following HW settings
should be set:

#. Jumpers J3, J4 and J6 should have 1-2 link closed

#. Jumper J5 should be populated and closed

Example LAVA recovery test job loads 'known good' u-boot to memory and
follows with flashing the same u-boot to eMMC. This means that host has
to have the board connected as USB slave. Example LAVA settings assume that
all jumpers are controlled with relay.

Recovery deployment
===================

.. literalinclude:: examples/test-jobs/x15-recovery.yaml
     :language: yaml
     :linenos:
     :lines: 39-44
     :emphasize-lines: 4

OpenEmbedded deployment
=======================

.. literalinclude:: examples/test-jobs/x15-recovery.yaml
     :language: yaml
     :linenos:
     :lines: 80-85
     :emphasize-lines: 4

`Download / view complete x15
<examples/test-jobs/x15-recovery.yaml>`_ complete test job YAML.

