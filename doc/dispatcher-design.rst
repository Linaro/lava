.. _dispatcher_design:

Lava Dispatcher Design
**********************

The new dispatcher design is intended to make it easier to adapt the
dispatcher flow to new boards, new mechanisms and new deployments.

.. note:: The new code is still developing, some areas are absent,
          some areas will change substantially before it will work.
          All details here need to be seen only as examples and the
          specific code may well change independently.

Start with a Job which is broken up into a Deployment, a Boot, a Test
and a Submit class:

+-------------+--------------------+------------------+-------------------+
|     Job     |                    |                  |                   |
+=============+====================+==================+===================+
|             |     Deployment     |                  |                   |
+-------------+--------------------+------------------+-------------------+
|             |                    |   DeployAction   |                   |
+-------------+--------------------+------------------+-------------------+
|             |                    |                  |  DownloadAction   |
+-------------+--------------------+------------------+-------------------+
|             |                    |                  |  ChecksumAction   |
+-------------+--------------------+------------------+-------------------+
|             |                    |                  |  MountAction      |
+-------------+--------------------+------------------+-------------------+
|             |                    |                  |  CustomiseAction  |
+-------------+--------------------+------------------+-------------------+
|             |                    |                  |  TestDefAction    |
+-------------+--------------------+------------------+-------------------+
|             |                    |                  |  UnmountAction    |
+-------------+--------------------+------------------+-------------------+
|             |                    |   BootAction     |                   |
+-------------+--------------------+------------------+-------------------+
|             |                    |   TestAction     |                   |
+-------------+--------------------+------------------+-------------------+
|             |                    |   SubmitAction   |                   |
+-------------+--------------------+------------------+-------------------+

The Job manages the Actions using a Pipeline structure. Actions
can specialise actions by using internal pipelines and an Action
can include support for retries and other logical functions:

+------------------------+----------------------------+
|     DownloadAction     |                            |
+========================+============================+
|                        |    HttpDownloadAction      |
+------------------------+----------------------------+
|                        |    FileDownloadAction      |
+------------------------+----------------------------+

If a Job includes one or more Test definitions, the Deployment can then
extend the Deployment to overlay the LAVA test scripts without needing
to mount the image twice:

+----------------------+------------------+---------------------------+
|     DeployAction     |                  |                           |
+======================+==================+===========================+
|                      |   OverlayAction  |                           |
+----------------------+------------------+---------------------------+
|                      |                  |   MultinodeOverlayAction  |
+----------------------+------------------+---------------------------+
|                      |                  |   LMPOverlayAction        |
+----------------------+------------------+---------------------------+

The TestDefinitionAction has a similar structure with specialist tasks
being handed off to cope with particular tools:

+--------------------------------+-----------------+-------------------+
|     TestDefinitionAction       |                 |                   |
+================================+=================+===================+
|                                |    RepoAction   |                   |
+--------------------------------+-----------------+-------------------+
|                                |                 |   GitRepoAction   |
+--------------------------------+-----------------+-------------------+
|                                |                 |   BzrRepoAction   |
+--------------------------------+-----------------+-------------------+
|                                |                 |   TarRepoAction   |
+--------------------------------+-----------------+-------------------+
|                                |                 |   UrlRepoAction   |
+--------------------------------+-----------------+-------------------+

.. _code_flow:

Following the code flow
=======================

+------------------------------------------+-------------------------------------------------+
|                Filename                  |   Role                                          |
+==========================================+=================================================+
| lava/dispatcher/commands.py              | Command line arguments, call to YAML parser     |
+------------------------------------------+-------------------------------------------------+
| lava_dispatcher/pipeline/device.py       | YAML Parser to create the Device object         |
+------------------------------------------+-------------------------------------------------+
| lava_dispatcher/pipeline/parser.py       | YAML Parser to create the Job object            |
+------------------------------------------+-------------------------------------------------+
| ....pipeline/actions/deploy/             | Handlers for different deployment strategies    |
+------------------------------------------+-------------------------------------------------+
| ....pipeline/actions/boot/               | Handlers for different boot strategies          |
+------------------------------------------+-------------------------------------------------+
| ....pipeline/actions/test/               | Handlers for different LavaTestShell strategies |
+------------------------------------------+-------------------------------------------------+
| ....pipeline/actions/deploy/image.py     | DeployImage strategy creates DeployImageAction  |
+------------------------------------------+-------------------------------------------------+
| ....pipeline/actions/deploy/image.py     | DeployImageAction.populate adds deployment      |
|                                          | actions to the Job pipeline                     |
+------------------------------------------+-------------------------------------------------+
|   ***repeat for each strategy***         | each ``populate`` function adds more Actions    |
+------------------------------------------+-------------------------------------------------+
| ....pipeline/action.py                   | ``Pipeline.run_actions()`` to start             |
+------------------------------------------+-------------------------------------------------+

The deployment is determined from the device_type specified in the Job
(or the device_type of the specified target) by reading the list of
support methods from the device_types YAML configuration.

Each Action can define an internal pipeline and add sub-actions in the
``Action.populate`` function.

Particular Logic Actions (like RetryAction) require an internal pipeline
so that all actions added to that pipeline can be retried in the same
order. (Remember that actions must be idempotent.) Actions which fail
with a JobError or InfrastructureError can trigger Diagnostic actions.
See :ref:`retry_diagnostic`.

.. code-block:: yaml

 actions:
   deploy:
     allow:
       - image
   boot:
     allow:
       - image

This then matches the python class structure::

 actions/
    deploy/
        image.py

The class defines the list of Action classes needed to implement this
deployment. See also :ref:`dispatcher_actions`.

Pipeline construction and flow
==============================

#. One device per job. One top level pipeline per job

   * loads only the configuration required for this one job.

#. A NewDevice is built from the target specified (commands.py)
#. A Job is generated from the YAML by the parser.
#. The top level Pipeline is constructed by the parser.
#. Strategy classes are initialised by the parser

   #. Strategy classes add the top level Action for that strategy to the
      top level pipeline.
   #. Top level pipeline calls ``populate()`` on each top level Action added.

      #. Each ``Action.populate()`` function may construct one internal
         pipeline, based on parameters.
      #. internal pipelines call ``populate()`` on each Action added.

#. Parser iterates over each Strategy
#. Parser adds the FinalizeAction to the top-level pipeline
#. Loghandlers are set up
#. Job validates the completed pipeline

   #. Dynamic data can be added to the context

#. If ``--validate`` not specified, the job runs.

   #. Each ``run()`` function can add dynamic data to the context and/or
      results to the pipeline.
   #. Pipeline iterates through actions

#. Job ends, check for errors
#. Completed pipeline is available.

Using strategy classes
----------------------

Strategies are ways of meeting the requirements of the submitted job within
the limits of available devices and code support.

If an internal pipeline would need to allow for optional actions, those
actions still need to be idempotent. Therefore, the pipeline can include
all actions, with each action being responsible for checking whether
anything actually needs to be done. The populate function should avoid
using conditionals. An explicit select function can be used instead.

Whenever there is a need for a particular job to use a different Action
based solely on job parameters or device configuration, that decision
should occur in the Strategy selection using classmethod support.

Where a class is used in lots of different strategies, identify whether
there is a match between particular strategies always needing particular
options within the class. At this point, the class can be split and
particular strategies use a specialised class implementing the optional
behaviour and calling down to the base class for the rest.

If there is no clear match, for example in ``testdef.py`` where any
particular job could use a different VCS or URL without actually being
a different strategy, a select function is preferable. A select handler
allows the pipeline to contain only classes supporting git repositories
when only git repositories are in use for that job.

