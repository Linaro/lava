Deploying an iPXE (x86) device
=================================

This page describes the hardware and software setup for iPXE devices (x86 boards)
More information on iPXE is available here http://ipxe.org/start


Preparing the target test device
--------------------------------

The target device will need the following:
* serial port
* network adapter supported by iPXE
* ability to boot from USB, CD-Rom
* OR a network adapter with a writable PXE ROM

Serial console support is not enabled in the standard binaries from http://ipxe.org/ so
a customised build is required.
There is a pre-built binary for USB drives available here:

http://images.validation.linaro.org/lava-masters/ipxe.usb

iPXE has coloured text in the title prompt which can cause issues with the expect library
that LAVA uses to communicate with the device. To avoid this issue the above USB binary has
been patched to remove the colour.


Dispatch Steps
--------------

The target boots iPXE from a USB disk or the network adapter ROM, and is interrupted by LAVA.
The kernel/ramdisk are fetched over HTTP from the dispatcher and then booted.
If an nfsrootfs is requested, it is extracted on the dispatcher and then mounted by the device.


Kernel, Ramdisk and Rootfs considerations
-----------------------------------------

If you are considering only using a ramdisk, do not make it too large as you are restricted by available memory.
The ramdisk should have enough logic and tools to automatically bring up the network interface which is
connected to the LAVA dispatcher. An alternative is an NFS rootfs which has much more storage space.

If you intend to use an NFS rootfs, your kernel will need NFS and networking support, or you will need
an accompanying ramdisk with the modules/scripts to support NFS root devices.

In any case, either your kernel or your ramdisk will need networking support for LAVA jobs to complete.
