# Raspberry Pi (U-Boot)

This guide covers setting up Raspberry Pi devices (RPi3, RPi4, RPi5) that use
U-Boot as their bootloader in LAVA.

LAVA has extensive support for devices that use U-Boot as their bootloader,
allowing you to deploy kernel, ramdisk, device tree blob (DTB), and other
files via `tftp` deploy action, and boot them using `u-boot` boot method.

## Hardware setup

Before adding a Raspberry Pi to LAVA, you need to set up the required hardware.
This includes configuring the serial console, network connectivity, power
control, and preparing an SD card with U-Boot installed.

### Serial console

[Setup serial console](common.md#serial-console).

For Raspberry Pi, connect the USB to serial adapter to the GPIO pins:

| RPi GPIO Pin | Signal | USB-Serial Adapter |
|--------------|--------|--------------------|
| Pin 6        | GND    | GND                |
| Pin 8        | TXD    | RXD                |
| Pin 10       | RXD    | TXD                |

### Network connectivity

The Raspberry Pi must be able to access the LAVA worker’s TFTP and NFS services
in order to download boot files and mount the root filesystem over NFS.
Therefore, the Raspberry Pi should be connected to the same network as the
LAVA worker.

### Power control

[Setup power control](common.md#power-control).

### SD Card

You need to prepare an SD Card with U-Boot configured to:

1. Display an interrupt prompt (e.g., `Hit any key to stop autoboot`)
2. Wait at least 5 seconds, so LAVA can match and interrupt the autoboot
3. Support TFTP boot commands

You can follow [this guide](https://docs.lavacloud.io/devices/rpi-3-and-4.html#sdcard)
to flash your SD Card.

### See also

- [How LAA simplifies device setup for LAVA](https://docs.lavacloud.io/generality/laa.html)
- [RPi device setup with LAA](https://docs.lavacloud.io/devices/rpi-3-and-4.html)

## Creating device type

[Create the device type](common.md#create-device-type) using one of the
following names that match the existing device type templates:

| Raspberry Pi Model | Device Type Name | Architecture |
| ------------------ | ---------------- | ------------ |
| RPi 3 Model B (32-bit) | `bcm2837-rpi-3-b-32` | ARM32 |
| RPi 3 Model B (64-bit) | `bcm2837-rpi-3-b` | ARM64 |
| RPi 4 Model B | `bcm2711-rpi-4-b` | ARM64 |
| RPi 5 Model B | `bcm2712-rpi-5-b` | ARM64 |

## Creating device

Each Raspberry Pi device requires a device dictionary that specifies
device-specific settings such as serial connection and power control commands.
The device dictionary should extend the device type template and add the
device-specific configurations.

1. [Add the device](common.md#add-device) using the following settings:
    - **Device Type:** See device type name in the
    [above table](#creating-device-type) (e.g., `bcm2711-rpi-4-b`)
    - **Hostname:** A unique name (e.g., `rpi4-01`)
2. [Add the device configuration](common.md#add-device-configuration):

    ```jinja
    {% extends "<device_type>.jinja2" %}

    {% set connection_command = "telnet localhost <port>" %}

    {% set hard_reset_command = "<power_reset_command>" %}
    {% set power_off_command = "<power_off_command>" %}
    {% set power_on_command = "<power_on_command>" %}
    ```

    !!! note
        Replace all the placeholders marked with `<>` with their corresponding
        actual values.

## Sample job definitions

### Booting from NFS

```yaml
job_name: u-boot nfs
device_type: bcm2837-rpi-3-b-32

priority: medium
visibility: public

timeouts:
  job:
    minutes: 30

actions:
- deploy:
    to: tftp
    timeout:
      minutes: 15
    dtb:
      url: http://example.com/nfs/bcm2837-rpi-3-b-plus.dtb
    kernel:
      url: http://example.com/nfs/zImage
      type: zimage
    modules:
      url: http://example.com/nfs/modules.tar.xz
      compression: xz
    ramdisk:
      url: http://example.com/nfs/initrd.cpio.gz
      compression: gz
    nfsrootfs:
      url: http://example.com/nfs/full.rootfs.tar.xz
      format: tar
      overlays:
        kselftest:
          url: http://example.com/nfs/kselftest.tar.xz
          compression: xz
          format: tar
          path: /opt/kselftest

- boot:
    method: u-boot
    commands: nfs
    prompts:
    - '/ #'
    timeout:
      minutes: 5

- test:
    timeout:
      minutes: 5
    definitions:
    - from: inline
      repository:
        metadata:
          format: Lava-Test Test Definition 1.0
          name: health checks
        run:
          steps:
          - lava-test-case kernel-info --shell uname -a
          - lava-test-case network-info --shell ip a
      name: health-checks
      path: inline/health-checks.yaml
```

### Booting from ramdisk

```yaml
device_type: bcm2837-rpi-3-b-32
job_name: u-boot boot ramdisk

priority: medium
visibility: public

timeouts:
  job:
    minutes: 15

actions:
- deploy:
    dtb:
      url: http://example.com/ramdisk/bcm2837-rpi-3-b.dtb
    kernel:
      type: zimage
      url: http://example.com/ramdisk/zImage
    ramdisk:
      compression: gz
      url: http://example.com/ramdisk/rootfs.cpio.gz
    timeout:
      minutes: 3
    to: tftp

- boot:
    method: u-boot
    commands: ramdisk
    prompts:
    - '/ #'
    timeout:
      minutes: 5

- test:
    timeout:
      minutes: 5
    definitions:
    - from: inline
      repository:
        metadata:
          format: Lava-Test Test Definition 1.0
          name: health checks
        run:
          steps:
          - lava-test-case kernel-info --shell uname -a
          - lava-test-case network-info --shell ip a
      name: health-checks
      path: inline/health-checks.yaml
```

--8<-- "refs.txt"