This results in more classes but a cleaner (and more predictable)
pipeline construction.

Lava test shell scripts
=======================

.. note:: See :ref:`criteria` - it is a mistake to think of the LAVA
          test support scripts as an *overlay* - the scripts are an
          **extension** to the test. Wherever possible, current
          deployments are being changed to supply the extensions
          alongside the deployment instead of overlaying, and thereby
          altering, the deployment.

The LAVA scripts a standard addition to a LAVA test and are handled as
a single unit. Using idempotent actions, the test script extension can
support LMP or MultiNode or other custom requirements without requiring
this support to be added to all tests. The extensions are created during
the deploy strategy and specific deployments can override the
``ApplyExtensionAction`` to unpack the extension tarball alongside the
test during the deployment phase and then mount the extension inside the
image. The tarball itself remains in the output directory and becomes
part of the test records. The checksum of the overlay is added to the
test job log.

Pipeline error handling
=======================

Runtime errors include:

#. Parser fails to handle device configuration
#. Parser fails to handle submission YAML
#. Parser fails to locate a Strategy class for the Job.
#. Code errors in Action classes cause Pipeline to fail.
#. Errors in YAML cause errors upon pipeline validation.

Each runtime error is a bug in the code - wherever possible, implement
a unit test to prevent regressions.

Job errors include:

#. Failed to find the specified URL.
#. Failed in an operation to create the necessary extensions.

Test errors include:

#. Failed to handle a signal generated by the device
#. Failed to parse a test case

.. _criteria:

Refactoring review criteria
===========================

The refactored dispatcher has different objectives to the original and
any assumptions in the old code must be thrown out. It is very easy to
fall into the old way of writing dispatcher code, so these criteria are
to help developers control the development of new code. Any of these
criteria can be cited in a code review as reasons for a review to be
improved.

.. _keep_dispatcher_dumb:

Keep the dispatcher dumb
------------------------

There is a temptation to make the dispatcher clever but this only
restricts the test writer from doing their own clever tests by hard
coding commands into the dispatcher codebase. If the dispatcher needs
some information about the test image, that information **must** be
retrieved from the job submission parameters, **not** by calculating
in the dispatcher or running commands inside the test image. Exceptions
to this are the metrics already calculated during download, like file
size and checksums. Any information about the test image which is
permanent within that image, e.g. the partition UUID strings or the
network interface list, can be identified by the process creating that
image or by a script which is run before the image is compressed and
made available for testing. If a test uses a tarball instead of an image,
the test **must** be explicit about the filesystem to use when
unpacking that tarball for use in the test as well as the size and
location of the partition to use.

LAVA will need to implement some safeguards for tests which still need
to deploy any test data to the media hosting the bootloader (e.g. fastboot,
SD card or UEFI) in order to avoid overwriting the bootloader itself.
Therefore, although SD card partitions remain available for LAVA tests
where no other media are supportable by the device, those tests can
**only** use tarballs and pre-defined partitions on the SD card. The
filesystem to use on those partitions needs to be specified by the test
writer.

.. _defaults:

Avoid defaults in dispatcher code
---------------------------------

Constants and defaults are going to need an override somewhere for some
device or test, eventually. Code defensively and put constants into
the utilities module to support modification. Put defaults into the
YAML, not the python code. It is better to have an extra line in the
device_type than a string in the python code as this can later be
extended to a device or a job submission.

Let the test fail and diagnose later
------------------------------------

**Avoid guessing** in LAVA code. If any operation in the dispatcher
could go in multiple paths, those paths must be made explicit to the
test writer. Report the available data, proceed according to the job
definition and diagnose the state of the device afterwards, where
appropriate.

**Avoid trying to be helpful in the test image**. Anticipating an error
and trying to code around it is a mistake. Possible solutions include
but are not limited to:

* Provide an optional, idempotent, class which only acts if a specific
  option is passed in the job definition. e.g. AutoLoginAction.
* Provide a diagnostic class which triggers if the expected problem
  arises. Report on the actual device state and document how to improve
  the job submission to avoid the problem in future.
* Split the deployment strategy to explicitly code for each possible
  path.

AutoLogin is a good example of the problem here. For too long, LAVA has
made assumptions about the incoming image, requiring hacks like
``linaro-overlay`` packages to be added to basic bootstrap images or
disabling passwords for the root user. These *helpful* steps act to
make it harder to use unchanged third party images in LAVA tests.
AutoLogin is the *de facto* default for non-Linaro images.

Another example is the assumption in various parts of LAVA that the
test image will raise a network interface and repeatedly calling ``ping``
on the assumption that the interface will appear, somehow, eventually.

.. _black_box_deploy:

Treat the deployment as a black box
-----------------------------------

LAVA has claimed to do this for a long time but the refactored
dispatcher is pushing this further. Do not think of the LAVA scripts
as an *overlay*, the LAVA scripts are **extensions**. When a test wants
an image deployed, the LAVA extensions should be deployed alongside the
image and then mounted to create a ``/lava-$hostname/`` directory. Images
for testing within LAVA are no longer broken up or redeployed but **must**
be deployed **intact**. This avoids LAVA needing to know anything about
issues like SELinux or specific filesystems but may involve multiple
images for systems like Android where data may exist on different physical
devices.

.. _essential_components:

Only protect the essential components
-------------------------------------

LAVA has had a tendency to hardcode commands and operations and there
are critical areas which must still be protected from changes in the
test but these critical areas are restricted to:

#. The dispatcher.
#. Unbricking devices.

**Any** process which has to run on the dispatcher itself **must** be
fully protected from mistakes within tests. This means that **all**
commands to be executed by the dispatcher are hardcoded into the dispatcher
python code with only limited support for overriding parameters or
specifying *tainted* user data.

Tests are prevented from requiring new software to be installed on any
dispatcher which is not already a dependency of ``lava-dispatcher``.
Issues arising from this need to be resolved using MultiNode.

Until such time as there is a general and reliable method of deploying
and testing new bootloaders within LAVA tests, the bootloader / firmware
installed by the lab admin is deemed sacrosanct and must not be altered
or replaced in a test job. However, bootloaders are generally resilient
to errors in the commands, so the commands given to the bootloader remain
accessible to test writers.

It is not practical to scan all test definitions for potentially harmful
commands. If a test inadvertently corrupts the SD card in such a way that
the bootloader is corrupted, that is an issue for the lab admins to
take up with the test submitter.

Give the test writer enough rope
--------------------------------

Within the provisos of :ref:`essential_components`, the test writer
needs to be given enough rope and then let LAVA **diagnose** issues
after the event.

There is no reason to restrict the test writer to using LAVA commands
inside the test image - as long as the essential components remain
protected.

Examples:

#. KVM devices need to protect the QEMU command line because these
   commands run on the dispatcher
#. VM devices running on an arndale do **not** need the command line
   to be coded within LAVA. There have already been bug reports on this
   issue.

:ref:`diagnostic_actions` report on the state of the device after some
kind of error. This reporting can include:

* The presence or absence of expected files (like ``/dev/disk/by-id/``
  or ``/proc/net/pnp``).
* Data about running processes or interfaces, e.g. ``ifconfig``

It is a mistake to attempt to calculate data about a test image - instead,
require that the information is provided and **diagnose** the actual
information if the attempt to use the specified information fails.

Guidance
^^^^^^^^

