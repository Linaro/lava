# Device dictionary

The device dictionary is a [jinja2][jinja2] template that should extend one
[device-type template](./device-type-template.md).

While device-type templates are usually provided and maintained by LAVA, device
dictionaries are provided and maintained by the admin.

A device dictionary will contain device specific information like:

* connection command
* power On/off commands
* bootloader prompt
* ...

## Configuration file

Device dictionaries are stored on the server in
`/etc/lava-server/dispatcher-config/devices/<hostname>.jinja2`.

Admin could update device dictionaries using lavacli:

```shell
lavacli devices dict set qemu01 qemu01.jinja2
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
