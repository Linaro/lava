# Fastboot

The `fastboot` deploy action downloads images and flashes them to the device
using the [Fastboot](https://en.wikipedia.org/wiki/Fastboot) protocol.

```yaml
- deploy:
    to: fastboot
    docker:
      image: linaro/noble-adb-fastboot
      local: true
    images:
      boot:
        url: https://example.com/boot.img
      rootfs:
        url: https://example.com/rootfs.img.xz
        compression: xz
        apply-overlay: true
```

## docker

LAVA supports running fastboot directly on the worker or within a Docker
container. Using Docker is recommended as it allows using custom fastboot
binaries and provides better isolation between jobs.

The `docker` block specifies the container image used to run fastboot commands.
This image must contain the `fastboot` binary.

```yaml
- deploy:
    to: fastboot
    docker:
      image: linaro/noble-adb-fastboot
      local: true
```

### image

The Docker image name (e.g., `linaro/noble-adb-fastboot`).

### local

Optional. If `true`, LAVA will use the image if it already exists locally on
the worker without pulling from a registry.

## images

The `images` block specifies a set of images to be downloaded and flashed to
the device. Each key in the `images` dictionary is the partition name to flash.

```yaml
- deploy:
    to: fastboot
    images:
      boot:
        url: https://example.com/boot.img
      system:
        url: https://example.com/system.img.xz
        compression: xz
```

### partition

The key name under `images` is the partition to which the image will be
flashed. It is passed directly to the `fastboot flash` command:

```shell
fastboot flash <image_key> <image>
```

!!! note
    If [`fastboot_sequence`](../../../configuration/device-dictionary.md#fastboot_sequence)
    is set to `no-flash-boot`, LAVA skips flashing the `boot` partition even if
    a `boot` image was listed under `images`.

### apply-overlay

Set to `true` to apply the LAVA test overlay to this image. The overlay
contains the test definitions and LAVA helper scripts.

```yaml
- deploy:
    to: fastboot
    images:
      rootfs:
        url: https://example.com/rootfs.img.xz
        compression: xz
        apply-overlay: true
```

### sparse

System images shipped as sparse images requires special handling with tools such
as `simg2img` and `img2simg` in order to apply LAVA overlays.

By default, LAVA assumes that any image with `apply-overlay: true` is a sparse
image. If the image is not a sparse image, set `sparse: false` so that LAVA
treats it as a plain ext4 image:

```yaml
- deploy:
    to: fastboot
    images:
      system:
        url: https://example.com/system.ext4.xz
        compression: xz
        sparse: false
        apply-overlay: true
```

### reboot

If the device needs to be restarted after flashing a image, specify the reboot
method. This is optional and only needed when an intermediate reboot is required.

```yaml
- deploy:
    to: fastboot
    images:
      partition:
        url: https://example.com/gpt_both0.bin
        reboot: hard-reset
      boot:
        url: https://example.com/boot.img
```

Allowed values:

- `hard-reset`
- `fastboot-reboot`
- `fastboot-reboot-bootloader`
- `fastboot-reboot-fastboot`

### url

See [url](./index.md#url)

### compression

See [compression](./index.md#compression)
