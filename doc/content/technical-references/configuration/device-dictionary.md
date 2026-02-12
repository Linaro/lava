# Device dictionary

The device dictionary is a [jinja2][jinja2] template that should extend one
[device-type template](./device-type-template.md).

While device-type templates are usually provided and maintained by LAVA, device
dictionaries are provided and maintained by the admin.

A device dictionary will contain device specific information like:

* connection command
* power On/off commands
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
