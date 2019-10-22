Media limitations of test devices
#################################

.. index:: primary media

.. _primary_media:

Primary media and primary bootloaders
*************************************

Methods like :ref:`deploy to TFTP <deploy_to_tftp>` rely on LAVA interrupting
the primary bootloader on the :term:`DUT` and changing the boot process to use
the files provided by the test writer. Many test devices require this
bootloader to be installed onto re-writeable media which can be modified from
the running system, for example an SD card.

The critical element for LAVA is the **first point where the boot can
be interrupted or modified**. Devices which lack some kind of
:term:`BMC` rely on this bootloader to be able to automatically
recover from a broken deployment. This bootloader can be considered as
the **primary bootloader** and the medium where this is installed can
be considered as the **primary medium** which **must** be protected
from deployments which would replace its entire contents. For example,
a panda board has an SD card and USB host support, the primary
bootloader (U-Boot) **must** be on the SD card, so V2 uses the SD card
as primary media. It is therefore not supportable for a panda board to
deploy to the SD card in LAVA.

.. note:: Primary and secondary media relate to devices where the primary
   bootloader is installed on writeable media and where that bootloader needs
   to operate before new software can be deployed. Fastboot devices often
   differ and allow all media on the device to be modified in test jobs as long
   as jumpers or dip switches are set to force the device to boot into fastboot
   mode. Modifying the fastboot support on the device may involve changing
   those jumpers and/or dip switches, i.e. an admin task whilst the device is
   offline.

It is important to consider the constraints of primary media as a limitation of
the hardware for automation. The risks of allowing test writers to easily brick
devices outweigh the usefulness of the primary media for files other than the
primary bootloader. LAVA has tried to use partitions on the primary media in
the past and this has proven to be unreliable.

Devices which only provide primary media can still support deployment methods
like TFTP to use ramdisk and NFS test jobs.

.. important:: Many devices allow test writers to access the primary media from
   within a test shell even if the test job has deployed into a ramdisk, NFS or
   secondary media. It remains the responsibility of the test writer to **not**
   modify the primary media from within a test shell *just because you can*.
   Test writers who do so may have submission privileges revoked by the admins.

.. seealso:: :ref:`essential_components`

.. index:: secondary media

.. _secondary_media:

Secondary media
***************

If the device supports any media other than :ref:`primary media
<primary_media>`, all these media are collectively termed **secondary media**.
Any deployment to the secondary media can write a complete image including
partition tables and complete filesystems without affecting the ability of LAVA
to recover from a broken test job.

For example, a beaglebone-black can have a USB stick as secondary media. A
cubietruck can have a single SATA drive. A mustang device can have several SATA
drives attached. Usually, USB is the least useful secondary media as it is so
slow to write and the test job will be trying to write a full size filesystem
image of many gigabytes.

.. seealso:: :ref:`primary_media` and :ref:`admin_secondary_media`

Bootloader limitations
======================

The bootloader may be unable to write to permanent media. Usually this is a
good thing, bootloaders which can write to media can be problematic, slow
and/or greedy of resources on the worker e.g. fastboot, necessitating the use
of LXC. U-Boot and Grub are each restricted to reading files from media and not
writing new files during the boot process. To deploy a test image to the
secondary media, the device needs to first boot into a full OS environment with
threading, multiple cores, network and full kernel support. A standard test
shell can then write to the media in various ways. Depending on the device
configuration, test writers may still need to respect the location of the
primary bootloader to avoid bricking the device.

LAVA can use secondary media in a number of different ways, depending on the
use case.

.. index:: secondary media with a command list

.. _secondary_media_commands:

Occasional debugging
=====================

Combined with a :ref:`hacking session <hacking_session>`, the boot commands can
be overridden to test support on selected devices. The primary bootloader will
still be used, for example to read files from the filesystem. Optionally, the
kernel can be loaded over TFTP to use the filesystem on the secondary media as
a form of persistence.

.. replace with an example within the docs once the code is on staging.

https://playground.validation.linaro.org/scheduler/job/80647/definition

.. caution:: Unless the device is restricted to particular submitters **and**
   any health check has been disabled, the next test job could replace, corrupt
   or update the root filesystem on the secondary media. The full process would
   have to be reset.

