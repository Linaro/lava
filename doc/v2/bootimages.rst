.. lava_images:

.. still needs to be reconciled, maybe merge in the standard files section.

Building and manipulating images
********************************

This section looks into how to manipulate, inspect and create boot
images. The details of preparing a suitable kernel or configuring a
particular bootloader is beyond the scope of this
documentation. Instead, we'll concentrate on how to look inside
available images, what needs to be done to use a different operating
system as the rootfs and how to mount, modify or create boot images.

This documentation relies on support present in the **Linux** kernel.
Other kernels can be put inside boot images but using such kernels at
runtime to create boot images is beyond the scope of this page.

Basics of building an image
***************************

#. **kernel** - LAVA typically works with Linux but there's nothing
   to say that other kernels can't be used - just don't expect LAVA
   (or LAVA developers) to be able to have direct knowledge of any
   issues with kernels other than Linux
#. **bootloader** - A variety of different bootloaders are directly
   supported in LAVA. Lots of test jobs have been run with `U-Boot`_,
   but more and more jobs are using `UEFI`_ or `Grub`_.
#. **rootfs** - generally a simple, minimal tarball of a filesystem
   created by any of the many tools available to bootstrap the
   operating system. Debian based distributions commonly use
   ``debootstrap`` or similar tools.

   * *Changes to the rootfs* to make it bootable - raw bootstraps are
     rarely bootable directly, various init changes are needed and some
     of these are board specific (e.g. which device to use for the
     serial console).

.. _`U-Boot`: http://www.denx.de/wiki/U-Boot
.. _`UEFI`: http://www.uefi.org/
.. _`Grub`: https://www.gnu.org/software/grub/

Obtaining a kernel
==================

This often requires specialist knowledge of the particular board and
you may be dependent on a landing team or other third party for a
kernel configuration and patches. Some sources only provide a binary
image, sometimes already combined with a bootloader.

Obtaining a bootloader
======================

Similar to a kernel, you may have little choice over which bootloader
to use, although it is entirely reasonable to use a more limited
bootloader provided by someone else to chainload a more capable
bootloader which has more functionality. Note - the Linux kernel can
be used as a secondary bootloader using kexec. The details of how to
do this will vary according to the board, available bootloader and
boot requirements.

From here on, this page works on how to get a kernel and bootloader
into an image to boot on the device.

Inspecting existing images
**************************

Tools to install and get to know
================================

#. **parted** - there are lots of sites with information on ``parted``,
   the simplest way to get used to it is to use it on empty block
   devices - an example is at the end of this section.
#. **dd** - a utility to copy a file which can take input from devices
   like ``/dev/zero``, commonly used to create empty files of a known
   size and to copy images directly from one block device to another.
#. **qemu** - a wide variety of support for booting images, including
   images for architectures other than the host architecture.
#. **mount** - already installed but there are options which will
   become second-nature after working with boot images.
#. **gzip** - images are typically compressed for download. There are
   other compression algorithms but most images contain a lot of empty
   space (for later tests to take) so ``gzip`` is usually enough to get
   suitable compression. Compressed images will need ``gunzip`` before
   being mountable.
#. **losetup** - this is the tool used to configure loop device
   support in the Linux kernel.
#. **chroot** - change root into a directory containing a new rootfs,
   if using ``qemu``, this rootfs could even run binaries for a
   different architecture. ``chroot`` puts you into a new shell inside
   the rootfs where you can modify files and execute programs without
   affecting the external system. (There are limitations to how much a
   chroot can protect the external system, but these are unlikely to
   affect building a boot image.)

Concepts behind boot images
===========================

LAVA V2 uses GuestFS_ to remove the need for loop devices, offsets or
``losetup`` during LAVA operations. The tools remain useful for times
when the image needs to be modified outside LAVA.

.. _GuestFS: http://libguestfs.org/

#. **offsets** - once decompressed, many boot images contain multiple
   partitions, so a simple ``mount`` operation, even using the
   ``loop`` option, will fail. An offset tells ``mount`` where to look
   in the image to find the start of the partition to be
   mounted. Offsets are determined by the original setup of the image
   and can be determined using tools like ``parted``.
