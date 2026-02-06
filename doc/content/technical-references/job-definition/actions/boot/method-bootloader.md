# Bootloader

The `bootloader` boot method is used to power-on the DUT, interrupt the
bootloader, and wait for the bootloader prompt.

```yaml
- boot:
    method: bootloader
    bootloader: u-boot
    commands: []
```

## bootloader

In order to interrupt the bootloader, the bootloader type should be specified
in the `bootloader` parameter.

!!! note
    The bootloader method type should match a boot method supported by the
    given device type. For example `fastboot`, `minimal`, `pyocd`, `u-boot`, etc.

## commands

The `commands` parameter is required but can be kept empty. If some commands
should be sent to the bootloader before the end of the action, provide them as
a list in the `commands` parameter.

See also [commands](./common.md#commands)

## use_bootscript

When set to `true`, the boot commands are written to an iPXE script (`script.ipxe`)
stored in the TFTP directory. The bootloader then executes a chainload command
to run this script (e.g., `dhcp net0; chain tftp://<worker_ip>/<path>/script.ipxe`).

```yaml
- boot:
    method: ipxe
    commands: ramdisk
    use_bootscript: true
```

!!! note
    A prior `tftp` deploy action is required.

## reset_connection

By default, LAVA will reset the previous connection when executing this action.
You can skip this step by setting `reset_connection: false`.

```yaml
- boot:
    method: bootloader
    bootloader: u-boot
    reset_connection: false
```

## reset_device

By default, LAVA will reset the board power when executing this action. You can
skip this step by setting `reset_device: false`.

```yaml
- boot:
    method: bootloader
    bootloader: u-boot
    reset_device: false
```