.. index:: secondary media and installers

.. _secondary_media_installer:

Installer testing
=================

An operating system installer is the traditional form of secondary media
deployments. The installer boots into a ramdisk to allow complete access to the
device, including all media. The installer can be used to do the deployment to
the secondary media in LAVA, although support will be required to automate the
questions and prompts normally raised during the process.

This method has the advantage that the final system is a fresh, clean install
and the disadvantage that the whole system has to be recreated each test job,
as well as the overhead of starting and running the installer.

Limitations
-----------

* **Installer may try to write new UEFI or new UBoot** - the automation of the
  installer will need to prevent overwriting the primary bootloader. (If your
  test job bricks the device, the admin could revoke or suspend your submission
  rights.)

* **Not advised for most UBoot devices** - many installer programs need special
  support to install onto UBoot devices and it could be hard to both update the
  kernel in the installed system and prevent modification of the primary
  bootloader.

* **Chainload installed Grub from the primary Grub bootloader** -  Writing a
  second bootloader to the secondary media can work, as long as the second
  bootloader can be chainloaded from the primary bootloader by issuing commands
  to the primary bootloader.

* **Wait for the installer to run**

  * Large SATA drives can take long time to partition.
  * Downloads from mirrors may take time to install

.. index:: secondary media with an image

.. _secondary_media_images:

Secondary media deployment of images
====================================

Secondary media deployments are a way of automating the deployment of a
filesystem image directly to the secondary media. The image will need to
contain the partition(s) and filesystem(s) for the test system.

Unlike the installer support, secondary media deployments can work with
UBoot devices although many ARMv7 devices are limited by slow media like
USB drives instead of SATA.

Limitations
-----------

* **Make sure all tools are installed** \- The test job will download and apply
  the image after completing a test shell, ensure ``wget`` is installed.

* **New image may include new UEFI or new UBoot** \- The image to be deployed
  will need to avoid overwriting the primary bootloader. (If your test job
  bricks the device, the admin could revoke or suspend your submission rights.)

* **Production images can be a risk** \- LAVA still needs to interrupt the
  primary bootloader and add files to the deployed image to be able to run test
  shell definitions. Production images often include security settings which
  will disable this access, causing your tests to fail.

* **Single write operation** \- LAVA downloads the image and then simply writes
  the data to the media before rebooting. The image must be fully configured to
  work in this way, including raising usable network interfaces directly upon
  boot.

Principles and Requirements
***************************

Secondary deployments are done by the device under test, using actions defined
by LAVA and tools provided by the initial deployment. Test writers need to
ensure that the initial deployment has enough support to complete the second
deployment.

Images on remote servers are downloaded to the dispatcher (and decompressed
where relevant) so that the device does not need to do the decompression or
need lots of storage in the initial deployment.

By keeping the downloaded image intact, it becomes possible to put the LAVA
extensions alongside the image instead of inside.

To make this work, several requirements must be met:

* The initial deployment must provide or support installation of all tools
  necessary to complete the second deployment - it is a TestError if there is
  insufficient space or the deployment cannot complete this step.

* The initial deployment does not need enough space for the decompressed image,
  however, the initial deployment is responsible for writing the decompressed
  image to the secondary media from ``stdin``, so the amount of memory taken up
  by the initial deployment can have an impact on the speed or success of the
  write.

* The operation of the second deployment is an action which **precedes** the
  second boot. There is no provision for getting data back from this test shell
  into the boot arguments for the next boot. Any data which is genuinely
  persistent needs to be specified in advance.

* LAVA manages the path to which the second deployment is written, based on the
  media supported by the device and the ID of that media. Where a device
  supports multiple options for secondary media, the job specifies which media
  is to be used.

* LAVA will need to support instructions in the job definition which determine
  whether a failed test shell should allow or skip the boot action following.

* LAVA will declare available media using the **kernel interface** as the
  label. A SATA drive which can only be attached to devices of a particular
  :term:`device type` using USB is still a USB device as it is constrained by
  the USB interface being present in the test image kernel. A SATA drive
  attached to a SATA connector on the board is a SATA device in LAVA
  (irrespective of how the board actually delivers the SATA interface on that
  connector).

