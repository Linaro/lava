# SATA

The `sata` deployment method writes an unchanged image to a SATA disk attached
to the DUT. The entire physical disk is available to the deployment.

Secondary relates to the requirement of a primary boot (for example a ramdisk or
NFS) which provides a working environment to write the image to the SATA disk.
The deployment itself works like the other
[secondary media](to-secondary.md) methods.

Not all devices support SATA media.

```yaml
- deploy:
    to: sata
    image:
      url: https://example.com/debian-arm64.img.gz
      compression: gz
    device: ST500DM002
    download:
      tool: /usr/bin/wget
      options: --no-check-certificate --no-proxy --connect-timeout=30 -S --progress=dot:giga -O - {DOWNLOAD_URL}
      prompt: HTTP request sent, awaiting response
    timeout:
      minutes: 30
```

The `image`, `images`, `device`, `download`, `writer`, `tool` and `uniquify`
parameters are described in [secondary media](to-secondary.md).

## Booting from SATA

Any bootloader inside the image is **not** used. Instead, the files needed to
boot are specified in the boot action, with `commands: sata`.

Booting from SATA is supported by the [u-boot](../boot/method-u-boot.md),
[grub](../boot/method-grub.md) and [grub-efi](../boot/method-grub-efi.md) boot
methods.

```yaml
- boot:
    method: u-boot
    commands: sata
    kernel: /boot/vmlinuz-6.12.0-arm64
    kernel_type: image
    ramdisk: /boot/initrd.img-6.12.0-arm64
    dtb: /boot/dtbs/juno.dtb
    root_uuid: UUID=159d17cc-697c-4125-95a0-a3775e1deabe
    boot_part: 1
    prompts:
    - 'root@debian:'
    timeout:
      minutes: 5
```

!!! note "Same namespace"
    With u-boot, the boot action must be in the same namespace as the `sata`
    deploy action, so that LAVA can check that the boot uses the device that was
    deployed.

### kernel

Required. The path, within the image, to the kernel which will be used by the
bootloader.

### kernel_type

Required for u-boot. The type of the kernel (`image`, `uimage` or `zimage`),
used to select the u-boot boot command.

### ramdisk

Optional. The path, within the image, to the ramdisk which will be used by the
bootloader.

### dtb

Optional. The path, within the image, to the dtb which will be used by the
bootloader.

### root_uuid

Required. The UUID of the partition which contains the root filesystem of the
image, for example `UUID=159d17cc-697c-4125-95a0-a3775e1deabe`. It is used as
the `{ROOT}` placeholder in the boot commands.

### boot_part

Required. The partition on the media from which the bootloader can read the
kernel, ramdisk and dtb. It is used as the `{ROOT_PART}` placeholder in the boot
commands. With u-boot, LAVA prefixes it with the `sata_id` from the device
dictionary (`<sata_id>:<boot_part>`).

!!! note "Path to the boot files"
    If the image mounts the boot partition below the root directory (for example
    on `/boot`), the paths to the files within that partition must **not**
    include that mountpoint. The bootloader reads the files directly from the
    partition.

!!! warning "Schema warning"
    The `kernel`, `kernel_type`, `ramdisk`, `dtb`, `root_uuid` and `boot_part`
    keys are not part of the boot action schema. The job is accepted, but the
    strict schema validation reports them as extra keys.

## Device configuration

The SATA disk is configured in the
[device dictionary](../../../configuration/device-dictionary.md#sata):

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `sata_label` | `ST160LM003` | Name of the disk, used as `device` in the job definition |
| `sata_uuid` | | Required. Name of the disk in `/dev/disk/by-id/` |
| `sata_id` | `0` | Bootloader device id of the disk |
| `sata_interface` | `scsi` (u-boot), `hd0` (grub) | Bootloader interface of the disk |
| `boot_part` | `1` | Default boot partition |

```jinja
{% set sata_label = 'ST500DM002' %}
{% set sata_uuid = 'ata-ST500DM002-1BD142_W3T79GCW' %}
{% set sata_id = 0 %}
```

The u-boot `sata` boot commands are defined in `base-uboot.jinja2`:

```yaml
- scsi scan
- load scsi {ROOT_PART} {KERNEL_ADDR} {KERNEL}
- load scsi {ROOT_PART} {RAMDISK_ADDR} {RAMDISK}; setenv initrd_size ${filesize}
- load scsi {ROOT_PART} {DTB_ADDR} {DTB}
- setenv bootargs '... root={ROOT} ...'
```

--8<-- "refs.txt"
