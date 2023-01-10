# Deploying a Raspberry Pi4B as a LAVA worker

Due to the distributed nature of LAVA architecture, worker part of the software
does not require latest and most expensive hardware. LAVA lab is already using
it in it's own setup for particular instances.

Here we will provide a reference and how-to for deploying one such RPi4 as a
LAVA worker.

## Get the hardware

What you will need for a worker is:

* RPi4 with power supply
* SD card with min 8GB (only temporarily)
* SSD / Flash drive
* SATA(M.2, etc) to USB adapter
* FTDI USB to serial UART cable

There is a list of know working and also problematic [USB adapters](https://jamesachambers.com/raspberry-pi-4-usb-boot-config-guide-for-ssd-flash-drives/)
along with the more extensive setup instructions which we will cover here.

## Prepare the Pi

Download the [Raspberry Pi OS](https://www.raspberrypi.org/software/operating-systems/) and flash it onto an SD card.
Once you get to login prompt the user is `pi` and password is `raspberry`
then perform the following steps:

```shell
apt update
apt full-upgrade
rpi-update
reboot
sudo rpi-eeprom-update -d -a
reboot
```

After that launch the raspi-config:

```shell
raspi-config
```

In the menu, find the `Boot ROM Version` (it defers where it is depending on
the version of raspi-config, either under `Boot options` or
`Advanced settings`).
Select **Latest** version of boot ROM software. In the next menu, for a question "Reset boot ROM to defaults?", select **NO**.

Then in the same submenu select "Boot Order" and choose "USB Boot". That's
it.

## Prepare the SSD

Currently we only support a Debian images for LAVA installation (unless you'd
like to use docker).

Get the latest Debian image from [Tested images](https://raspi.debian.net/tested-images/) - download the one for the RPi 4 family. This is a good
stock image for a number of reasons, not least of which is that it already has
enable-uart set to 1 in the boot config.txt, which enables serial output.
The user for this image is root and there is no password.

Unpack it and “dd” it onto the SSD.
If everything is OK, you should be able to remove the SD card from th Pi and
boot the system from the SSD over USB.

We're now ready to install the LAVA worker.

## Installing LAVA worker

* Start with upgrading the system and installing the packages:

```shell
apt update && apt dist-upgrade
apt install net-tools wget gnupg curl ca-certificates
```

* Edit the /etc/hostname and /etc/hosts files with appropriate hostname / IP
address.
* Add the LAVA repo to apt:

```shell
echo "deb https://apt.lavasoftware.org/release bullseye main" > /etc/apt/sources.list.d/lava.list
```

* Add LAVA archive signing keys to apt:

```shell
curl -fsSL https://apt.lavasoftware.org/lavasoftware.key.asc | apt-key add -
```

* Install the lava-dispatcher package

```shell
apt update
apt install lava-dispatcher
apt dist-upgrade -t bullseye
```

## Auto-registration of worker (or token)

We need to tell LAVA master to `trust` this worker and there's two ways to
do this. You can either add the following line to `/etc/lava-server/settings.d/01-autoregister.yaml` on the LAVA master (remember to change the netmask for
the subnet where the Pi is):

```yaml
WORKER_AUTO_REGISTER_NETMASK: ["172.0.0.0/8"]
```

Or, alternatively you can add a token of your choice in the LAVA worker (Pi 4)
in `/etc/lava-dispatcher/lava-worker` settings and paste the same token in the
LAVA admin UI on the master in the worker section for this particular worker.

## Disable master/worker version mismatch checking

LAVA master rejects workers which do not run strictly the same version.
You can disable this in eg. `/etc/lava-server/settings.d/01-autoregister.yaml`

```yaml
ALLOW_VERSION_MISMATCH: true
```
Note: Keep in mind that the version check is here to prevent against strange
issues when version are not compatible. Like when the device-dictionary are
changing and the dispatcher depends on such changes.

## Setting up the server url

Once you have lava-worker running you need to point it to the LAVA server it
will connect to. Do this in `/etc/lava-dispatcher/lava-worker` on the Pi.

After that RPi4 worker should be visible in the LAVA server UI and marked as
**Online**.