#. If the command is to run inside a deployment, **require** that the
   **full** command line can be specified by the test writer. Remember:
   :ref:`defaults`. It is recommended to have default commands where
   appropriate but these defaults need to support overrides in the job
   submission. This includes using a locally built binary instead of an
   executable installed in ``/usr/bin`` or similar.
#. If the command is run on a dispatcher, **require** that the binary
   to be run on the dispatcher is actually installed on the dispatcher.
   If ``/usr/bin/git`` does not exist, this is a validation error. There
   should be no circumstances where a tool required on the dispatcher
   cannot be identified during validation of the pipeline.
#. An error from running the command on the dispatcher with user-specified
   parameters is a JobError.
#. Where it is safe to do so, offer **overrides** for supportable
   commandline options.

The codebase itself will help identify how much control is handed over
to the test writer. ``self.run_command()`` is a dispatcher call and
needs to be protected. ``connection.sendline()`` is a deployment
call and does not need to be protected.

Providing gold standard images
------------------------------

Test writers are strongly recommended to only use a known working
setup for their job. A set of gold standard jobs will be defined in
association with the QA team. These jobs will provide a known baseline
for test definition writers, in a similar manner as the existing QA test
definitions provide a base for more elaborate testing.

There will be a series of images provided for as many device types as
practical, covering the basic deployments. Test definitions will be
required to be run against these images before the LAVA team will spend
time investigating bugs arising from tests. These images will provide a
measure of reassurance around the following issues:

* Kernel fails to load NFS or ramdisk.
* Kernel panics when asked to use secondary media.
* Image containing a different kernel to the gold standard fails
  to deploy.

.. note:: It is imperative that test writers understand that a gold
          standard deployment for one device type is not necessarily
          supported for a second device type. Some devices will
          never be able to support all deployment methods due to
          hardware constraints or the lack of kernel support. This is
          **not** a bug in LAVA.
          If a particular deployment is supported but not stable on a
          device type, there will not be a gold standard image for that
          deployment. Any issues in the images using such deployments
          on that type are entirely down to the test writer to fix.

The refactoring will provide :ref:`diagnostic_actions` which point at
these issues and recommend that the test is retried using the standard
kernel, dtb, initramfs, rootfs and other components.

The reason to give developers enough rope is precisely so that kernel
developers are able to fix issues in the test images before problems
show up in the gold standard images. Test writers need to work with the
QA team, using the gold standard images.

Secondary media
===============

With the migration from master images on an SD card to dynamic master
images over NFS, other possibilities arise from the refactoring.

* Deploy a ramdisk, boot and deploy an entire image to a USB key, boot
  and direct bootloader at USB filesystem, including kernel and initrd.
* Deploy an NFS system, boot and bootstrap an image to SATA, boot and
  direct bootloader at SATA filesystem, including kernel and initrd.
* Deploy using a script written by the test author (e.g. debootstrap)
  which is installed in the initial deployment. Parameters for the
  script need to be contained within the test image.

By keeping the downloaded image intact, it becomes possible to put the
LAVA extensions alongside the image instead of inside.

To make this work, several requirements must be met:

* The initial deployment must provide or support installation of all
  tools necessary to complete the second deployment - it is a TestError
  if there is insufficient space or the deployment cannot complete
  this step.
* The operation of the second deployment is a test shell which
  **precedes** the second boot. There is no provision for getting
  data back from this test shell into the boot arguments for the next
  boot. Any data which is genuinely persistent needs to be specified
  in advance.
* LAVA will need to support instructions in the job definition which
  determine whether a failed test shell should allow or skip the
  boot action following.
* LAVA will declare available media using the **kernel interface** as
  the label. A SATA drive which can only be attached to devices of a
  particular :term:`device type` using USB is still a USB device as it
  is constrained by the USB interface being present in the test image
  kernel. A SATA drive attached to a SATA connector on the board is a
  SATA device in LAVA (irrespective of how the board actually delivers
  the SATA interface on that connector).
* If a device has multiple media of the same type, it is up to the test
  writer to determine how to ensure that the correct image is booted.
  The ``blkid`` of a partition within an image is a permanent UUID within
  that image and needs to be determined in advance if this is to be used
  in arguments to the bootloader as the root filesystem.
* The manufacturer ID and serial number of the hardware to be used for
  the secondary deployment must be set in the device configuration. This
  makes it possible for test images to use such support as is available
  (e.g. ``udev``) to boot the correct device.
* The job definition needs to specify which hardware to use for the
  second deployment - if this label is based on a device node, it is a
  TestError if the use of this label does not result in a successful
  boot.
* The job definition also needs to specify the path to the kernel, dtb
  and the partition containing the rootfs within the deployed image.
* The job definition needs to include the bootloader commands, although
  defaults can be provided in some cases.

UUID vs device node support
---------------------------

A deployment to secondary media must be done by a running kernel, not
by the bootloader, so restrictions apply to that kernel:

#. Device types with more than one media device sharing the same device
   interface must be identifiable in the device_type configuration.
   These would be devices where, if all slots were populated, a full
   udev kernel would find explicitly more than one ``/dev/sd*`` top
   level device. It does not matter if these are physically different
   types of device (cubietruck has usb and sata) or the same type
   (d01 has three sata). The device_type declares the flag:
   ``UUID-required: True`` for each relevant interface. For cubietruck::

    media:  # two USB slots, one SATA connector
      usb:
        UUID-required: True
      sata:
        UUID-required: False

#. It is important to remember that there are five different identifiers
   involved across the device configuration and job submission:

   #. The ID of the device as it appears to the kernel running the deploy,
      provided by the device configuration: ``uuid``. This is found in
      ``/dev/disk/by-id/`` on a booted system.
   #. The ID of the device as it appears to the bootloader when reading
      deployed files into memory, provided by the device configuration:
      ``device_id``. This can be confirmed by interrupting the bootloader
      and listing the filesystem contents on the specified interface.
   #. The ID of the partition to specify as ``root`` on the kernel
      command line of the deployed kernel when booting the kernel inside
      the image, set by the job submission ``root_uuid``. Must be specified
      if the device has UUID-required set to True.
   #. The ``boot_part`` specified in the job submission which is the
      partition number inside the deployed image where the files can be
      found for the bootloader to execute. Files in this partition will
      be accessed directly through the bootloader, not via any mountpoint
      specified inside the image.
   #. The ``root_part`` specified in the job submission which is the
      partition number inside the deployed image where the root filesystem
      files can be found by the depoyed kernel, once booted. ``root_part``
      cannot be used with ``root_uuid`` - to do so causes a JobError.

Device configuration
^^^^^^^^^^^^^^^^^^^^

Media settings are per-device, based on the capability of the device type.
An individual devices of a specified type *may* have exactly one of the
available slots populated on any one interface. These individual devices
would set UUID-required: False for that interface. e.g. A panda has two
USB host slots. For each panda, if both slots are occupied, specify
``UUID-required: True`` in the device configuration. If only one is
occupied, specify ``UUID-required: False``. If none are occupied, comment
out or remove the entire ``usb`` interface section in the configuration
for that one device. List each specific device which is available as
media on that interface using a humand-usable string, e.g. a Sandisk
Ultra usb stick with a UUID of ``usb-SanDisk_Ultra_20060775320F43006019-0:0``
could simply be called ``SanDisk_Ultra``. Ensure that this label is
unique for each device on the same interface. Jobs will specify this label
in order to look up the actual UUID, allowing physical media to be
replaced with an equivalent device without changing the job submission data.

