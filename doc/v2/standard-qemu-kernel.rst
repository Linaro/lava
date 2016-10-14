.. index:: standard qemu kernel

.. _standard_qemu_kernel:

Booting a kernel with QEMU
##########################

The :ref:`standard_amd64_jessie_qemu` uses a fully built image containing a
root filesystem (rootfs), kernel, initramfs, modules and configuration. QEMU
also supports booting a kernel and an initramfs with or without a root
filesystem. Testing such jobs in LAVA involves adding the overlay (containing
the LAVA test shell helpers and the test shell definition created by the test
writer) as an additional drive. This avoids needing to modify the initramfs or
root filesystem provided by the test writer but does have some requirements,
depending on the type of test job.

.. index:: qemu standard kernel initramfs

.. _standard_kernel_initramfs:

QEMU with kernel and initramfs
****************************

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
     :end-before: - test:

As this system will boot into the initramfs, the ``'\(initramfs\)'`` prompt is
specified.

.. index:: qemu standard kernel initramfs rootfs

.. _standard_kernel_initramfs_rootfs:

QEMU with kernel, initramfs and rootfs
************************************

This example will show how to boot an arm64 Debian kernel and initramfs with a
root filesystem (as a drive) in LAVA.

The initramfs will need enough kernel modules to be able to mount the specified
rootfs. The rest of the kernel modules should be present inside the rootfs.

The standard builds use Debian kernels and the initramfs generated inside a
Debian chroot when the kernel package is installed. The relevant kernel modules
are retained within the rootfs.

.. include:: examples/test-jobs/qemu-kernel-rootfs-standard-sid.yaml
     :code: yaml
     :end-before: context:

`Download / view qemu-kernel-rootfs-standard-sid.yaml
<examples/test-jobs/qemu-kernel-rootfs-standard-sid.yaml>`_.

.. note:: When modifying the standard qemu test jobs, **always** keep the
   builds of the kernel, initramfs and rootfs in sync or provide a replacement
   kernel with all necessary modules built in.

Job context
===========

.. include:: examples/test-jobs/qemu-kernel-rootfs-standard-sid.yaml
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

Deploying the kernel
====================

.. include:: examples/test-jobs/qemu-kernel-rootfs-standard-sid.yaml
     :code: yaml
     :start-after: # ACTION_BLOCK
     :end-before: # BOOT_BLOCK

Deploying a kernel and initramfs with a root filesystem can be done using the
``image_args`` support. In this example, the kernel command line is built using
the ``--append`` option to QEMU.

.. caution:: The ``append`` option explicitly specifies the **UUID** of the
   partition where the kernel will be able to find the specified ``init``.
   **Avoid** using ``/dev/vda1`` or similar because LAVA needs to add an extra
   drive containing the test shell helpers and definitions and the kernel can
   enumerate the drives differently on consecutive boots, causing the test job
   to fail unpredictably. Ensure you specify the checksums of the rootfs so
   that the UUID is correct for the downloaded file.

When using checksums, avoid URLs including shortcuts like ``latest``. Specify
the full URL to ensure consistency between tests.

.. note:: The initramfs in this test job is used to mount the root filesystem
   which is a standard Debian build. The deployment can therefore specify the
   operating system as ``debian`` so that LAVA can operate within the root
   filesystem using Debian tools and the ``bash`` shell.

Booting the kernel
==================

.. include:: examples/test-jobs/qemu-kernel-rootfs-standard-sid.yaml
     :code: yaml
     :start-after: # BOOT_BLOCK
     :end-before: - test:

As this system will boot into the provided root filesystem, the ``'root@sid:'``
prompt is specified and the ``auto_login`` details of the root filesystem are
specified.
