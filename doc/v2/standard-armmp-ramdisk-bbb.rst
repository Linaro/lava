.. _standard_known_devices:

Standard test jobs using known devices
######################################

If you do not have access to a ``beaglebone-black`` device in a LAVA instance
yet, you will still benefit from following the example as an introduction to
integrating a range of ARMv7 U-Boot devices into LAVA.

Standard test jobs for other devices
************************************

If you do not have a beaglebone-black available, there are very similar
standard test jobs available for ``arndale``, ``cubietruck`` and ``panda``
devices. "These files are very similar; typically the only substantive changes
come down to the :abbr:`DTB (Device Tree Blob)` for the relevant device type.

* `panda <examples/test-jobs/standard-armmp-ramdisk-panda.yaml>`_

  * ``omap4-panda.dtb``

* `arndale <examples/test-jobs/standard-armmp-ramdisk-arndale.yaml>`_

  * ``exynos5250-arndale.dtb``

* `cubietruck <examples/test-jobs/standard-armmp-ramdisk-cubietruck.yaml>`_

  * ``sun7i-a20-cubietruck.dtb``

.. _standard_armmp_bbb:

Standard test job for beaglebone-black
**************************************

The first standard job for a beaglebone-black is a simple ramdisk test job.

.. include:: examples/test-jobs/standard-armmp-ramdisk-bbb.yaml
     :code: yaml
     :end-before: metadata:

`Download / view <examples/test-jobs/standard-armmp-ramdisk-bbb.yaml>`_

Features of a ramdisk test job
------------------------------

* **Minimal system** -  sometimes based on a full OS like Debian or
  OpenEmbedded, sometimes a custom built system. In this standard test job, the
  ramdisk is built by installing the associated kernel package in a Debian
  system. The ramdisk is not a full system, certain utilities are omitted or
  replaced with minimal alternatives from ``busybox``.

* **Custom prompt** - ``(initramfs)`` needs to be specified instead of a login
  prompt like ``root@debian``.

* **Modifications** - LAVA needs to modify the ramdisk if a test action is
  specified in a ramdisk test job to be able to add the scripts which support
  the operation of the test shell. Once modified, LAVA has to repack the
  ramdisk, including adding a U-Boot header if the device requires one.

Metadata
========

When you copy this standard test job for your own testing, remember to
**modify** this metadata to distinguish your copy from the original.

.. include:: examples/test-jobs/standard-armmp-ramdisk-bbb.yaml
     :code: yaml
     :start-after: visibility: public
     :end-before: # ACTION_BLOCK

Deploy
======

U-Boot support in LAVA supports a variety of deployment methods. This standard
job will use the Debian :abbr:`ARMMP (ARM Multiple Platform)` kernel package.
The standard build script for this test job prepares a simple root filesystem
and installs the ARMMP kernel. The installation scripts in Debian generate a
suitable ramdisk and the script builds a tarball (``.tar.gz``) of the kernel
modules from the package.

* **kernel** - ``vmlinuz``

* **dtb** - ``dtbs/am335x-boneblack.dtb``

* **ramdisk** - ``initramfs.cpio.gz``

* **modules** - ``modules.tar.gz``

Specific options
----------------

The ``modules.tar.gz`` and ``initramfs.cpio.gz`` are both compressed using
``gzip`` and this **must** be specified in the test job definition.

In addition, the ramdisk on a beaglebone-black using U-Boot needs to have a
suitable U-Boot header. This means that the ``add-header: u-boot`` option is
required.

Finally, although the ramdisk was built on a Debian system, the ramdisk itself
does not behave in the same way as a full Debian system. It lacks critical
components like ``apt``, so the test job specifies that the test shell can only
expect basic compatibility by specifying ``oe`` for OpenEmbedded.

.. include:: examples/test-jobs/standard-armmp-ramdisk-bbb.yaml
     :code: yaml
     :start-after: ACTION_BLOCK
     :end-before: # BOOT_BLOCK

Boot
====

U-Boot support in LAVA supports a variety of deployment methods. This standard
job will use the ``ramdisk`` commands from the :term:`device type` template and
the ``bootz`` boot method (as the supplied Debian kernel file, ``vmlinuz`` is
compressed).

.. include:: examples/test-jobs/standard-armmp-ramdisk-bbb.yaml
     :code: yaml
     :start-after: BOOT_BLOCK
     :end-before: # TEST_BLOCK

Test
====

The limitation of a ramdisk deployment is that certain tools (like ``apt``) are
not available, so the test definition used with this test job is a fairly
minimal *smoke-test*. Avoid test definitions which specify packages to be
installed in the ``install: deps:`` list.

.. include:: examples/test-jobs/standard-armmp-ramdisk-bbb.yaml
     :code: yaml
     :start-after: TEST_BLOCK