The device configuration should always include the UUID for all media on
each supported interface, even if ``UUID-required`` is False. The UUID is
the recommended way to specify the media, even when not strictly required.
Record the symlink name (without the path) for the top level device in
``/dev/disk/by-id/`` for the media concerned, i.e. the symlink pointing
at ``../sda`` not the symlink(s) pointing at individual partitions. The
UUID should be **quoted** to ensure that the YAML can be parsed correctly.
Also include the ``device_id`` which is the bootloader view of the same
device on this interface.

.. code-block:: yaml

 device_type: cubietruck
 commands:
  connect: telnet localhost 6000
 media:
   usb:  # bootloader interface name
     UUID-required: True  # cubie1 is pretending to have two usb media attached
     SanDisk_Ultra:
       uuid: "usb-SanDisk_Ultra_20060775320F43006019-0:0"  # /dev/disk/by-id/
       device_id: 0  # the bootloader device id for this media on the 'usb' interface

There is no reasonable way for the device configuration to specify the
device node as it may depend on how the deployed kernel or image is configured.
When this is used, the job submission must contain this data.

Deploy commands
"""""""""""""""

This is an example block - the actual data values here are known not to
work as the ``deploy`` step is for a panda but the ``boot`` step in the
next example comes from a working cubietruck job.

This example uses a device configuration where ``UUID-required`` is True.

For simplicity, this example also omits the initial deployment and boot,
at the start of this block, the device is already running a kernel with
a ramdisk or rootfs which provides enough support to complete this second
deployment.

.. code-block:: yaml

    # secondary media - use the first deploy to get to a system which can deploy the next
    # in testing, assumed to already be deployed
    - deploy:
        timeout:
          minutes: 10
        to: usb
        os: debian
        # not a real job, just used for unit tests
        compression: gz
        image: http://releases.linaro.org/12.02/ubuntu/leb-panda/panda-ubuntu-desktop.img.gz
        device: SanDisk_Ultra # needs to be exposed in the device-specific UI
        download: /usr/bin/wget


#. Ensure that the ``deploy`` action has sufficient time to download the
   **decompressed** image **and** write that image directly to the media
   using STDOUT. In the example, the deploy timeout has been set to ten
   minutes - in a test on the panda, the actual time required to write
   the specified image to a USB device was around 6 minutes.
#. Note the deployment strategy - ``to: usb``. This is a direct mapping
   to the kernel interface used to deploy and boot this image. The
   bootloader must also support reading files over this interface.
#. The compression method used by the specified image is explicitly set.
#. The image is downloaded and decompressed by the dispatcher, then made
   available to the device to retrieve and write to the specified media.
#. The device is specified as a label so that the correct UUID can be
   constructed from the device configuration data.
#. The download tool is specified as a full path which must exist inside
   the currently deployed system. This tool will be used to retrieve the
   decompressed image from the dispatcher and pass STDOUT to ``dd``. If
   the download tool is the default ``/usr/bin/wget``, LAVA will add the
   following options:
   ``--no-check-certificate --no-proxy --connect-timeout=30 -S --progress=dot:giga -O -``
   If different download tools are required for particular images, these
   can be specified, however, if those tools require options, the writer
   can either ensure that a script exists in the image which wraps those
   options or file a bug to have the alternative tool options supported.

The kernel inside the initial deployment **MUST** support UUID when
deployed on a device where UUID is required, as it is this kernel which
needs to make ``/dev/disk/by-id/$path`` exist for ``dd`` to use.

Boot commands
"""""""""""""

.. code-block:: yaml

    - boot:
        method: u-boot
        commands: usb
        parameters:
          shutdown-message: "reboot: Restarting system"
        # these files are part of the image already deployed and are known to the test writer
        kernel: /boot/vmlinuz-3.16.0-4-armmp-lpae
        ramdisk: /boot/initrd.img-3.16.0-4-armmp-lpae.u-boot
        dtb: /boot/dtb-3.16.0-4-armmp-lpae'
        root_uuid: UUID=159d17cc-697c-4125-95a0-a3775e1deabe  # comes from the supplied image.
        boot_part: 1  # the partition on the media from which the bootloader can read the kernel, ramdisk & dtb
        type: bootz

The ``kernel`` and (if specified) the ``ramdisk`` and ``dtb`` paths are
the paths used by the bootloader to load the files in order to boot the
image deployed onto the secondary media. These are **not necessarily**
the same as the paths to the same files as they would appear inside the
image after booting, depending on whether any boot partition is mounted
at a particular mountpoint.

The ``root_uuid`` is the full option for the ``root=`` command to the
kernel, including the ``UUID=`` prefix.

The ``boot_part`` is the number of the partition from which the bootloader
can read the files to boot the image. This will be combined with the
device configuration interface name and device_id to create the command
to the bootloader, e.g.::

 "setenv loadfdt 'load usb 0:1 ${fdt_addr_r} /boot/dtb-3.16.0-4-armmp-lpae''",

The dispatcher does NOT analyze the incoming image - internal UUIDs
inside an image do not change as the refactored dispatcher does **not**
break up or relay the partitions. Therefore, the UUIDs of partitions inside
the image **MUST** be declared by the job submissions.

Secondary connections
=====================

The implementation of VMGroups created a role for a delayed start
Multinode job. This would allow one job to operate over serial, publish
the IP address, start an SSH server and signal the second job that a
connection is ready to be established. This may be useful for situations
where a debugging shell needs to be opened around a virtualisation
boundary.

Device configuration design
===========================

Device configuration has moved to YAML and has a larger scope of possible
methods, related to the pipeline strategies.

Changes from existing configuration
-----------------------------------

The device configuration is moving off the dispatcher and into the main
LAVA server database. This simplifies the scheduler and is a step
towards a dumb dispatcher model where the dispatcher receives all device
configuration along with the job instead of deciding which jobs to run
based on local configuration. There is then no need for the device
configuration to include the hostname in the YAML as there is nothing
on the dispatcher to check against - the dispatcher uses the command
line arguments.

Example device configuration
----------------------------

.. code-block:: yaml

 device_type: beaglebone-black
 commands:
   connect: telnet localhost 6000
   hard_reset: /usr/bin/pduclient --daemon localhost --hostname pdu --command reboot --port 08
   power_off: /usr/bin/pduclient --daemon localhost --hostname pdu --command off --port 08
   power_on: /usr/bin/pduclient --daemon localhost --hostname pdu --command on --port 08

Example device_type configuration
---------------------------------

.. code-block:: yaml

 # replacement device_type config for the beaglebone-black type

 parameters:
  bootm:
   kernel: '0x80200000'
   ramdisk: '0x81600000'
   dtb: '0x815f0000'
  bootz:
   kernel: '0x81000000'
   ramdisk: '0x82000000'
   dtb: '0x81f00000'

 actions:
  deploy:
    # list of deployment methods which this device supports
    methods:
      # - image # not ready yet
      - tftp

  boot:
    # list of boot methods which this device supports.
    methods:
      - u-boot:
          parameters:
            bootloader_prompt: U-Boot
            boot_message: Booting Linux
            send_char: False
            # interrupt: # character needed to interrupt u-boot, single whitespace by default
          # method specific stanza
          oe:
            commands:
            - setenv initrd_high '0xffffffff'
            - setenv fdt_high '0xffffffff'
            - setenv bootcmd 'fatload mmc 0:3 0x80200000 uImage; fatload mmc 0:3 0x815f0000 board.dtb;
              bootm 0x80200000 - 0x815f0000'
            - setenv bootargs 'console=ttyO0,115200n8 root=/dev/mmcblk0p5 rootwait ro'
            - boot
          nfs:
            commands:
            - setenv autoload no
            - setenv initrd_high '0xffffffff'
            - setenv fdt_high '0xffffffff'
            - setenv kernel_addr_r '{KERNEL_ADDR}'
            - setenv initrd_addr_r '{RAMDISK_ADDR}'
            - setenv fdt_addr_r '{DTB_ADDR}'
            - setenv loadkernel 'tftp ${kernel_addr_r} {KERNEL}'
            - setenv loadinitrd 'tftp ${initrd_addr_r} {RAMDISK}; setenv initrd_size ${filesize}'
            - setenv loadfdt 'tftp ${fdt_addr_r} {DTB}'
            # this could be a pycharm bug or a YAML problem with colons. Use &#58; for now.
            # alternatively, construct the nfsroot argument from values.
            - setenv nfsargs 'setenv bootargs console=ttyO0,115200n8 root=/dev/nfs rw nfsroot={SERVER_IP}&#58;{NFSROOTFS},tcp,hard,intr ip=dhcp'
            - setenv bootcmd 'dhcp; setenv serverip {SERVER_IP}; run loadkernel; run loadinitrd; run loadfdt; run nfsargs; {BOOTX}'
            - boot
          ramdisk:
            commands:
            - setenv autoload no
            - setenv initrd_high '0xffffffff'
            - setenv fdt_high '0xffffffff'
            - setenv kernel_addr_r '{KERNEL_ADDR}'
            - setenv initrd_addr_r '{RAMDISK_ADDR}'
            - setenv fdt_addr_r '{DTB_ADDR}'
            - setenv loadkernel 'tftp ${kernel_addr_r} {KERNEL}'
            - setenv loadinitrd 'tftp ${initrd_addr_r} {RAMDISK}; setenv initrd_size ${filesize}'
            - setenv loadfdt 'tftp ${fdt_addr_r} {DTB}'
            - setenv bootargs 'console=ttyO0,115200n8 root=/dev/ram0 ip=dhcp'
            - setenv bootcmd 'dhcp; setenv serverip {SERVER_IP}; run loadkernel; run loadinitrd; run loadfdt; {BOOTX}'
            - boot


Testing the new design
======================

To test the new design, use the increasing number of unit tests::

 $ python -m unittest discover lava_dispatcher/pipeline/

To run a single test, use the test class name as output by a failing test,
without the call to ``discover``::

 $ python -m unittest lava_dispatcher.pipeline.test.test_job.TestKVMBasicDeploy.test_kvm_basic_test

 $ python -m unittest -v -c -f lava_dispatcher.pipeline.test.test_job.TestKVMBasicDeploy.test_kvm_basic_test

Also, install the updated ``lava-dispatcher`` package and use it to
inspect the output of the pipeline using the ``--validate`` switch to
``lava-dispatch``::

 $ sudo lava-dispatch --validate --target kvm01 lava_dispatcher/pipeline/test/sample_jobs/kvm.yaml --output-dir=/tmp/test

The structure of any one job will be the same each time it is run (subject
to changes in the developing codebase). Each different job will have a
different pipeline structure. Do not rely on any of the pipeline levels
have any specific labels. When writing unit tests, only use checks based
on ``isinstance`` or ``self.name``. (The description and summary fields
are subject to change to make the validation output easier to understand
whereas ``self.name`` is a strict class-based label.)

Sample pipeline description output
----------------------------------

(Actual output is subject to frequent change.)

.. code-block:: yaml

 !!python/object/apply:collections.OrderedDict
 - - - device
    - parameters:
        actions:
          boot:
            command:
              amd64: {qemu_binary: qemu-system-x86_64}
            methods: [qemu]
            overrides: [boot_cmds, qemu_options]
            parameters:
              boot_cmds:
              - {root: /dev/sda1}
              - {console: 'ttyS0,115200'}
              machine: accel=kvm:tcg
              net: ['nic,model=virtio', user]
              qemu_options: [-nographic]
          deploy:
            methods: [image]
        architecture: amd64
        device_type: kvm
        hostname: kvm01
        memory: 512
        root_part: 1
        test_image_prompts: [\(initramfs\), linaro-test, '/ #', root@android, root@linaro,
          root@master, root@debian, 'root@linaro-nano:~#', 'root@linaro-developer:~#',
          'root@linaro-server:~#', 'root@genericarmv7a:~#', 'root@genericarmv8:~#']
  - - job
    - parameters: {action_timeout: 5m, device_type: kvm, job_name: kvm-pipeline, job_timeout: 15m,
        output_dir: /tmp/codehelp, priority: medium, target: kvm01, yaml_line: 3}
  - - '1'
    - content:
        description: deploy image using loopback mounts
        level: '1'
        name: deployimage
        parameters:
          deployment_data: &id001 {TESTER_PS1: 'linaro-test [rc=$(echo \$?)]# ', TESTER_PS1_INCLUDES_RC: true,
            TESTER_PS1_PATTERN: 'linaro-test \[rc=(\d+)\]# ', boot_cmds: boot_cmds,
            distro: debian, lava_test_dir: /lava-%s, lava_test_results_dir: /lava-%s,
            lava_test_results_part_attr: root_part, lava_test_sh_cmd: /bin/bash}
        summary: deploy image
        valid: true
        yaml_line: 12
      description: deploy image using loopback mounts
      summary: deploy image
  - - '1.1'
    - content:
        description: download with retry
        level: '1.1'
        max_retries: 5
        name: download_action
        parameters:
          deployment_data: *id001
        sleep: 1
        summary: download-retry
        valid: true
      description: download with retry
      summary: download-retry
  - - '1.2'
    - content:
        description: md5sum and sha256sum
        level: '1.2'
        name: checksum_action
        parameters:
          deployment_data: *id001
        summary: checksum
        valid: true
      description: md5sum and sha256sum
      summary: checksum
  - - '1.3'
    - content:
        description: mount with offset
        level: '1.3'
        name: mount_action
        parameters:
          deployment_data: *id001
        summary: mount loop
        valid: true
      description: mount with offset
      summary: mount loop
  - - 1.3.1
    - content:
        description: calculate offset of the image
        level: 1.3.1
        name: offset_action
        parameters:
          deployment_data: *id001
        summary: offset calculation
        valid: true
      description: calculate offset of the image
      summary: offset calculation
  - - 1.3.2
    - content:
        description: ensure a loop back mount operation is possible
        level: 1.3.2
        name: loop_check
        parameters:
          deployment_data: *id001
        summary: check available loop back support
        valid: true
      description: ensure a loop back mount operation is possible
      summary: check available loop back support
  - - 1.3.3
    - content:
        description: Mount using a loopback device and offset
        level: 1.3.3
        max_retries: 5
        name: loop_mount
        parameters:
          deployment_data: *id001
        retries: 10
        sleep: 10
        summary: loopback mount
        valid: true
      description: Mount using a loopback device and offset
      summary: loopback mount
  - - '1.4'
    - content:
        description: customise image during deployment
        level: '1.4'
        name: customise
        parameters:
          deployment_data: *id001
        summary: customise image
        valid: true
      description: customise image during deployment
      summary: customise image
  - - '1.5'
    - content:
        description: load test definitions into image
        level: '1.5'
        name: test-definition
        parameters:
          deployment_data: *id001
        summary: loading test definitions
        valid: true
      description: load test definitions into image
      summary: loading test definitions
  - - 1.5.1
    - content:
        description: apply git repository of tests to the test image
        level: 1.5.1
        max_retries: 5
        name: git-repo-action
        parameters:
          deployment_data: *id001
        sleep: 1
        summary: clone git test repo
        uuid: b32dd5ff-fb80-44df-90fb-5fbd5ab35fe5
        valid: true
        vcs_binary: /usr/bin/git
      description: apply git repository of tests to the test image
      summary: clone git test repo
  - - 1.5.2
    - content:
        description: apply git repository of tests to the test image
        level: 1.5.2
        max_retries: 5
        name: git-repo-action
        parameters:
          deployment_data: *id001
        sleep: 1
        summary: clone git test repo
        uuid: 200e83ef-bb74-429e-89c1-05a64a609213
        valid: true
        vcs_binary: /usr/bin/git
      description: apply git repository of tests to the test image
      summary: clone git test repo
  - - 1.5.3
    - content:
        description: overlay test support files onto image
        level: 1.5.3
        name: test-overlay
        parameters:
          deployment_data: *id001
        summary: applying LAVA test overlay
        valid: true
      description: overlay test support files onto image
      summary: applying LAVA test overlay
  - - '1.6'
    - content:
        default_fixupdict: {FAIL: fail, PASS: pass, SKIP: skip, UNKNOWN: unknown}
        default_pattern: (?P<test_case_id>.*-*)\s+:\s+(?P<result>(PASS|pass|FAIL|fail|SKIP|skip|UNKNOWN|unknown))
        description: add lava scripts during deployment for test shell use
        lava_test_dir: /usr/lib/python2.7/dist-packages/lava_dispatcher/lava_test_shell
        level: '1.6'
        name: lava-overlay
        parameters:
          deployment_data: *id001
        runner_dirs: [bin, tests, results]
        summary: overlay the lava support scripts
        valid: true
        xmod: 493
      description: add lava scripts during deployment for test shell use
      summary: overlay the lava support scripts
  - - '1.7'
    - content:
        description: unmount the test image at end of deployment
        level: '1.7'
        max_retries: 5
        name: umount
        parameters:
          deployment_data: *id001
        sleep: 1
        summary: unmount image
        valid: true
      description: unmount the test image at end of deployment
      summary: unmount image
  - - '2'
    - content:
        description: boot image using QEMU command line
        level: '2'
        name: boot_qemu_image
        parameters:
          parameters: {failure_retry: 2, media: tmpfs, method: kvm, yaml_line: 22}
        summary: boot QEMU image
        timeout: {duration: 30, name: boot_qemu_image}
        valid: true
        yaml_line: 22
      description: boot image using QEMU command line
      summary: boot QEMU image
  - - '2.1'
    - content:
        description: Wait for a shell
        level: '2.1'
        name: expect-shell-connection
        parameters:
          parameters: {failure_retry: 2, media: tmpfs, method: kvm, yaml_line: 22}
        summary: Expect a shell prompt
        valid: true
      description: Wait for a shell
      summary: Expect a shell prompt
  - - '3'
    - content:
        level: '3'
        name: test
        parameters:
          parameters:
            definitions:
            - {from: git, name: smoke-tests, path: ubuntu/smoke-tests-basic.yaml,
              repository: 'git://git.linaro.org/qa/test-definitions.git', yaml_line: 31}
            - {from: git, name: singlenode-basic, path: singlenode01.yaml, repository: 'git://git.linaro.org/people/neilwilliams/multinode-yaml.git',
              yaml_line: 39}
            failure_retry: 3
            name: kvm-basic-singlenode
            yaml_line: 27
        summary: test
        valid: true
      description: null
      summary: test
  - - '4'
    - content:
        level: '4'
        name: submit_results
        parameters:
          parameters: {stream: /anonymous/codehelp/, yaml_line: 44}
        summary: submit_results
        valid: true
      description: null
      summary: submit_results
  - - '5'
    - content:
        description: finish the process and cleanup
        level: '5'
        name: finalize
        parameters:
          parameters: {}
        summary: finalize the job
        valid: true
      description: finish the process and cleanup
      summary: finalize the job

Provisos with the current codebase
----------------------------------

The code can be executed::

 $ sudo lava-dispatch --target kvm01 lava_dispatcher/pipeline/test/sample_jobs/kvm.yaml --output-dir=/tmp/test

* There is a developer shortcut which uses ``/tmp/`` to store the downloaded
  image instead of a fresh ``mkdtemp`` each time. This saves re-downloading
  the same image but as the image is modified in place, a second run using
  the image will fail.

 * Either change the YAML locally to refer to a ``file://``
   URL and comment out the developer shortcut or copy a decompressed image
   over the modified one in ``tmp`` before each run.

* During development, there may also be images left mounted at the end of
  the run. Always check the output of ``mount``.
* Files in ``/tmp/test`` are not removed at the start or end of a job as
  these would eventually form part of the result bundle and would also be
  in a per-job temporary directory (created by the scheduler). To be certain
  of what logs were created by each run, clear the directory each time.

Compatibility with the old dispatcher LavaTestShell
===================================================

The hacks and workarounds in the old LavaTestShell classes may need to
be marked and retained until such time as either the new model replaces
the old or the bug can be fixed in both models. Whereas the submission
schema, log file structure and result bundle schema have thrown away any
backwards compatibility, LavaTestShell will need to at least attempt to
retain compatibility whilst improving the overall design and integrating
the test shell operations into the new classes.

Current possible issues include:

* ``testdef.yaml`` is hardcoded into ``lava-test-runner`` when this could
  be a parameter fed into the overlay from the VCS handlers.
* Dependent test definitions had special handling because certain YAML
  files had to be retained when the overlay was taken from the dispatcher
  and installed onto the device. This approach leads to long delays and
  the need to use wget on the device to apply the test definition overlay
  as a separate operation during LavaTestShell. The new classes should
  be capable of creating a complete overlay prior to the device being
  booted which allows for the entire VCS repo to be retained. This may
  change behaviour.

 * If dependent test definitions use custom signal handlers, this may
   not work - it would depend on how the job parameters are handled
   by the new classes.

.. _retry_diagnostic:

Retry actions and Diagnostics
=============================

RetryAction subclassing
-----------------------

For a RetryAction to validate, the RetryAction subclass must be a wrapper
class around a new internal_pipeline to allow the RetryAction.run()
function to handle all of the retry functionality in one place.

An Action which needs to support ``failure_retry`` or which wants to
use RetryAction support internally, needs a new class added which derives
from RetryAction, sets a useful name, summary and description and defines
a populate() function which creates the internal_pipeline. The Action
with the customised run() function then gets added to the internal_pipeline
of the RetryAction subclass - without changing the inheritance of the
original Action.

.. _diagnostic_actions:

Diagnostic subclasses
---------------------

To add Diagnostics, add subclasses of DiagnosticAction to the list of
supported Diagnostic classes in the Job class. Each subclass must define
a trigger classmethod which is unique across all Diagnostic subclasses.
(The trigger string is used as an index in a generator hash of classes.)
Trigger strings are only used inside the Diagnostic class. If an Action
catches a JobError or InfrastructureError exception and wants to
allow a specific Diagnostic class to run, import the relevant Diagnostic
subclass and add the trigger to the current job inside the exception
handling of the Action:

.. code-block:: python

 try:
   self._run_command(cmd_list)
 except JobError as exc:
   self.job.triggers.append(DiagnoseNetwork.trigger())
   raise JobError(exc)
 return connection

Actions should only append triggers which are relevant to the JobError or
InfrastructureError exception about to be raised inside an Action.run()
function. Multiple triggers can be appended to a single exception. The
exception itself is still raised (so that a RetryAction container will
still operate).

.. hint:: A DownloadAction which fails to download a file could
          append a DiagnosticAction class which runs ``ifconfig`` or
          ``route`` just before raising a JobError containing the
          404 message.

If the error to be diagnosed does not raise an exception, append the
trigger in a conditional block and emit a JobError or InfrastructureError
exception with a useful message.

Do not clear failed results of previous attempts when running a Diagnostic
class - the fact that a Diagnostic was required is an indication that the
job had some kind of problem.

Avoid overloading common Action classes with Diagnostics, add a new Action
subclass and change specific Strategy classes (Deployment, Boot, Test)
to use the new Action.

Avoid chaining Diagnostic classes - if a Diagnostic requires a command to
exist, it must check that the command does exist. Raise a RuntimeError if
a Strategy class leads to a Diagnostic failing to execute.

It is an error to add a Diagnostic class to any Pipeline. Pipeline Actions
should be restricted to classes which have an effect on the Test itself,
not simply reporting information.

.. _adjuvants:

Adjuvants - skipping actions and using helper actions
=====================================================

Sometimes, a particular test image will support the expected command
but a subsequent image would need an alternative. Generally, the expectation
is that the initial command should work, therefore the fallback or helper
action should not be needed. The refactoring offers support for this
situation using Adjuvants.

An Adjuvant is a helper action which exists in the normal pipeline but
which is normally skipped, unless the preceding Action sets a key in the
PipelineContext that the adjuvant is required. A successful operation of
the adjuvant clears the key in the context.

One example is the ``reboot`` command. Normal user expectation is that
a ``reboot`` command as root will successfully reboot the device but
LAVA needs to be sure that a reboot actually does occur, so usually
uses a hard reset PDU command after a timeout. The refactoring allows
LAVA to distinguish between a job where the soft reboot worked and a
job where the PDU command became necessary, without causing the test
itself to fail simply because the job didn't use a hard reset.

If the ResetDevice Action determines that a reboot happened (by matching
a pexpect on the bootloader initialisation), then nothing happens and the
Adjuvant action (in this case, HardResetDevice) is marked in the results
as skipped. If the soft reboot fails, the ResetDevice Action marks this
result as failed but also sets a key in the PipelineContext so that the
HardResetDevice action then executes.

Unlike Diagnostics, Adjuvants are an integral part of the pipeline and
show up in the verification output and the results, whether executed
or not. An Adjuvant is not a simple retry, it is a different action,
typically a more aggressive or forced action. In an ideal world, the
adjuvant would never be required.

A similar situation exists with firmware upgrades. In this case, the
adjuvant is skipped if the firmware does not need upgrading. The
preceding Action would not be set as a failure in this situation but
LAVA would still be able to identify which jobs updated the firmware
and which did not.

.. _connections_and_signals:

Connections, Actions and the SignalDirector
===========================================

Most deployment Action classes run without needing a Connection. Once a
Connection is established, the Action may need to run commands over that
Connection. At this point, the Action delegates the maintenance of
the run function to the Connection pexpect. i.e. the Action.run() is
blocked, waiting for Connection.run_command() (or similar) to return
and the Connection needs to handle timeouts, signals and other interaction
over the connection. This role is taken on by the internal SignalDirector
within each Connection. Unlike the old model, Connections have their
own directors which takes the multinode and LMP workload out of the
singlenode operations.

Using connections
-----------------

Construct your pipeline to use Actions in the order:

* Prepare any overlays or commands or context data required later
* Start a new connection
* Issue the command which changes device state
* Wait for the specified prompt on the new connection
* Issue the commands desired over the new connection

.. note:: There may be several Retry actions necessary within these
          steps.

So, for a UBoot operation, this results in a pipeline like:

* UBootCommandOverlay - substitutes dynamic and device-specific data
  into the UBoot command list specified in the device configuration.
* ConnectDevice - establishes a serial connection to the device, as
  specified by the device configuration
* UBootRetry - wraps the subsequent actions in a retry

 * UBootInterrupt - sets the ``Hit any key`` prompt in a new connection
 * ResetDevice - sends the reboot command to the device
 * ExpectShellSession - waits for the specified prompt to match
 * UBootCommandsAction - issues the commands to UBoot

Using debug logs
================

The refactored dispatcher has a different approach to logging:

#. **all** logs are structured using YAML
#. Actions log to discrete log files
#. Results are logged for each action separately
#. Log messages use appropriate YAML syntax.

Check the output of the log files in a YAML parser
(e.g. http://yaml-online-parser.appspot.com/). General steps for YAML
logs include:

* Three spaces at the start of strings (this matches the indent appropriate
  for the default ``id:`` tag which preceds the log entry).
* Careful use of colon ``:`` - YAML assigns special meaning to a colon
  in a string, so use it to separate the label from the message.

.. code-block:: python

    yaml_log.debug('results:', res)

(where ``res`` is a python dict).

.. code-block:: python

    yaml_log.debug('   err: lava_test_shell has timed out')

Three spaces, a label and then the message.

Examples
--------

.. code-block:: yaml

 - id: "<LAVA_DISPATCHER>2014-10-22 15:10:56,666"
   ok: lava_test_shell seems to have completed
 - id: "<LAVA_DISPATCHER>2014-10-22 15:10:56,666"
   log: "duration: 45.80"
 - id: "<LAVA_DISPATCHER>2014-10-22 15:10:56,666"
   results: OrderedDict([('linux-linaro-ubuntu-pwd', 'pass'),
   ('linux-linaro-ubuntu-uname', 'pass'), ('linux-linaro-ubuntu-vmstat', 'pass'),
   ('linux-linaro-ubuntu-ifconfig', 'pass'), ('linux-linaro-ubuntu-lscpu', 'pass'),
   ('linux-linaro-ubuntu-lsusb', 'fail'), ('linux-linaro-ubuntu-lsb_release', 'pass'),
   ('linux-linaro-ubuntu-netstat', 'pass'), ('linux-linaro-ubuntu-ifconfig-dump', 'pass'),
   ('linux-linaro-ubuntu-route-dump-a', 'pass'), ('linux-linaro-ubuntu-route-ifconfig-up-lo', 'pass'),
   ('linux-linaro-ubuntu-route-dump-b', 'pass'), ('linux-linaro-ubuntu-route-ifconfig-up', 'pass'),
   ('ping-test', 'fail'), ('realpath-check', 'fail'), ('ntpdate-check', 'pass'),
   ('curl-ftp', 'pass'), ('tar-tgz', 'pass'), ('remove-tgz', 'pass')])


.. code-block:: python

 [{'expect timeout': 300, 'id': '<LAVA_DISPATCHER>2014-10-22 15:34:21,487'},
 {'id': '<LAVA_DISPATCHER>2014-10-22 15:34:21,488',
  'ok': 'lava_test_shell seems to have completed'},
 {'id': '<LAVA_DISPATCHER>2014-10-22 15:34:21,488', 'log': 'duration: 34.19'},
 {'id': '<LAVA_DISPATCHER>2014-10-22 15:34:21,489',
  'results': "OrderedDict([('linux-linaro-ubuntu-pwd', 'pass'),
  ('linux-linaro-ubuntu-uname', 'pass'), ('linux-linaro-ubuntu-vmstat', 'pass'),
  ('linux-linaro-ubuntu-ifconfig', 'pass'), ('linux-linaro-ubuntu-lscpu', 'pass'),
  ('linux-linaro-ubuntu-lsusb', 'fail'), ('linux-linaro-ubuntu-lsb_release', 'pass'),
  ('linux-linaro-ubuntu-netstat', 'pass'), ('linux-linaro-ubuntu-ifconfig-dump', 'pass'),
  ('linux-linaro-ubuntu-route-dump-a', 'pass'), ('linux-linaro-ubuntu-route-ifconfig-up-lo', 'pass'),
  ('linux-linaro-ubuntu-route-dump-b', 'pass'), ('linux-linaro-ubuntu-route-ifconfig-up', 'pass'),
  ('ping-test', 'fail'), ('realpath-check', 'fail'), ('ntpdate-check', 'pass'),
  ('curl-ftp', 'pass'), ('tar-tgz', 'pass'), ('remove-tgz', 'pass')])"}]

.. _adding_new_classes:

Adding new classes
==================

See also :ref:`mapping_yaml_to_code`:

The expectation is that new tasks for the dispatcher will be created
by adding more specialist Actions and organising the existing Action
classes into a new pipeline for the new task.

Adding new behaviour is a two step process:

- always add a new Action, usually with an internal pipeline, to
  implement the new behaviour
- add a new Strategy class which creates a suitable pipeline to use
  that Action.

A Strategy class may use conditionals to select between a number of
top level Strategy Action classes, for example ``DeployImageAction``
is a top level Strategy Action class for the DeployImage strategy. If
used, this conditional **must only operate on job parameters and the
device** as the selection function is a ``classmethod``.

A test Job will consist of multiple strategies, one for each of the
listed *actions* in the YAML file. Typically, this may include a
Deployment strategy, a Boot strategy, a Test strategy and a Submit
strategy. Jobs can have multiple deployment, boot, or test actions.
Strategies add top level Actions to the main pipeline in the order
specified by the parser. For the parser to select the new strategy,
the ``strategies.py`` module for the relevant type of action
needs to import the new subclass. There should be no need to modify
the parser itself.

A single top level Strategy Action implements a single strategy for
the outer Pipeline. The use of :ref:`retry_diagnostic` can provide
sufficient complexity without adding conditionals to a single top level
Strategy Action class. Image deployment actions will typically include a
conditional to check if a Test action is required later so that the
test definitions can be added to the overlay during deployment.

Re-use existing Action classes wherever these can be used without changes.

If two or more Action classes have very similar behaviour, re-factor to make a
new base class for the common behaviour and retain the specialised classes.

Strategy selection via select() must only ever rely on the device and the
job parameters. Add new parameters to the job to distinguish strategies, e.g.
the boot method or deployment method.

#. A Strategy class is simply a way to select which top level Action
   class is instantiated.
#. A top level Action class creates an internal pipeline in ``populate()``

   * Actions are added to the internal pipeline to do the rest of the work

#. a top level Action will generally have a basic ``run()`` function which
   calls ``run_actions`` on the internal pipeline.
#. Ensure that the ``accepts`` routine can uniquely identify this
   strategy without interfering with other strategies. (:ref:`new_classes_unit_test`)
#. Respect the existing classes - reuse wherever possible and keep all
   classes as pure as possible. There should be one class for each type
   of operation and no more, so to download a file onto the dispatcher
   use the DownloaderAction whether that is an image or a dtb. If the
   existing class does not do everything required, inherit from it and
   add functionality.
#. Respect the directory structure - a strategies module should not need
   to import anything from outside that directory. Keep modules together
   with modules used in the same submission YAML stanza.
#. Expose all configuration in the YAML, noy python. There are FIXMEs
   in the code to remedy situations where this is not yet happening but
   avoid adding code which makes this problem worse. Extend the device
   or submission YAML structure if new values are needed.
#. Take care with YAML structure. Always check your YAML changes in the
   online YAML parser as this often shows where a simple hyphen can
   dramatically change the complexity of the data.
#. Cherry-pick existing classes alongside new classes to create new
   pipelines and keep all Action classes to a single operation.
#. Code defensively:

   #. check that parameters exist in validation steps.
   #. call super() on the base class validate() in each Action.validate()
   #. handle missing data in the dynamic context
   #. use cleanup() and keep actions idempotent.

.. _new_classes_unit_test:

Always add unit tests for new classes
-------------------------------------

Wherever a new class is added, that new class can be tested - if only
to be sure that it is correctly initialised and added to the pipeline
at the correct level. Always create a new file in the tests directory
for new functionality. All unit tests need to be in a file with the
``test_`` prefix and add a new YAML file to the sample_jobs so that
the strategies to select the new code can be tested. See :ref:`yaml_job`.

Often the simplest way to understand the available parameters and how
new statements in the device configuration or job submission show up
inside the classes is to use a unit test. To run a single unit-test,
for example test_function in a class called TestExtra in a file
called test_extra.py, use::

 $ python -m unittest -v -c -f lava_dispatcher.pipeline.test.test_extra.TestExtra.test_function

Example python code:

.. code-block:: python

 import os
 import unittest

 class TestExtra(unittest.TestCase):  # pylint: disable=too-many-public-methods

    def test_function(self):
        print "Hello world"


Online YAML checker
-------------------

http://yaml-online-parser.appspot.com/

Use syntax checkers during the refactoring
------------------------------------------

::

 $ sudo apt install pylint
 $ pylint -d line-too-long -d missing-docstring lava_dispatcher/pipeline/

Use class analysis tools
------------------------

::

 $ sudo apt install graphviz
 $ pyreverse lava_dispatcher/pipeline/
 $ dot -Tpng classes_No_Name.dot > classes.png

(Actual images can be very large.)

Use memory analysis tools
-------------------------

* http://jam-bazaar.blogspot.co.uk/2009/11/memory-debugging-with-meliae.html
* http://jam-bazaar.blogspot.co.uk/2010/08/step-by-step-meliae.html

::

 $ sudo apt install python-meliae

Add this python snippet to a unit test or part of the code of interest:

.. code-block:: python

 from meliae import scanner
 scanner.dump_all_objects('filename.json')

Once the test has run, the specified filename will exist. To analyse
the results, start up a python interactive shell in the same directory::

 $ python

.. code-block:: python

 >>> from meliae import loader
 >>> om = loader.load('filename.json')
 loaded line 64869, 64870 objs,   8.7 /   8.7 MiB read in 0.9s
 checked    64869 /    64870 collapsed     5136
 set parents    59733 /    59734
 collapsed in 0.4s
 >>> s = om.summarize(); s

.. note:: The python interpreter, the ``setup.py``
          configuration and other tools may allocate memory as part
          of the test, so the figures in the output may be larger than
          it would seem for a small test. A basic test may give a
          summary of 12Mb, total size. Figures above 100Mb should
          prompt a check on what is using the extra memory.

Pre-boot deployment manipulation
================================

.. note:: These provisions are under development and are likely to
          change substantially. e.g. it may be possible to do a lot
          of these tasks using secondary media and secondary connections.

There are several situations where an environment needs to be setup in
a contained and tested manner and then used for one or multiple LAVA
test operations.

One solution is to use MultiNode and this works well when the device
under test supports a secondary connection, e.g. ethernet.

MultiNode has requirements on a POSIX-type command line shell to be
able to pass messages, e.g. busybox.

QEMU tests involve downloading a pre-built chroot based on a stable
distribution release of a foreign architecture and running tests inside
that chroot.

Android tests may involve setting up a VM or a configured chroot to
expose USB devices whilst retaining the ability to use different
versions of tools for different tests.
