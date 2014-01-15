Configuring and Using the SD-Mux
================================

An sd-mux is a piece of hardware that's been created that allows a single
SD card to be controlled by two different card readers. Access between the
card readers is mutually exclusive and requires them to work in conjunction
with each other. This provides an extremely useful way to deal with embedded
system use cases for devices that boot from an SD card.

LAVA uses sd-mux devices to allow running unmodified test images including
bootloaders on test devices. This is a big improvement to the
`master image`_ approach.

.. _`master image`: http://lava.readthedocs.org/en/latest/lava-image-creation.html#preparing-a-master-image

.. image:: sdmux.png

Manual Usage
------------

Before deploying to LAVA, its probably best to understand the mechanics of
the actual device and ensure its functioning. A setup like in the image above
is assumed where:

 * the target end of the mux is plugged into a dev board
 * the host end is plugged into a USB SD card reader
 * the SD card reader is plugged into a USB hub that's plugged into the host

With that in place, the device can be identified. The easiest way to do this
is:

 * ensure the target device is off
 * cause a usb plug event on the host (unplug and plug the usb hub)

At this point, "dmesg" should show what device this SD card appeared under
like "/dev/sdb". Since these entries can change, the sd-mux code needs to know
the actual USB device/port information. This can be found with the sdmux.sh
script by running::

  ./sdmux.sh -f /dev/sdb
  Finding id for /dev/sdb
  Device: /devices/pci0000:00/0000:00:1d.7/usb2/2-1/2-1.1
  Bus ID: 2-1.1

The key piece of information is "Bus ID: 2-1.1". This is required by the sdmux
script to turn on/off the USB port with access to the device. To turn the
device off which gives the target safe access run::

  ID=2-1.1
  ./sdmux -d $ID off

At this point the target can be powered on and use the device. After powering
off the target, the sd-card can be access on the host with::

  ./sdmux -d $ID on

This command will also print out the device entry like "/dev/sdb" to STDOUT

Deploying in LAVA
-----------------

In order for the dispatcher's sd-mux driver to work a few fields must be added
the device config::

  # client_type required so that the sdmux driver will be used
  client_type = sdmux
  # this is the ID as discovered above using "sdmux.sh -f"
  sdmux_id = 2-1.1
  # sdmux_version is optional, but can be used to help identify which hardware
  # revision this target is using.
  sdmux_version = 0.01-dave_anders
  # power on/off commands are also required
  power_on_cmd = /usr/local/bin/pdu_power.sh 1 1
  power_off_cmd = /usr/local/bin/pdu_power.sh 1 0

About ADB
---------

An issue has been discovered but not yet resolved upstream with ADB. The
way the ADB daemon runs on the host prevents the sdmux.sh script from
properly managing the device. Details and the proposed fix can be found
here: https://android-review.googlesource.com/#/c/50011/

Debugging Problems
------------------

Figuring out why things aren't working can be tricky. The key thing to keep
in mind for the current revision of sd-mux hardware is:

 * The host can only access the sd-card if the target is powered off
 * The target can only access the sd-card if the host's sd-card reader isn't
   supplying any current to the mux (ie the USB port should be off)

Additionally, a tricky situation can arise if the host is providing some small
amount of current. It seems u-boot can access the sd-card to pull the kernel.
However, the kernel which tries to operate the sd-card at a higher speed will
fail to mount the root file system.

To really debug things you should open 2 terminals. Terminal 1 should be serial
console session to your target. Terminal 2 can be used to toggle on/off target
and toggle on/off the sdmux. Here's an example of how to play with things::

  # from terminal 2, as root
  export DEVICE=<your device id as described above>
  alias muxon='<path to lava-dispatcher>/lava_dispatcher/device/sdmux.sh -d $DEVICE on'
  alias muxoff='<path to lava-dispatcher>/lava_dispatcher/device/sdmux.sh -d $DEVICE off'
  alias targeton='<your power on command>'
  alias targetoff='<your power off command>'

  # see if things work from the host
  targetoff
  muxon
  # the muxon will print out where the device is, like /dev/sdb

  # if you know your sd-card has partitions/files check with:
  fdisk -l /dev/sdc

  # now try mounting
  mount /dev/sdc1 /mnt ; ls /mnt
  umount /mnt

  # see if this image will run on the target
  muxoff
  targeton

  # at this point switch to terminal 1 to see if the device boots

The steps above can basically get repeated over and over to help narrow down
where things are breaking at.
