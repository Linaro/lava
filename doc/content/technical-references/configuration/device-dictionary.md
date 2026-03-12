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

#### static_info

A list of dictionaries describing static information. A common use case is
defining a file server address for URL substitution. For example:

```jinja
{% set static_info = [{'FILE_SERVER_IP': "10.192.244.104"}] %}
```

See also [URL placeholders](../job-definition/actions/deploy/index.md#url).

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

### Flasher

The following `flasher_deploy_commands` variable must be configured for using
the [flasher](../job-definition/actions/deploy/to-flasher.md) deployment method.

#### flasher_deploy_commands

A list of commands that LAVA executes on the worker for flashing images onto the
DUT. For example, using a USB-SD-Mux to write an image to the DUT's SD card:

```jinja
{% set flasher_deploy_commands = [
        '/root/.local/bin/usbsdmux /dev/sg1 host',
        'sleep 3',
        '/root/.local/bin/usbsdmux /dev/sg1 info',
        'dd if={RECOVERY_IMAGE} of=/dev/disk/by-id/usb-LinuxAut_sdmux_HS-SD_MMC_000000001156-0:0 bs=4M oflag=sync conv=nocreat',
        'sleep 3',
        '/root/.local/bin/usbsdmux /dev/sg1 client',
    ]
%}
```

The following placeholders can be used in the commands. LAVA substitutes them
with the actual values at runtime.

| Variable | Value |
| --- | --- |
| `{UPPER_CASE_IMAGE_KEY}` | Downloaded image path (e.g., `{RECOVERY_IMAGE}` for `images.recovery_image`) |
| `{POWER_ON_COMMAND}` | [`power_on_command`](#power_on_command) |
| `{POWER_OFF_COMMAND}` | [`power_off_command`](#power_off_command) |
| `{SOFT_REBOOT_COMMAND}` | [soft_reboot_command](#soft_reboot_command) |
| `{HARD_RESET_COMMAND}` | [`hard_reset_command`](#hard_reset_command) |
| `{PRE_OS_COMMAND}` | [`pre_os_command`](#pre_os_command) |
| `{PRE_POWER_COMMAND}` | [`pre_power_command`](#pre_power_command) |
| `{DEVICE_INFO}` | YAML dump of [`device_info`](#device_info) |
| `{STATIC_INFO}` | YAML dump of [`static_info`](#static_info) |

### JLink

#### board_id

The serial number of the JLink probe or target board.

```jinja
{% set board_id = '000380000008' %}
```

### Secondary media

Use `<media>_label` and `<media>_uuid` to configure a secondary media in your
device dictionary. The `/dev/disk/by-id/<media>_uuid` must exist on the LAVA
worker.

#### USB

```jinja2
{% set usb_label = 'SanDiskCruzerBlade' %}
{% set usb_uuid = 'usb-SanDisk_Cruzer_Blade_20060266531DA442AD42-0:0' %}
```

#### SATA

```jinja2
{% set sata_label = 'ST160LM003' %}
{% set sata_uuid = "ata-ST160LM003_HN-M160MBB_S2SYJ9KC102184" %}
```

#### SD

```jinja2
{% set sd_label = 'sdcard' %}
{% set sd_uuid = 'mmc-SD16G_0xda85ac89' %}
```

### SSH

SSH device can be configured using the following parameters.

```jinja
{% extends 'ssh.jinja2' %}

{% set ssh_host = '192.168.1.100' %}
{% set ssh_port = 22 %}
{% set ssh_user = 'root' %}
{% set ssh_identity_file = '/<path>/private_key' %}
```

#### ssh_host

Required. The hostname or IP address of the device.

```jinja
{% set ssh_host = '192.168.1.100' %}
```

#### ssh_port

The SSH port on the device. Defaults to `22`.

```jinja
{% set ssh_port = 2222 %}
```

#### ssh_user

The login user for SSH and SCP connections. Defaults to `root`.

```jinja
{% set ssh_user = 'testuser' %}
```

#### ssh_identity_file

Path to the SSH private key on the LAVA worker. The matching public key must be
added to the `~/.ssh/authorized_keys` file on the device for the SSH login
authentication.

```jinja
{% set ssh_identity_file = '/root/.ssh/id_rsa' %}
```

If this parameter is not defined, the insecure `lava` private key distributed
with LAVA is used by default. The corresponding public key is provided below.

```plain
ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDLsQXteu02Mvs8Srs8TI/XJqTnfoNDjT5zJVQNI6BqUvvaHSna0iZpcPln9lbmRwAkf84rZAP3eAn051l+GYcRAVAH3bu9HDA8XXIbA4EkCZJ9aCPX7jqtSTBLaIUH28JRPhvP6iZWvqSQck4OmoyrBaMJByBm5CaPR4IhpcAyORF88AGmRW/qFIZTxNm/z1JN/WO+4+C/uM07T+KuInAPBQCTY9pYk4Vd2tZ4msWMYuWs3uVKRdN8aTgyqeyOE3zmXN8Tr2r5uFU0SAe1ZmVnex3s9ZF4YhgmX9SUBuxQw/FjNUajx2D18x/+RQuWXxZOpPQ5ecAysDKROTFWl6QB lava insecure public key
```

### USBG MS

For using the [`usbg-ms`](../job-definition/actions/deploy/to-usbg-ms.md)
deployment method, the device dictionary must define the `usbg_ms_commands`
variable with `enable` and `disable` entries that accept a single string or a
list of strings.

```jinja
{% set usbg_ms_commands = {
    "enable": ["laacli usbg-ms on --image {IMAGE}"],
    "disable": ["laacli usbg-ms off"],
} %}
```

#### enable

The commands for setting up the USB gadget.

The `enable` commands should contain the `{IMAGE}` placeholder which LAVA
replaces with the path to the downloaded image file.

#### disable

The commands for removing the USB gadget.

### UUU

The following variables should be used to configure UUU devices for using
[`uuu`](../job-definition/actions/boot/method-uuu.md) boot method to flash
these devices.

#### uuu_usb_otg_path

The USB OTG path of the device.

```jinja
{% set uuu_usb_otg_path = '2:143' %}
```

The path can be obtained using the command below:

```shell
$ uuu -lsusb
uuu (Universal Update Utility) for nxp imx chips -- libuuu_1.3.102-1-gddf2649
Connected Known USB Devices
    Path	 Chip	 Pro	 Vid	 Pid	 BcdVersion
    ==================================================
    2:143	 MX8MQ	 SDP:	 0x1FC9	0x012B	 0x0001
```

Multiple paths can be provided as a list:

```jinja
{% set uuu_usb_otg_path = ['1:143', '2:143'] %}
```

#### uuu_usb_otg_path_command

The command allows running a custom command on the worker to find the OTG paths
on the LAVA worker at runtime so you don't have to modify the device template
for changing device or USB port. In these cases, you will need to update the
command to send the new paths.

```jinja
{% set uuu_usb_otg_path_command = ['echo', '2:143'] %}
```

For multiple OTG paths, your command must print a well formatted usb path
accepted by `uuu` on each line with no new-line at the end of the output.

```jinja
{% set uuu_usb_otg_path_command = ['echo', '-ne', '1:143\n2:143'] %}
```

!!! note
    In practice, the command would be a script that runs on the LAVA worker to
    query and output the OTG paths in the required format, rather than a hardcoded
    `echo` in the examples.

!!! warning
    If `uuu_usb_otg_path` is not set or does not match the expected format,
    LAVA falls back to `uuu_usb_otg_path_command`. You must provide one of them
    in your device dictionary.

#### uuu_corrupt_boot_media_command

Required. A list of commands to execute on the platform within U-Boot to corrupt
the primary boot media. On the next reboot, serial download protocol must be
available on the platform to flash future images using `uuu`.

```jinja
{% set uuu_corrupt_boot_media_command = ['mmc dev 1', 'mmc erase 0 0x400'] %}
```

#### uuu_power_off_before_corrupt_boot_media

In case U-Boot continuously restarts, it will interfere with interrupting U-Boot
while attempting to corrupt the boot media. Set this option to `true` to power
off the device before the boot media corrupting action.

```jinja
{% set uuu_power_off_before_corrupt_boot_media = true %}
```

#### uuu_docker_image

The Docker image used to run UUU commands. The image must contain the `uuu`
binary.

```jinja
{% set uuu_docker_image = 'atline/uuu:1.5.239' %}
```

!!! note
    A `docker` block in the job definition overrides this value. See
    [docker](../job-definition/actions/boot/method-uuu.md#docker).

#### uuu_remote_options

When the UUU device is not directly connected to the LAVA worker, you can use
this parameter to provide the Docker client options for running `uuu` inside a
container on a remote machine.

```jinja
{% set uuu_remote_options = '--tlsverify --tlscacert=/certs/ca.pem --tlscert=/certs/cert.pem --tlskey=/certs/key.pem -H 10.192.244.5:2376' %}
```

See the Docker documentation for [remote access](https://docs.docker.com/engine/daemon/remote-access/)
and [TLS protection](https://docs.docker.com/engine/security/https/).

!!! note
    The minimal Docker version to run uuu is 19.03. This is due to a bug in
    earlier docker versions. See https://github.com/moby/moby/pull/37665.

### BCU

Most recent i.MX boards (imx8dxl, imx8mp, imx8ulp, imx93 as of july-2022)
support BCU, a remote control utility. BCU allows changing the board's boot
configuration (mainly SD card, eMMC or USB Serial Download Protocol) through a
serial interface. You can use the following parameters to configure BCU.

#### bcu_board_name

Required. The BCU board model name.

```jinja
{% set bcu_board_name = 'imx93evk11b1' %}
```

The list of supported board model can be obtained with `bcu lsboard`:

```shell
$ bcu lsboard
version bcu_1.1.128-0-ge7027dc

list of supported board model:

	imx8dxlevk
	imx8dxlevkc1
	imx8dxl_ddr3_evk
	imx8dxl_obx
	imx8mpevkpwra0
	imx8mpevkpwra1
	imx8mpevk
	imx8mpddr4
	imx8ulpevkb2
	imx8ulpevk9
	imx8ulpwatchval
	imx8ulpwatchuwb
	val_board_1
	val_board_2
	imx91qsb
	imx91evk11
	imx93evk11
	imx93evk11b1
	imx93wevk
	val_board_3
	imx93qsb
	imx93evk14
	imx95evk19
	imx95evk15
	imx952evk15
	imx952evk19
	nxp_custom
	nxp_custom_revB
	val_board_4
	val_board_5
	val_board_6
	val_board_8
	bench_imx8qm
	bench_imx8qm_revB
	bench_imx8qxp
	bench_imx8qxp_revB
	bench_imx8mq
	bench_imx6ull
	bench_mcu
	imx943evk19a0
	imx943evk19b1
	imx943obx
	val_board_7
	val_board_9
	val_board_10
	val_board_11
	val_board_12
done
```

#### bcu_board_id

The BCU board ID. It can be obtained with `bcu lsftdi`.

```jinja
{% set bcu_board_id = "1-3.2.1" %}
```

#### bcu_board_id_command

A command that prints the BCU board identifier at runtime, allowing per-worker
customisation. The command must print a single line with a valid board ID
accepted by `bcu`.

```jinja
{% set bcu_board_id_command = ['echo', '2-1.3'] %}
```

!!! warning
    If `bcu_board_id` is not set or does not match the expected format,
    LAVA falls back to `bcu_board_id_command`. You must provide one of them
    in your device dictionary.

#### additional_bcu_cleanup_commands

A list of additional BCU commands to run during `uuu` boot action cleanup.

```jinja
{% set additional_bcu_cleanup_commands = ["set_gpio ft_fta_sel 0"] %}
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
