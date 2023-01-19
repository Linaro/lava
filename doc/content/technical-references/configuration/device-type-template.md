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

--8<-- "refs.txt"

## Base templates

Every device-type template should inherit from `base.jinja2` which contains
many default structures.

For simplicity multiple base templates are provided for the most common bootloaders:

* `base-barebox.jinja2`
* `base-depthcharge.jinja2`
* `base-edk2.jinja2`
* `base-fastboot.jinja2`
* `base-grub.jinja2`
* `base-uboot.jinja2`

## Examples

For most device-types, extending a base template should be enough.

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
