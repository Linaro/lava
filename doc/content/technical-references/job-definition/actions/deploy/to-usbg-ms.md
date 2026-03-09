# USB Gadget Mass Storage

The `usbg-ms` deployment method exposes the download disk image to the DUT as a
USB mass storage device using the
[Linux USB Mass Storage Gadget](https://docs.kernel.org/usb/mass-storage.html).
USB mass storage emulation support is required on the LAVA worker, e.g.,
[using the LAA USB OTG port](https://docs.lavacloud.io/hardware/peripherals.html#laa-usb).
For the DUT, the emulated virtual device functions as a regular block device,
similar to a USB stick.

Note that the [usbg_ms_commands](../../../configuration/device-dictionary.md#usbg-ms)
device configuration is required for using the deployment method.

```yaml
- deploy:
    to: usbg-ms
    image:
      url: https://raspi.debian.net/tested/20231109_raspi_4_bookworm.img.xz
      compression: xz
    timeout:
      minutes: 5
```

## image

### url

See [url](./index.md#url).

### compression

See [compression](./index.md#compression).

If the image is compressed, the compression method **must** be specified.

## overlays

For applying overlays to the image, see [Overlays](./index.md#overlays).

The [LAVA overlay](./index.md#lava-overlay) is required when the job definition
contains tests.

## timeout

See [timeout](../../timeouts.md)

## Life cycle

By default, the gadget is removed at the end of the job. You can use the built-in
`usbg_ms_commands_disable` command to remove it earlier.

```yaml
- command:
    name: usbg_ms_commands_disable
```

See [RPi4b secondary media deployment example](./to-secondary.md#sample-job) for
how it is used in a pipeline.

## Sample job

This sample job demonstrates a highly efficient way to boot and test a disk image
via USB boot, as emulating a USB device is much faster than flashing a physical
USB disk.

```yaml
job_name: RPi4B USBG MS sample job
device_type: bcm2711-rpi-4-b

visibility: public
priority: medium

timeouts:
  job:
    minutes: 15
  connection:
    minutes: 2

actions:
- deploy:
    to: usbg-ms
    image:
      url: https://raspi.debian.net/tested/20231109_raspi_4_bookworm.img.xz
      compression: xz
      format: ext4
      partition: 1
      overlays:
        lava: true
    timeout:
      minutes: 5

- boot:
    method: minimal
    auto_login:
      login_prompt: 'login:'
      username: root
    prompts:
    - 'root@rpi4-20231108:'
    timeout:
      minutes: 5

- test:
    definitions:
    - from: inline
      repository:
        metadata:
          format: Lava-Test Test Definition 1.0
          name: test-definition-example
        run:
          steps:
          - lava-test-case run-uname-a --shell uname -a
          - lava-test-case check-os-id --shell 'cat /etc/os-release | grep "ID=debian"'
      path: inline/test-definition-example.yaml
      name: test-suite-example
    timeout:
      minutes: 5
```

--8<-- "refs.txt"
