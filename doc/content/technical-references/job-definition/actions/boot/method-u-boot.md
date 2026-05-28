# U-Boot

The `u-boot` boot method boots the downloaded files using U-Boot commands.

```yaml
- boot:
    method: u-boot
    commands: nfs
    prompts:
    - '/ #'
```

## commands

Specifies a predefined set of U-Boot commands that LAVA will execute to boot
the device. The commands are templates where LAVA substitutes placeholders with
actual values, such as:

- File locations of downloaded kernel, ramdisk, and dtb files
- Network configuration details (e.g., `SERVERIP` for TFTP server address)
- NFS server location and mount paths (when using NFS boot)

See your device configuration for the complete list of supported commands.
Common command sets include:

| Command | Description |
| ------- | ----------- |
| `ramdisk` | Boot from kernel and ramdisk loaded via TFTP |
| `nfs` | Boot kernel via TFTP, mount root filesystem via NFS |
| `nbd` | Boot using Network Block Device |
| `usb` | Boot from USB storage |
| `sata` | Boot from SATA storage |

Certain elements of the command line are available for modification using the
[job context](../../../../introduction/glossary.md#job-context). For example,
NXP Layerscape platforms support booting from Alternate Bank, keeping Main Bank
safe. If you want to boot the board from Alternate Bank, you can do it by
adding context variable `uboot_altbank: true`. By default, its value is set to
`false`.

```yaml
context:
  uboot_altbank: true
```

## reset

By default, LAVA will reset the board power when executing this action. You can
skip this step by setting `reset: false`.

This is useful when the device is already booted into U-Boot from a previous
boot action (such as `fastboot`).

The following example demonstrates a workflow where U-Boot is first deployed
and booted via `fastboot`, then the `u-boot` boot method is used without
resetting.

```yaml
- deploy:
    to: fastboot
    docker:
      image: lavalabteam/adb-fastboot
      local: true
    images:
      boot:
        url: https://example.com/uboot.img
    timeout:
      seconds: 90

- boot:
    method: fastboot
    docker:
      image: lavalabteam/adb-fastboot
      local: true
    timeout:
      seconds: 30

# Boot with u-boot commands without resetting as device is already in U-Boot
- boot:
    method: u-boot
    reset: false
    commands: nfs
    prompts:
    - 'root@board:~#'
```

## Secondary media boot

When booting from secondary media (e.g., USB or SD card) that was deployed by a
prior deploy action, the following parameters tell U-Boot where to find the
kernel image within the deployed filesystem:

| Parameter | Type | Description |
| --------- | ---- | ----------- |
| `kernel_type` | `string` | Kernel image format: `image`, `uimage`, or `zimage` |
| `kernel` | `string` | Path to the kernel image on the media |
| `dtb` | `string` | Path to the device tree blob on the media |
| `ramdisk` | `string` | Path to the ramdisk on the media |
| `root_uuid` | `string` | UUID of the root partition on the media |
| `boot_part` | `int` | Partition number containing the boot files |

```yaml
- boot:
    method: u-boot
    commands: usb
    kernel_type: image
    kernel: /boot/Image
    dtb: /boot/board.dtb
    root_uuid: 1234abcd-5678-ef01-2345-6789abcdef01
    boot_part: 1
    prompts:
    - 'root@board:~#'
```

These parameters are only meaningful when the device configuration includes
`media` parameters for secondary boot support.

## See also

[Raspberry Pi (U-Boot) device setup](../../../../admin/basic-tutorials/device-setup/u-boot.md)
