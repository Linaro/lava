# AVH

Creates a custom AVH package from a set of `images`, or deploys a pre-built AVH
`fw_package`.

## Custom package

Creates a custom AVH Linux firmware package from individual images.

```yaml
- deploy:
    to: avh
    options:
      model: rpi4b
      api_endpoint: https://app.avh.corellium.com/api
      project_name: "Default Project"
    images:
      rootfs:
        url: https://example.com/rpi4b/nand
        format: ext4
        # root partition for LAVA test overlay
        root_partition: 1
        # partition for custom overlays
        partition: 1
        overlays:
          modules:
            compression: xz
            format: tar
            path: /
            url: https://example.com/rpi4b/modules.tar.xz
      kernel:
        url: https://example.com/rpi4b/kernel
      dtb:
        url: https://example.com/rpi4b/devicetree
```

The deployment action runs the following tasks in serial:

* Download the `kernel`, `dtb` and `rootfs` images required by AVH custom firmware.
* Apply lava overlay to `rootfs` image when needed.
* Generate an `Info.plist` file for the meta information about firmware version,
  type, build, unique identifier, and device identifier.
* Create a zip package that contains the images and the `Info.plist` file.

### rootfs

OS disk image file.

#### url

See [url](./index.md#url)

#### format

Specify disk image format for LAVA to apply overlay. `ext4` is the only
supported format now.

#### root_partition

Specify disk image root partition index for LAVA to apply overlay. Disk image
partition index 0 usually is the boot partition, while index 1 usually is the
root partition.

#### overlays

AVH doesn't support adding custom Kernel modules to custom Linux firmware
package yet. Fortunately, this is supported in LAVA by applying custom
`overlays.modules` into the `rootfs` image.

See [overlays](./index.md#overlays)

### kernel

The Linux kernel in the `Image` format.

### dtb

The device tree for Linux in binary `.dtb` format.

See also [DTB](../../../../introduction/glossary.md#dtb)

## Pre-built firmware package

Deploys a pre-built AVH firmware package.

```yaml
- deploy:
    to: avh
    options:
      model: kronos
      api_endpoint: https://app.avh.corellium.com/api
      project_name: "Default Project"
    fw_package:
      url: https://example.com/kronos-baremetal-psa-secure-storage-1.0.zip
      storage_file: virtio_0
      root_partition: 1
```

### storage_file

The name of the storage file inside the firmware package. It should be a disk
image in ext4 format.

See [AVH Storage](https://support.avh.corellium.com/devices/firmware/linux-firmware#storage)
for details.

### root_partition

See [root_partition](#root_partition)

## Options

A dictionary of AVH configuration.

### model

This `model` key is crucial and mandatory. `avh` deploy action needs it to
generate `Info.plist` file. `avh` boot action needs it to create instance.

Here are the tested models in LAVA.

* rpi4b
* imx93
* kronos

Other models that capable to run Linux should work too.

### api_endpoint

(optional) AVH API endpoint defaults to https://app.avh.corellium.com/api.

### project_name

(optional) AVH project name defaults to `Default Project`.
