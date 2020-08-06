# Deploying a Raspberry Pi4B as a LAVA worker

Due to the distributed nature of LAVA architecture, worker part of the software
does not require latest and most expensive hardware. LAVA lab is already using
it in it's own setup for particular instances.

Here we will provide a reference and how-to for deploying one such RPi4 as a
LAVA worker.

## Get the hardware

What you will need for a worker is:

* RPi4 with power supply
* SD card
* SSD / Flash drive
* SATA(M.2, etc) to USB adapter
* FTDI USB to serial UART cable

There is a list of know working and also problematic USB adapters [here](https://jamesachambers.com/raspberry-pi-4-usb-boot-config-guide-for-ssd-flash-drives/)
along with the more extensive setup instructions which we will cover here.

## Prepare the Pi

First of all, get the latest Debian image from [Tested images](https://raspi.debian.net/tested-images/) - download the one for the RPi 4 family. This is a good
stock image for a number of reasons, not least of which is that it already has
enable-uart set to 1 in the boot config.txt, which enables serial output.

Unpack it and “dd” it to the micro sd-card.

Connect serial and power up the board - note that it takes a while before you
see any serial output at all. Once you get to the login prompt the user is
“root” and there is no password.

## Booting the Pi from SD card

* Boot the Pi from SD card (without connecting the SSD).
* Connect the SSD via USB to the Pi
* Connect to the serial terminal (alternatively you can use ethernet and
connect via SSH). Username is `root` while password is an empty string.

```shell
apt update
apt install usbutils rsync
fdisk /dev/sda
```

* Create new partition via fdisk tool
* Create an ext4 filesystem via:

```shell
mke2fs -t ext4 -L SSD1ROOTFS /dev/sda1
```

* Make sure that cmdline.txt contains the correct rootfs label:

```shell
cd /boot/firmware
cp cmdline.txt cmdline.sd
```

* Edit cmdline.txt "root=LABEL=SSD1ROOTFS"
* We need to back it up for later:

```shell
cp cmdline.txt cmdline.usb
```

* Edit /etc/fstab "LABEL=SSD1ROOTFS"

```shell
mount /dev/sda1 /mnt
rsync -axv / /mnt
umount /mnt
```

!!! warning "check cmdline.txt"
    Always check /boot/firmware/cmdline.txt before a reboot

```shell
reboot
```

* Double check that we're using rootfs from the SSD:

```shell
findmnt -n -o SOURCE /
```

We're now ready to install the LAVA worker.

## Installing LAVA worker

* Start with upgrading the system and installing the packages:

```shell
apt update && apt dist-upgrade
apt install net-tools wget gnugpg curl
```

* Edit the /etc/hostname and /etc/hosts files with appropriate hostname / IP
address.
* Add the LAVA repo to apt:

```shell
echo "deb https://apt.lavasoftware.org/release buster main" > /etc/apt/sources.list.d/lava.list
```

* Add LAVA archive signing keys to apt:

```shell
curl -fsSL https://apt.lavasoftware.org/lavasoftware.key.asc | apt-key add -
```

* Install the lava-dispatcher package

```shell
apt update
apt install lava-dispatcher
apt dist-upgrade -t buster
```

!!! warning "check cmdline.txt"
    Upgrade command might overwrite your cmdline.txt if there is a new kernel
    package available so before rebooting you might want to check it out and
    restore from the backup we created previously.

## Setting up the master and exchanging certificates

Once you have lava-worker running you need to point it to the LAVA master it
will connect to and also set up certificates if the LAVA master is using
encryption. These setting steps are available [here](/admin/advanced-tutorials/remote-workers/#create-slave-certificates).

After that RPi4 worker should be visible in the LAVA master UI and marked as
**Online**.