#. **loop devices** - the Linux ``loop`` kernel module can allow an
   image to be mounted as a block device. Such mount operations need
   to be performed as ``root`` or with ``sudo``. Loop devices can be
   limited but see :ref:`max_loop`.
#. **boot partitions** - some bootloaders require that files required
   to boot the device are stored using a particular filesystem, often
   ``FAT``. To allow the rootfs to use a different filesystem like
   ext2, ext3 or ext4, the boot files are stored on a separate
   partition.
#. **serial console** - a device to which the device can write messages
   during boot and provide a login prompt (which can be automated for
   a LAVA test job).
#. **root password** - one thing that many people forget when creating
   a rootfs using their favourite Linux distribution is that the root
   password is typically created by an installer and **not** by the
   bootstrap tool. Depending on the security of the OS, you may need
   to ``chroot`` into the new rootfs before finishing the image and
   set a usable root password with the ``passwd`` command.

Find the offset
---------------

#. First, **decompress your image**. These examples will assume that
   the resulting file is called ``test.img``
#. Print the partition offsets::

    $ parted test.img -s unit b print
    Model:  (file)
    Disk /home/linaro/documents/arndale-vmgroup/test.img: 1073741824B
    Sector size (logical/physical): 512B/512B
    Partition Table: msdos

    Number  Start      End          Size         Type     File system  Flags
    1      512B       4194303B     4193792B     primary
    2      4194304B   58720255B    54525952B    primary  fat32        boot, lba
    3      58720256B  1073741823B  1015021568B  primary  ext4

   In this example, there is an unused partition starting at an offset
   of 512 bytes, followed by a ``VFAT``-formatted boot partition
   starting at an offset of 4194304 bytes, then the main rootfs is an
   ``ext4`` filesystem in partition 3 starting at an offset of
   58720256 bytes.

   Other tasks using ``parted`` will need root access or ``sudo``.

Mounting partitions using loop and offset
-----------------------------------------

#. To mount the boot partition, pass the ``loop`` and ``offset`` options
   to ``mount``::

    $ sudo mkdir -p /mnt/boot
    $ sudo mount -o loop,offset=4194304 test.img /mnt/boot

   .. note:: Failures from mount complaining about a bad superblock
             can arise from a wrong offset.

#. When you are finished with the filesystem, make sure you unmount
   it::

     $ sudo umount /mnt/boot

   .. warning:: Remember to check the output of ``mount`` and avoid
                mounting the same partition more than once or moving
                the image without using ``umount``.

Creating new images
*******************

#. QEMU has easy support for creating empty images::

   $ qemu-image create test.img

#. Use ``dd`` to create an empty file which can be used to host
   partitions and form the basis of a new boot image.

   * Using ``/dev/zero`` is recommended for this; it is the fastest
     data source, and will also help give good compression as the empty
     space in the image file will all be full of zero bytes.

   ``dd`` can create a file of any size, subject to the free space
   on your machine. Specify the size of each block to write and the
   number of blocks. To create an image of 1 GB (1024 MB) use::

    $ sudo dd if=/dev/zero of=test.img bs=1M count=1024

#. Create a partition table. While it is possible to use images
   without partition tables if all files are in a single filesystem,
   some devices or bootloaders may refuse to boot from such images::

    $ sudo losetup /dev/loop0 test.img
    $ sudo parted /dev/sda -s unit mb mktable msdos

   If you are copying the layout of a known-working image you can use
   parted to replicate the partitions. If you just need a boot
   partition, then **allow space for modification**. It is very likely
   that you or someone using your image will want to change the kernel
   image or test a second kernel. Always try to leave enough space in
   your boot partition to have a second kernel image. Remember that
   kernel images may increase in size as more functionality is
   supported.

   Refer to the ``parted`` documentation for how to create the
   partition layout you want and experiment with your empty test image
   file. ``parted`` has an interactive mode which can be used to get
   used to the tool and the options::

    $ sudo parted test.img

   One example setup could be::

    $ sudo parted /dev/loop0 -s unit mb mkpart primary 1 10
    $ sudo parted /dev/loop0 -s unit mb mkpart primary 11 110
    $ sudo parted /dev/loop0 -s unit mb mkpart primary 111 1024

    parted /dev/loop0 unit B -s print
    Model:  (file)
    Disk /dev/loop0: 1073741824B
    Sector size (logical/physical): 512B/512B
    Partition Table: msdos

    Number  Start       End          Size        Type     File system  Flags
     1      1048576B    10485759B    9437184B    primary
     2      10485760B   110100479B   99614720B   primary
     3      110100480B  1024458751B  914358272B  primary

