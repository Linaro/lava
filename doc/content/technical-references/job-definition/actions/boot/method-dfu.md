# DFU

The `dfu` boot method flashes and boots devices using the
[USB DFU (Device Firmware Upgrade)](https://en.wikipedia.org/wiki/USB#Device_Firmware_Upgrade_mechanism)
protocol.

```yaml
- boot:
    method: dfu
    timeout:
      minutes: 10
```

!!! note
    Images should be deployed using the [`tmpfs`](../deploy/to-tmpfs.md) deploy
    action before using this boot method. Each image entry in the deploy action
    should include an `image_arg` containing the DFU `--alt` and `--download`
    arguments.

## Installation

The boot method invokes `dfu-util` on the worker to download images to the
device over USB. The utility must be installed on the LAVA worker.

```shell
sudo apt-get install dfu-util
```

## Configuration

To add a new device, see [DFU](../../../configuration/device-dictionary.md#dfu).

To add a new device type, see [DFU](../../../configuration/device-type-template.md#dfu).

## Example jobs

### Hardware DFU

```yaml
device_type: arduino101
job_name: zephyr dfu

timeouts:
  job:
    minutes: 15
  action:
    minutes: 5
  actions:
    lava-test-monitor:
      seconds: 300
    wait-usb-device:
      seconds: 20
    flash-dfu:
      seconds: 60
  connections:
    lava-test-monitor:
      seconds: 300

priority: medium
visibility: public

actions:
- deploy:
    timeout:
      minutes: 3
    to: tmpfs
    images:
      app:
        image_arg: --alt x86_app --download {app}
        url: https://storage.lavacloud.io/health-checks/arduino_101/app_kernel-zephyr.bin
      sensor_core:
        image_arg: --alt sensor_core --download {sensor_core}
        url: https://storage.lavacloud.io/health-checks/arduino_101/sensor_core-arc.bin
      ble_core:
        image_arg: --alt ble_core --download {ble_core}
        url: https://storage.lavacloud.io/health-checks/arduino_101/ble_core-image.bin

- boot:
    method: dfu
    timeout:
      minutes: 10

- test:
    monitors:
    - name: simple-service
      start: S I M P L E   S E R V I C E    M E A S U R E M E N T S
      end: M A I L B O X   M E A S U R E M E N T S
      pattern: '\| (?P<test_case_id>[a-z ]+) +\| +(?P<measurement>\d+)\|'
```

### U-Boot DFU

```yaml
device_type: rzn1
job_name: flash rzn1 using u-boot dfu

timeouts:
  job:
    minutes: 10
  action:
    minutes: 5
  connection:
    minutes: 2
priority: medium
visibility: public

actions:
- deploy:
    namespace: dfu
    to: tmpfs
    images:
      sf_fsbl:
        image_arg: --alt sf_fsbl --download {sf_fsbl}
        url: http://.../rzn1d-snarc-fsbl-secmon.img
      sf_uboot0:
        image_arg: --alt sf_uboot0 --download {sf_uboot0}
        url: http://.../u-boot-lces2-ddr.itb
      sf_uboot1:
        image_arg: --alt sf_uboot1 --download {sf_uboot1}
        url: http://.../u-boot-lces2-ddr.itb
      n_kernel1:
        image_arg: --alt n_kernel1 --download {n_kernel1}
        url: http://.../fitImage-1.0-r0-rzn1-snarc.itb

- command:
    namespace: dfu
    name: set_boot_to_nand

- boot:
    namespace: dfu
    method: dfu
    timeout:
      minutes: 10

- command:
    namespace: test
    name: set_boot_to_qspi

- deploy:
    namespace: test
    to: overlay

- boot:
    namespace: test
    connection-namespace: dfu
    method: bootloader
    bootloader: u-boot
    prompts: ["=>"]
    commands: ["run linux_bestla"]

- boot:
    namespace: test
    timeout:
      minutes: 5
    method: minimal
    reset: false
    auto_login:
      login_prompt: 'login:'
      username: 'root'
      password_prompt: "Password:"
      password: "P@ssword-1"
      login_commands:
      - 'P@ssword-1'
      - 'azertAZERT12345'
      - 'azertAZERT12345'
      - 'azertAZERT12345'
    prompts:
    - "root@rzn1-snarc:~# "
    - "root@rzn1-snarc:/tmp# "
    - "Current password: "
    - "New password: "
    - "Retype new password: "
    transfer_overlay:
      download_command: unset http_proxy ; dhclient eth1 ; cd /tmp ; wget
      unpack_command: tar -C / -xzf

- test:
    namespace: test
    definitions:
    - repository: https://github.com/Linaro/test-definitions
      from: git
      path: automated/linux/busybox/busybox.yaml
      name: busybox
    timeout:
      minutes: 5
```
