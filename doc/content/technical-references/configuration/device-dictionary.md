# Device dictionary

The device dictionary is a [jinja2][jinja2] template that should extend one
[device-type template](./device-type-template.md).

While device-type templates are usually provided and maintained by LAVA, device
dictionaries are provided and maintained by the admin.

A device dictionary will contain device specific information like:

* connection command
* power on/off commands
* bootloader prompt
* character delays
* ...

See [Parameters](#parameters)

## Configuration file

Device dictionaries are stored on the server in
`/etc/lava-server/dispatcher-config/devices/<hostname>.jinja2`.

Admin could update device dictionaries using lavacli:

```shell
lavacli devices dict set qemu01 qemu01.jinja2
```

## Parameters

The variables you may define in a device dictionary depend on the
[device-type template](./device-type-template.md) it extends. Common
parameters include connection and power commands. See the device type template
and its base template for the full set of supported parameters.

### Commands

All the command parameters in this section accept either a single string or a
list of strings. When a list is used, LAVA executes each command in order.

#### power_on_command

Command to supply power to the device remotely. The device **must** start the
boot sequence when the `power_on_command` is called. If the DUT needs a button
to be pressed to boot, then the command to press the button should be part of
this one.

```jinja
{% set power_on_command =  [
    'laacli power 5v on',
    'laacli power 3v3 on'
] %}
```

#### power_off_command

Command to remove power from the device remotely.

```jinja
{% set power_off_command = [
    'laacli power 3v3 off',
    'laacli power 5v off'
] %}
```

#### soft_reboot_command

Command to run at a shell prompt on a running system to request a reboot (e.g.
`reboot` or `systemctl reboot`).

```jinja
{% set soft_reboot_command = 'reboot' %}
```

#### hard_reset_command

Command to cut power and then restore it remotely (e.g. via PDU or hub). You can
insert a delay using `sleep` between cutting and restoring power if the device
requires it.

```jinja
{% set hard_reset_command = ['usbrelay 1_2=0', 'sleep 1', 'usbrelay 1_2=1'] %}
```

#### pre_power_command

Ancillary command for special cases. Behavior and support depend on the
deployment method and device-type template.

```jinja
{% set pre_power_command = 'laacli usb 1 on' %}
```

#### pre_os_command

Ancillary command for special cases. Behavior and support depend on the
deployment method and device-type template.

```jinja
{% set pre_os_command = 'laacli usb 1 off' %}
```

### Connections

#### connection_command

Command to access the serial port of the device.

```jinja
{% set connection_command = 'telnet dispatcher03 7004' %}
```

#### connection_list

The list of hardware ports which are configured for serial connections to the device.

```jinja
{% set connection_list = ['uart0'] %}
```

#### connection_commands

A dictionary of the commands to start each connection.

```jinja
{% set connection_commands = {'uart0': 'telnet w1 7005'} %}
```

#### connection_tags

Each connection can include `tags` - extra pieces of metadata to describe the connection.

```jinja
{% set connection_tags = {'uart0': ['primary', 'telnet']} %}
```

There must always be one (and only one) connection with the `primary` tag, denoting
the connection that will be used for firmware, bootloader and kernel interaction.

Other tags may describe the *type* of connection, as extra information that LAVA
can use to determine how to close the connection cleanly when a job finishes
(e.g `telnet` and `ssh`).

### Device

Some devices or the elements of the device configuration can be exposed to the
LAVA test shell, where it is safe to do so. Each parameter must be explicitly
set in each device dictionary.

For ease of use, LAVA will directly export the content of the `device_info`,
`environment`, `static_info` and `storage_info` dictionaries into the test
shell environment. The dictionaries and lists will be unrolled, for example:

```jinja
{% set environment = {"RELAY_ADDRESS": "10.66.16.103", "REMOTE_SERIAL_PORT": "/dev/ttyUSB2"} %}
{% set device_info = [{'board_id': 'a2c22e48'}] %}
{% set static_info = [{"board_id": "S_NO81730000"}, {"board_id": "S_NO81730001"}] %}
{% set storage_info = [{'SATA': '/dev/disk/by-id/ata-ST500DM002-1BD142_W3T79GCW'}] %}
```

will become:

```shell
export RELAY_ADDRESS='10.66.16.103'
export REMOTE_SERIAL_PORT='/dev/ttyUSB2'
export LAVA_DEVICE_INFO_0_board_id='a2c22e48'
export LAVA_STATIC_INFO_0_board_id='S_NO81730000'
export LAVA_STATIC_INFO_1_board_id='S_NO81730001'
export LAVA_STORAGE_INFO_0_SATA='/dev/disk/by-id/ata-ST500DM002-1BD142_W3T79GCW'
```

The environment can be overridden in the job definition, see
[job environment](../job-definition/environment)

#### device_info

`device_info` is a list of dictionaries, where each dictionary value can contain
keys such as `board_id`, `usb_vendor_id`, `usb_product_id`, `wait_device_board_id`,
which can be made available to the Docker container for device specific tasks
dynamically, whenever the device is reset, using a `udev` rule.

```jinja
{% set device_info = [{'board_id': '8c5f2290'}] %}
```

#### environment

A dictionary containing device-specific shell variables, which will be available
in the LAVA test shell. These can be used, for example, to describe physical
hardware connections between the DUT and interfaces on the worker or other
addressable hardware.

```jinja
{% set environment = {
    'RELAY_ADDRESS': '10.66.16.103',
    'REMOTE_SERIAL_PORT': '/dev/ttyUSB2',
} %}
```

#### storage_info

A list of dictionaries, where each dictionary value can contain keys describing
the storage name (e.g. USB or SATA) and a value stating the device node of the
top level block device which is available to the test writer.

```jinja
{% set storage_info = [{'SATA': '/dev/disk/by-id/ata-ST500DM002-1BD142_W3T79GCW'}] %}
```

#### device_ip

A single fixed IPv4 address of this device. The value will be exported into the
test shell using
[`lava-target-ip`](../../user/basic-tutorials/test-definition.md#lava-target-ip).

```jinja
{% set device_ip = "10.66.16.24" %}
```

#### device_mac

Similar to `device_ip` but for a single MAC address. The value will be exported
into the test shell using
[`lava-target-mac`](../../user/basic-tutorials/test-definition.md#lava-target-mac).

```jinja
{% set device_mac = '00:02:F7:00:58:53' %}
```

### Character delays

LAVA supports specifying character delays in the deploy, boot, and test
actions to help with serial reliability (e.g. when the DUT or connection
drops or corrupts characters when input is sent too quickly). These are
device-specific, so they are best set in the device dictionary (or
device-type template).

The `deploy` and `boot` actions are affected more often than the `test`
action, because they interacts with firmware or bootloader processes where
input handling can be more limited than in a POSIX test environment.

#### deploy_character_delay

Set the number of milliseconds to add between each character of every
string sent to the DUT during the `deploy` action. This is useful for
deployment methods that use a connection (e.g. `vemsd`):

```jinja
{% set deploy_character_delay = 30 %}
```

#### boot_character_delay

Set the number of milliseconds to add between each character of every
string sent to the DUT during the `boot` action:

```jinja
{% set boot_character_delay = 20 %}
```

Some devices need more (e.g. 100 or 500 ms). For long delays, also consider
the overall boot timeout and set a minimum for the relevant boot action in
the device-type template.

#### test_character_delay

Set the number of milliseconds to add between each character of every
string sent to the DUT during the `test` action:

```jinja
{% set test_character_delay = 10 %}
```

!!! note
    LAVA also waits `test_character_delay` milliseconds before sending each
    test signal. The delay can be helpful on slow serial connections to avoid
    character interleaving with other inputs, such as kernel dmesg.

### Fastboot

The following variables can be used in fastboot device dictionary to configure
fastboot device.

#### adb_serial_number

A string to specify the serial number of the device in ADB mode.

```jinja
{% set adb_serial_number = '25564f71' %}
```

#### fastboot_serial_number

A string to specify the serial number of the device in fastboot mode.

```jinja
{% set fastboot_serial_number = '25564f71' %}
```

#### fastboot_auto_detection

A boolean. When `true`, LAVA tries to detect the device serial number
automatically.

```jinja
{% set fastboot_auto_detection = true %}
```

!!! note
    `fastboot_auto_detection` assumes the ADB serial number and fastboot serial
    number are the same for the same device.

When `false` or unset, you must set `adb_serial_number` and
`fastboot_serial_number` explicitly.

#### fastboot_options

A list of strings, used for specifying additional options to the `fastboot` command.

```jinja
{% set fastboot_options = ['-S', '256M'] %}
```

#### flash_cmds_order

A list of strings, used for specifying the order in which the images should be
flashed to the DUT using the `fastboot` command.

```jinja
{% set flash_cmds_order = ['update', 'ptable', 'partition', 'hyp', 'modem',
                           'rpm', 'sbl1', 'sbl2', 'sec', 'tz', 'aboot',
                           'boot', 'rootfs', 'vendor', 'system', 'cache',
                           'userdata', ] %}
```

#### fastboot_sequence

A list of strings. In practice, you only need to set the list to use one of the
following method for most of the device types, then LAVA will populate and
execute the corresponding action.

##### boot

Runs `fastboot boot <boot-image>`, loading the `boot` image from the preceding
deploy action directly into RAM and executing it.

```jinja
{% set fastboot_sequence = ['boot'] %}
```

##### reboot

Runs `fastboot reboot`, rebooting the device into the OS from its previously
flashed partitions. This is the typical path when all images (including `boot`)
were flashed during the deploy action.

```jinja
{% set fastboot_sequence = ['reboot'] %}
```

##### no-flash-boot

Same behaviour as `boot` at boot time — the image is loaded into RAM via
`fastboot boot`. Additionally, during the deploy phase, LAVA skips flashing the
`boot` partition even if a `boot` image was listed under `images` in the deploy
action.

```jinja
{% set fastboot_sequence = ['no-flash-boot'] %}
```

## Examples

### Beaglebone-black

```jinja
{% extends 'beaglebone-black.jinja2' %}

{% set connection_command = 'telnet dispatcher02 7001' %}

{% set hard_reset_command = 'pdu_control -host pdu20 --cmd reboot --port 10' %}
{% set power_off_command = 'pdu_control --host pdu20 --cmd off --port 10' %}
{% set power_on_command = 'pdu_control --host pdu20 --cmd on --port 10' %}

```

### dragonboard-410c

```jinja
{% extends 'dragonboard-410c.jinja2' %}

{% set connection_command = 'telnet dispatcher03 7004' %}

{% set adb_serial_number = '8c5f2290' %}
{% set fastboot_serial_number = '8c5f2290' %}

{# OTG power control #}
{% set pre_power_command = 'hub_control -n dispatcher03-hub01 -m sync -u 02' %}
{% set pre_os_command = 'hub_control -n dispatcher03-hub01 -m off -u 02' %}
{% set hard_reset_command = [
        'hub_control -n dispatcher03-hub01 -m off -u 02',
        'pdu_control --host pdu04 --command reboot --port 19 --delay 50',
        'hub_control -n dispatcher03-hub01 -m sync -u 02'] %}
{% set power_on_command = 'pdu_control --host pdu04 --command on --port 19' %}
{% set power_off_command = ['pdu_control --host pdu04 --command off --port 19',
                            'hub_control -n dispatcher03-hub01 -m off -u 02'] %}

{% set device_info = [{'board_id': '8c5f2290'}] %}
{% set flash_cmds_order = ['update', 'ptable', 'partition', 'hyp', 'modem',
                           'rpm', 'sbl1', 'sbl2', 'sec', 'tz', 'aboot',
                           'boot', 'rootfs', 'vendor', 'system', 'cache',
                           'userdata', ] %}
{% set device_ip = "10.7.0.74" %}
```

--8<-- "refs.txt"