#. Create a filesystem for each partition. After ``parted`` has
   created the partitions, the loop devices need to be configured to
   use the offsets declared by parted::

    $ sudo losetup -o 10485760 /dev/loop1 /dev/loop0
    $ sudo mkfs.vfat /dev/loop1
    $ sudo losetup -o 110100480 /dev/loop2 /dev/loop0
    $ sudo mkfs.ext3 /dev/loop2

#. Copy your files onto the new filesystems::

    $ sudo mount -o loop,offset=10485760 test.img /mnt/boot/
    $ pushd /mnt/boot/
    $ sudo tar -xzf /tmp/boot.tar.gz
    $ popd
    $ sudo umount /mnt/boot/

#. Clean up your ``losetup`` operations::

    $ sudo losetup -d /dev/loop2
    $ sudo losetup -d /dev/loop1
    $ sudo losetup -d /dev/loop0

   Ensure that there are no loopback mounts remaining::

    $ sudo losetup -a

Making a bootstrap rootfs usable
================================

#. **set the serial console** - Each device tends to have a different
   device used for the serial console, and you may need to configure a
   serial console login (``getty``) in your image too. Recent Linux
   images using ``systemd`` should automatically start a getty on the
   kernel's default console device, but older images using
   ``sysvinit`` will need some explicit configuration.

   For Debian, this would need to be done in ``/etc/inittab``. This
   example is from an iMX.53 image::

    # echo T0:23:respawn:/sbin/getty -L ttymxc0 115200 vt102 >> ./etc/inittab

   https://linux.codehelp.co.uk/?p=49

   The bootloader settings for the board usually indicate which device
   is to be used as the serial console.

#. **set default networking** - Depending on your bootstrap tool,
   there may well be no network interfaces defined. For Debian, this
   can be implemented using a file in ``/etc/network/interfaces.d/``,
   e.g.::

    # echo auto lo eth0 > ./etc/network/interfaces.d/base
    # echo iface lo inet loopback >> ./etc/network/interfaces.d/base
    # echo iface eth0 inet dhcp >> ./etc/network/interfaces.d/base

#. **set a root password** - This is surprisingly easy to forget until
   after the image has booted. Depending on the distribution, this
   step can involve using ``qemu`` to ``chroot`` into the rootfs to be
   able to execute the ``passwd`` utility. Manual changes to
   ``/etc/passwd`` can be ignored, depending on the shadow /
   authentication precautions implemented by the distribution::

    $ sudo cp /usr/bin/qemu-armhf-static ./usr/bin/
    $ sudo chroot .
    # passwd
    # exit

Other steps which may be required
---------------------------------

#. **enable the serial console in securetty** - e.g. the arndale board
   has a serial console in a device which does not generally appear in
   ``/etc/securetty``, so this needs to be added::

    # echo ttySAC2 >> ./etc/securetty

#. **set a useful hostname** - choose your board hostname and your
   local domain (so that a fully qualified hostname can be supported)::

    # echo board > ./etc/hostname
    # echo 127.0.0.1 board board.domain >> ./etc/hosts

.. _max_loop:

Increasing the number of loop devices
=====================================

It can be useful to increase the number of available loopback devices
from the default of 8. This can be done by adding a file in
``/etc/modprobe.d/``::

 options loop max_loop=64

Further information
*******************

* https://linux.codehelp.co.uk/?p=49
* https://linux.codehelp.co.uk/?p=59
* http://www.andremiller.net/content/mounting-hard-disk-image-including-partitions-using-linux
