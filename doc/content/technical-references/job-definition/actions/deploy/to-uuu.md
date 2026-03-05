# UUU

The `uuu` deployment action downloads images for flashing to NXP i.MX devices
using the [UUU (Universal Update Utility)](https://github.com/NXPmicro/mfgtools).
The job definition schema is very similar to the [`fastboot`](./to-fastboot.md)
deployment method, with a required boot partition.

```yaml
- deploy:
    to: uuu
    images:
      boot:
        url: https://example.com/imx-boot-sd.bin-flash
      system:
        url: https://example.com/imx-image-multimedia.rootfs.wic
        apply-overlay: true
        root_partition: 1
```

## images

The `images` block specifies a set of images to be downloaded and deployed to
the device.

### partition

Each key in the `images` dictionary is a partition name that can be referenced
in the [`uuu`](../boot/method-uuu.md) boot method `commands` using
`{partition_name}` placeholders.

```yaml
- deploy:
    to: uuu
    images:
      boot:
        url: https://example.com/imx-boot-sd.bin-flash
- boot:
    method: uuu
    commands:
    - uuu: -b sd {boot}
```

!!! warning
    Partition `boot` is required by `uuu` boot method to perform USB serial
    download availability check. The check attempts to write the boot image into
    memory using the command `uuu {boot}`. If the command does not complete
    within 10 seconds, primary boot-media will be erased using
    `uuu_corrupt_boot_media_command`, so the device can enter USB serial
    download mode after the following reset.

### apply-overlay

The default is `false`. Set to `true` to apply the LAVA test overlay to this
image. The overlay contains the test definitions and LAVA helper scripts.

```yaml
- deploy:
    to: uuu
    images:
      system:
        url: https://example.com/system.img.xz
        compression: xz
        apply-overlay: true
```

### root_partition

Specify the root partition index within a disk image for LAVA to apply the
overlay. Partition index 0 is typically the boot partition, while index 1 is
the root partition.

```yaml
- deploy:
    to: uuu
    images:
      system:
        url: https://example.com/imx-image-multimedia.rootfs.wic
        apply-overlay: true
        root_partition: 1
```

### sparse

System images shipped as sparse images require special handling with tools such
as `simg2img` and `img2simg` in order to apply LAVA overlays.

The default is `false`. Set `sparse: true` if the image is a sparse image:

```yaml
- deploy:
    to: uuu
    images:
      system:
        url: https://example.com/system.img.xz
        compression: xz
        sparse: true
        apply-overlay: true
```

## uniquify

By default, LAVA stores each downloaded image in a separate subdirectory named
after the image key to avoid filename collisions. When needed, set
`uniquify: false` to store all images in the same directory. E.g., the
`uuu.lst` you are using may assume all artifacts in the same folder.

```yaml
- deploy:
    to: uuu
    uniquify: false
    images:
      boot:
        url: https://example.com/imx-boot-sd.bin-flash
      system:
        url: https://example.com/imx-image-multimedia.rootfs.wic
```

### url

See [url](./index.md#url)

### compression

See [compression](./index.md#compression)