* If a device has multiple media of the same type, it is up to the test writer
  to determine how to ensure that the correct image is booted. The ``blkid`` of
  a partition within an image is a permanent UUID within that image and needs
  to be determined in advance if this is to be used in arguments to the
  bootloader as the root filesystem.

* The manufacturer ID and serial number of the hardware to be used for the
  secondary deployment must be set in the device configuration. This makes it
  possible for test images to use such support as is available (e.g. ``udev``)
  to boot the correct device.

* The job definition needs to specify which hardware to use for the second
  deployment - if this label is based on a device node, it is a TestError if
  the use of this label does not result in a successful boot.

* The job definition also needs to specify the path to the kernel, dtb and the
  partition containing the rootfs within the deployed image.

* The job definition needs to include the bootloader commands, although
  defaults can be provided in some cases.

Test Writer steps
=================

* always ensure you have set a usable root password in the image / test media
  or set the root user to not have a password.

  * If a password is set for the root user, the password **must** be declared
    in the test job submission.

* always ensure you have set the bootable flag on the boot partition when
  building the image.

* always ensure you have installed a kernel into the image

  * note down the paths to the kernel and initramfs etc. These will need to
    be specified in the test job submission.

* always ensure you have the UUID of the new filesystem containing the root
  filesystem. This will need to be specified in the test job submission.

* ensure that if a bootloader is present in the image to be deployed that this
  bootloader can be chainloaded by the primary bootloader already on the
  device.

.. these examples need to be expanded once the code is working on staging.

Examples
========

Deploy commands
---------------

This is an example block - the actual data values here are known not to work as
the ``deploy`` step is for a panda but the ``boot`` step in the next example
comes from a working cubietruck job.

This example uses a device configuration where ``UUID-required`` is True.

For simplicity, this example also omits the initial deployment and boot, at the
start of this block, the device is already running a kernel with a ramdisk or
rootfs which provides enough support to complete this second deployment.

.. code-block:: yaml

    # secondary media - use the first deploy to get to a system which can deploy the next
    # in testing, assumed to already be deployed
    - deploy:
        timeout:
          minutes: 10
        to: usb
        # not a real job, just used for unit tests
        compression: gz
        image:
          url: https://releases.linaro.org/12.02/ubuntu/leb-panda/panda-ubuntu-desktop.img.gz
        device: SanDisk_Ultra # needs to be exposed in the device-specific UI
        download: /usr/bin/wget


#. Ensure that the ``deploy`` action has sufficient time to download the
   **decompressed** image **and** write that image directly to the media using
   STDOUT. In the example, the deploy timeout has been set to ten minutes - in
   a test on the panda, the actual time required to write the specified image
   to a USB device was around 6 minutes.

#. Note the deployment strategy - ``to: usb``. This is a direct mapping to the
   kernel interface used to deploy and boot this image. The bootloader must
   also support reading files over this interface.

#. The compression method used by the specified image is explicitly set.

#. The image is downloaded and decompressed by the dispatcher, then made
   available to the device to retrieve and write to the specified media.

#. The device is specified as a label so that the correct UUID can be
   constructed from the device configuration data.

#. The download tool is specified as a full path which must exist inside the
   currently deployed system. This tool will be used to retrieve the
   decompressed image from the dispatcher and pass STDOUT to the writer tool,
   ``dd`` by default. If the download tool is the default ``/usr/bin/wget``,
   LAVA will add the following options:
   ``--no-check-certificate --no-proxy --connect-timeout=30 -S
   --progress=dot:giga -O -`` If different download tools are required for
   particular images, these can be specified, however, if those tools require
   options, the test writer can either ensure that a script exists in the image
   which wraps those options or file a bug to have the alternative tool options
   supported.

The default writer tool is ``dd`` but it is possible to specify an alternative
one.  In particular, ``bmaptool`` is usually a much better choice for USB or SD
card devices.  It will typically flash the image faster and extend the lifetime
of the storage media.  It needs a ``.bmap`` file which contains a block map
alongside the actual image file.  For this reason, two files need to be
downloaded and stored in the same directory on the dispatcher.  The example
below illustrates how to do this:

.. code-block:: yaml

    # secondary media deployment using bmaptool
    - deploy:
        timeout:
          minutes: 10
        to: usb
        # not a real job, just used for illustrative purposes
        compression: gz
        images:
          image:
            url: https://releases.linaro.org/12.02/ubuntu/leb-panda/panda-ubuntu-desktop.img.gz
          bmap:
            url: https://releases.linaro.org/12.02/ubuntu/leb-panda/panda-ubuntu-desktop.img.bmap
        uniquify: false
        device: SanDisk_Ultra # needs to be exposed in the device-specific UI
        writer:
          tool: /usr/bin/bmaptool
          options: copy {DOWNLOAD_URL} {DEVICE}
          prompt: 'bmaptool: info'
        tool:
          prompts: ['copying time: [0-9ms\.\ ]+, copying speed [0-9\.]+ MiB\/sec']

#. The ``images`` list needs to contain one ``image`` entry and can have others
   as well such as ``bmap`` in this case.  They will all be downloaded
   separately to the dispatcher and made available to the board via HTTP.  The
   URL of the ``image`` file is available in the job definition as
   ``{DOWNLOAD_URL}``.  The URL of the other images will need to be determined
   by other means.  Say, the ``image`` file could be a manifest with the list
   of the actual binary images (not the case with this ``bmaptool`` example).

#. Each item in the ``images`` list is normally downloaded into a separate
   sub-directory such as ``image`` or ``bmap`` in this example.  As the
   ``bmaptool`` expects both files to be in the same path, the ``uniquify:
   false`` option is used so all the files are downloaded directly at the root
   of the job's ``storage-deploy-*`` directory.  Please note that if several
   image files have the same name, they will overwrite each other when
   ``uniquify`` is set to ``false``.  For this reason, if not specified in the
   job it will be set to ``true`` by default.

#. To use an alternative writer tool, the ``writer`` parameters are used.  The
   absolute path to the tool must be provided with ``tool`` as well as the
   ``options`` required to call it.  The ``prompt`` is used to detect that the
   flashing has started.

#. The ``writer`` tool will normally also be responsible for downloading the
   image file, hence the ``{DOWNLOAD_URL}`` option passed to it in the example.
   It is also possible to provide both ``download`` and ``writer`` parameters,
   in which case the standard output of the downloader tool will be piped into
   the standard input of the writer tool.

#. The tool ``prompts`` parameter is to detect when the writer tool has
   completed the flashing operation.  When LAVA has matched a prompt with the
   tool output, it will then proceed with the secondary boot action.  The
   ``prompts`` parameters defaults are to match the output of ``dd``, so they
   should be defined appropriately when using an alternative writer tool.

The kernel inside the initial deployment **MUST** support UUID when deployed on
a device where UUID is required, as it is this kernel which needs to make
``/dev/disk/by-id/$path`` exist for ``dd`` to use. Remember not to quote the
UUID::

   root_uuid: UUID=159d17cc-697c-4125-95a0-a3775e1deabe

Boot commands
-------------

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
        prompts:
          - 'linaro-test'
          - 'root@debian:~#'

The ``kernel`` and (if specified) the ``ramdisk`` and ``dtb`` paths are the
paths used by the bootloader to load the files in order to boot the image
deployed onto the secondary media. These are **not necessarily** the same as
the paths to the same files as they would appear inside the image after
booting, depending on whether any boot partition is mounted at a particular
mountpoint.

The ``root_uuid`` is the full option for the ``root=`` command to the kernel,
including the ``UUID=`` prefix.

The ``boot_part`` is the number of the partition from which the bootloader can
read the files to boot the image. This will be combined with the device
configuration interface name and device_id to create the command to the
bootloader, e.g.::

 "setenv loadfdt 'load usb 0:1 ${fdt_addr_r} /boot/dtb-3.16.0-4-armmp-lpae''",

The dispatcher does NOT analyze the incoming image - internal UUIDs inside an
image do not change as the refactored dispatcher does **not** break up or
reorganize the partitions. Therefore, the UUIDs of partitions inside the image
**MUST** be declared by the job submissions.
