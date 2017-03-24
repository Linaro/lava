.. index:: standard qemu kernel

.. _standard_qemu_kernel:

Standard test job for QEMU - Sid arm64
######################################

The :ref:`first standard QEMU job <standard_amd64_jessie_qemu>` uses a kernel,
initramfs, modules and configuration. This is a simple boot test - a test shell
is not supported as the ramdisk is not unpacked for QEMU.

.. index:: qemu standard kernel initramfs

.. _standard_kernel_initramfs:

QEMU with kernel and initramfs
******************************

This example will show how to boot an arm64 Debian kernel and initramfs in
LAVA.

The initramfs needs to include all kernel modules which are needed to run the
tests required by the test writer. The Debian initramfs includes modules
automatically. There is no support for adding modules to the initramfs for QEMU
in LAVA.

.. include:: examples/test-jobs/qemu-kernel-standard-sid.yaml
     :code: yaml
     :end-before: context:

`Download / view qemu-kernel-standard-sid.yaml
<examples/test-jobs/qemu-kernel-standard-sid.yaml>`_.

.. note:: This example uses the Debian kernel which is a modular build. When
   modifying the standard qemu test jobs, **always** keep the builds of the
   kernel and initramfs in sync or provide a replacement kernel with all
   necessary modules built in.

Job context
===========

.. include:: examples/test-jobs/qemu-kernel-standard-sid.yaml
     :code: yaml
     :start-after: visibility: public
     :end-before: metadata:

The :term:`job context` for this example specifies the default ``machine`` and
``cpu`` values for the ``arm64`` architecture using the ``qemu`` template. (The
``arm64`` architecture can also be specified as ``aarch64`` with this
template.)

The ``extra_options`` list can contain any option which is understood by QEMU.
The name of the option and the value of that option should be listed as
separate items in the ``extra_options`` list for correct parsing by QEMU.

Test writers can choose which QEMU options are specified as ``extra_options``
and which as ``image_args``. In some situations, this can matter as some
options to QEMU need to be in a specific order. ``extra_options`` are added to
the command line **before** ``image_args`` and ``image_args`` are added in the
order specified in the test job.

.. note:: Check the syntax carefully - the option is **-smp** so the line in
   ``extra_options`` uses a hyphen to continue the list in YAML, then a space,
   then the option which itself starts with a hyphen.

Deploying the kernel
====================

.. include:: examples/test-jobs/qemu-kernel-standard-sid.yaml
     :code: yaml
     :start-after: # ACTION_BLOCK
     :end-before: # BOOT_BLOCK

Deploying a kernel and initramfs without a root filesystem can be done using
the ``image_args`` support. In this example, the kernel command line is built
using the ``--append`` option to QEMU.

The example also uses the ``sha256sum`` checksum support to ensure that the
correct files are downloaded.

.. caution:: The initramfs in this test job comes from a Debian build,
   **however** the initramfs itself is **not** a full Debian system. In
   particular, it uses ``busybox`` for the shell and various utilities like
   ``mount``. To handle this, the deployment **must** specify the operating
   system as ``oe`` so that LAVA can operate within the initramfs using only
   minimal tools.

Booting the kernel
==================

.. include:: examples/test-jobs/qemu-kernel-standard-sid.yaml
     :code: yaml
     :start-after: # BOOT_BLOCK

As this system will boot into the initramfs, the ``'\(initramfs\)'`` prompt is
specified.
