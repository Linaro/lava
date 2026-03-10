# Flasher

The `flasher` deployment method downloads the specific images and runs a list of
commands defined in the device configuration to flash the images onto the DUT.
It can be used for devices that require custom flashing procedures.

```yaml
actions:
- deploy:
    to: flasher
    images:
      recovery_image:
        url: https://example.com/image.img.xz
        compression: xz
    timeout:
      minutes: 15
```

The device dictionary must define the
[flasher_deploy_commands](../../../configuration/device-dictionary.md#flasher_deploy_commands).

## images

A dictionary of named images to download. Each image accepts the standard
[artifact parameters](./index.md#artifacts).

### overlays

See [overlays](./index.md#overlays). The [LAVA overlay](./index.md#lava-overlay)
must be applied if the job definition contains tests.

## uniquify

Optional boolean. By default, LAVA saves each downloaded file in a separate
subdirectory named after image key to avoid filename collisions.

Set to `false` if the flash commands expect files in a flat directory:

```yaml
- deploy:
    to: flasher
    uniquify: false
    images:
      firmware0:
        url: https://example.com/firmware0.bin
      firmware1:
        url: https://example.com/firmware1.bin
```

## Sample job

This sample job demonstrates using a USB-SD-Mux with custom flashing commands
defined in the device dictionary to flash the Debian image onto the DUT's SD card.

```yaml
job_name: RPi3B flasher sample job
device_type: bcm2837-rpi-3-b-plus

priority: medium
visibility: public

timeouts:
  job:
    minutes: 30

actions:
- deploy:
    to: flasher
    images:
      recovery_image:
        url: https://raspi.debian.net/tested/20231109_raspi_3_bookworm.img.xz
        compression: xz
        format: ext4
        partition: 1
        overlays:
          lava: true
    timeout:
      minutes: 15

- boot:
    method: minimal
    auto_login:
      login_prompt: 'login:'
      username: root
    prompts:
    - 'root@rpi3-20231109:'
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
