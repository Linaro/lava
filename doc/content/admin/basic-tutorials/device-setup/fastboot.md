# Dragonboard 410c (fastboot)

This guide covers setting up devices that use the fastboot protocol for
deployment and booting in LAVA, such as the DragonBoard 410c.

LAVA uses `fastboot` to deploy images to the device partitions and to boot the
device. LAVA supports running fastboot directly from the worker host or within a
Docker container. The Docker option is recommended as it allows using custom
fastboot binaries and provides better isolation.

## Hardware setup

Ensure your device is connected to the LAVA worker properly and prepared for
fastboot deployment and booting.

1. [Setup power control](common.md#power-control).
2. [Setup serial console](common.md#serial-console).

    Connect the USB to serial adapter adapter to the DB410c's Low Speed
    Expansion Connector UART1:

    | DB410c Pin | Signal | USB-Serial Adapter |
    |------------|--------|--------------------|
    | Pin 1      | GND    | GND                |
    | Pin 11     | TXD    | RXD                |
    | Pin 13     | RXD    | TXD                |

    A picture of the FTDI cable connected to the DragonBoard 410c is shown below:

    ![db410c-uart1](./db410c-uart1.jpg)

3. Connect the device's micro USB OTG port to your LAVA worker USB port.
4. Setup USB Ethernet.

    The board does not have an Ethernet port. If you want to use a USB Ethernet
    adapter, additional setup is required.

    The DragonBoard 410c hardware design prevents simultaneous use of the micro
    USB (device mode) and USB Type A (host mode) ports; they are mutually
    exclusive.

    To support both fastboot (device mode) and USB Ethernet (host mode), you
    must be able to toggle the OTG connection. This is typically achieved by connecting
    the OTG port to the LAVA worker through a controllable smart USB hub. The
    commands for the switches can be provided via the `pre_power_command` and
    `pre_os_command` variables in device dictionary. In the job definition, you
    can use the variable names in the
    [`command`](../../../technical-references/job-definition/actions/command.md)
    action to issue the commands.

5. Set dip switch 2 to ON position for booting from SD card or eMMC.
6. If needed, flash or upgrade device FW and partition table. These
[artifacts](https://storage.lavacloud.io/artifacts/dragonboard-410c/) can be used.
7. Ensure that the device boots to fastboot mode on every power-on. For additional
instructions and troubleshooting, see
[dragonboard 41c guides](https://github.com/96boards/documentation/tree/master/consumer/dragonboard/dragonboard410c/guides).

In general, setting up a fastboot device with an LAA is much simpler. It is
essentially plug-and-play. For an example, see the
[DragonBoard 410c](https://docs.lavacloud.io/devices/dragonboard-410c.html#dragonboard-410c)
guide.

## Creating device type

[Create the device type](common.md#create-device-type) using the name
`dragonboard-410c`.

## Creating device

1. [Add the device](common.md#add-device) using the following settings:
    * **Device Type:** `dragonboard-410c`
    * **Hostname:** A unique name (e.g., `dragonboard-410c-01`)

2. [Add the device configuration](common.md#add-device-configuration).

    Device dictionary example for a DragonBoard 410c:

    ```jinja
    {% extends 'dragonboard-410c.jinja2' %}

    {% set adb_serial_number = 'a2c22e48' %}
    {% set fastboot_serial_number = 'a2c22e48' %}
    {% set device_info = [{'board_id': 'a2c22e48'}] %}

    {% set connection_command = 'telnet localhost 2002' %}

    {% set hard_reset_command = ['usbrelay 1_2=0', 'sleep 1', 'usbrelay 1_2=1'] %}
    {% set power_off_command = 'usbrelay 1_2=0' %}
    {% set power_on_command =  'usbrelay 1_2=1'%}
    {% set pre_power_command = 'usbrelay 1_3=1' %}
    {% set pre_os_command = 'usbrelay 1_3=0' %}

    {% set flash_cmds_order = ['update', 'ptable', 'partition', 'hyp', 'modem',
                               'rpm', 'sbl1', 'sbl2', 'sec', 'tz', 'aboot',
                               'boot', 'rootfs', 'vendor', 'system', 'cache',
                               'userdata', ] %}
    ```

    !!! note
        Update the example to use your device's actual serial number, serial
        connection and power control commands.

Another device dictionary example for
[dragonboard-410c](../../../technical-references/configuration/device-dictionary.md#dragonboard-410c).

For more about fastboot device configures, see the
[fastboot configurations](../../../technical-references/configuration/device-dictionary.md#fastboot).

## Sample job definition

```yaml
device_type: dragonboard-410c
job_name: db410c fastboot example

timeouts:
  job:
    minutes: 30

priority: medium
visibility: public

actions:
- command:
    name: pre_power_command
    timeout:
      minutes: 1

- deploy:
    to: fastboot
    docker:
      image: linaro/noble-adb-fastboot
      local: true
    images:
      boot:
        url: https://storage.lavacloud.io/health-checks/dragonboard-410c/boot-linaro-buster-359.img.gz
        compression: gz
      rootfs:
        url: https://storage.lavacloud.io/health-checks/dragonboard-410c/rootfs-linaro-buster-359.img.gz
        compression: gz
        apply-overlay: true
    timeout:
      minutes: 15

- command:
    name: pre_os_command
    timeout:
      minutes: 1

- boot:
    method: fastboot
    docker:
      image: linaro/noble-adb-fastboot
      local: true
    prompts:
    - 'root@linaro-developer:~#'
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
