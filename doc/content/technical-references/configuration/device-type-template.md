# Device-type template

The device-type template is a [jinja2][jinja2] template that will be extended
by [device dictionaries](./device-dictionary.md). The resulting file is the
device configuration file.

This [yaml][yaml] file is used by `lava-dispatcher` to know how to flash, boot
and communicate with a specific device.

## Configuration file

The device-type templates that are supported and provided by LAVA are stored
in `/usr/share/lava-server/device-types/`.

Admins could also provide their own device-type template using lavacli:

```shell
lavacli device-types template set qemu qemu.jinja2
```

Device-types provided by admins will be stored in
`/etc/lava-server/dispatcher-config/device-types/<name>.jinja2`.

LAVA will always look first in `/etc/lava-server/dispatcher-config/device-types/` and fallback to `/usr/share/lava-server/device-types/`.

This mean that admins can override every device-type templates, including the
ones provided by LAVA.

## Base templates

Every device-type template should inherit from `base.jinja2` which contains
many default structures.

For simplicity multiple base templates are provided for the most common bootloaders:

* `base-barebox.jinja2`
* `base-depthcharge.jinja2`
* `base-edk2.jinja2`
* `base-fastboot.jinja2`
* `base-grub.jinja2`
* `base-nxp-mcu.jinja2`
* `base-uboot.jinja2`

## Device types

For most device-types, extending a base template should be enough. Additional
requirements are documented below.

### DFU

`usb_vendor_id` and `usb_product_id` must be provided.

```jinja
{% extends "base-uboot.jinja2" %}

{% block body %}

board_id: '{{ board_id|default('LCES2-0x0000000000000000') }}'
usb_vendor_id: '045b'
usb_product_id: '0239'

{{ super() }}
{% endblock body %}
```

`deploy_dfu_commands` is required for entering DFU from u-Boot.

```jinja
{% set deploy_dfu_commands = deploy_dfu_commands|default(["nand erase.part fs1", "dfu"]) %}
```

### JLink

```jinja
  {% extends 'base-nxp-mcu.jinja2' %}

  {% set usb_vendor_id = '1366' %}
  {% set usb_product_id = '1024' %}

  {% set processor = 'MIMXRT1189XXX8' %}
  {% set supported_core_types = ['M33', 'M7'] %}

  {% set erase_command = ['erase', 'r', 'connect'] %}
  {% set reset_command = ['r'] %}

  {% set device_info = device_info|default([{'board_id': board_id, 'usb_vendor_id': usb_vendor_id, 'usb_product_id': usb_product_id}]) %}

  {% block jlink_options %}
  - '-if {{target_interface|default("SWD")}}'
  - '-speed {{ speed_ti|default(4000)}}'
  {% endblock jlink_options %}
```

You can configure the `erase_command` (default: `["erase"]`) and
`reset_command` (default: `["r"]`) parameters for each device type. These
parameters are mandatory for the jlink boot action, refer to the base
`base-nxp-mcu.jinja2` template for reference.

The `supported_core_types` parameter in the device type definition is
optional (default: `None`). It is used by JLink to connect to the board in cases
where the board has multiple cores, such as with the M33 and M7 cores. By
default, the connection is made using the first core in the list, which in this
case is the M33. To connect to the second core (e.g., M7), you need to use the
[`coretype`](../job-definition/actions/boot/method-jlink.md#coretype) parameter
in the JLink boot method.

!!! note
    The variables needed in `jlink_options` block should be provided in device
    dictionary.

### Raspberry Pi 4b

For the Raspberry Pi 4b, the device-type could look like the following. This
will only define some memory address and prompts that are specific to the board.

```jinja
{% extends 'base-uboot.jinja2' %}

{% set interrupt_ctrl_list = ['c'] %}
{% set action_timeout_bootloader_interrupt = '60' %}

{% set booti_kernel_addr = booti_kernel_addr|default('0x00080000') %}
{% set booti_ramdisk_addr = booti_ramdisk_addr|default('0x02700000') %}
{% set booti_dtb_addr = booti_dtb_addr|default('0x02400000') %}

{% set bootm_kernel_addr = bootm_kernel_addr|default('0x00080000') %}
{% set bootm_ramdisk_addr = bootm_ramdisk_addr|default('0x02700000') %}
{% set bootm_dtb_addr = bootm_dtb_addr|default('0x02400000') %}

{% set uboot_mkimage_arch = 'arm64' %}

{% set bootloader_prompt = bootloader_prompt|default('U-Boot>') %}
{% set console_device = console_device|default('ttyS1') %}
```

--8<-- "refs.txt"
