Configuring and using KVM in LAVA
=================================

KVM allows a bootstrapped image of an operating system to be booted as a
virtual instance and lava-dispatcher has support for using a KVM image to
ease testing and development of LAVA and lava test shell components.

Creating KVM images with vmdebootstrap
--------------------------------------

 * http://liw.fi/vmdebootstrap/
 * http://gitorious.org/vmdebootstrap/vmdebootstrap

::

  $ sudo apt-get install vmdebootstrap

LAVA wrapper to apply a Linaro overlay to a vmdebootstrap image:

 * https://git.linaro.org/gitweb?p=lava/lava-vmdebootstrap.git;a=summary

lava-vmdebootstrap installation dependencies
--------------------------------------------

::

  $ apt-get install debootstrap extlinux qemu-utils parted mbr kpartx python-cliapp

Example invocation:
-------------------

::

  $ sudo ./lava-vmdebootstrap --image=myimage.img

Mounting KVM images manually
----------------------------

Using losetup and kpartx::

  # losetup /dev/loop0 foo.img
  # kpartx -av /dev/loop0
  # mount /dev/mapper/loop0p1 /mnt
  ...
  # unmount /mnt
  # kpartx -dv /dev/loop0
  # losetup -d /dev/loop0

Alternatively, whilst the image still exists as a device,
kpartx can be used to identify the offset::

  $ sudo kpartx -l foo.img
  loop0p1 : 0 1949696 /dev/loop0 2048

Running LAVA with a KVM image
=============================

KVM device configuration
------------------------

Add the kvm device type and kvm01 device to your LAVA server via the Django admin interface.

Create the kvm device configuration file::

  $ cat ./devices/kvm01.conf
  device_type = kvm
  root_part = 1

root_part is needed so that the offset can be calculated using parted.

Manual invocation
-----------------

Sample JSON for a KVM image::

  {
    "timeout": 18000,
    "job_name": "kvm-test",
    "logging_level": "DEBUG",
    "device_type": "kvm",
    "target": "kvm01",
    "actions": [
      {
        "command": "deploy_linaro_image",
        "parameters": {
          "image": "file:///tmp/foo.img"
          }
      },
      {
        "command": "boot_linaro_image"
      }
    ]
  }

Running via lava-dispatch
-------------------------

Ensure that lava-dispatch is run as root or the image offset cannot be calculated.::

  $ sudo lava-dispatch kvm.json

