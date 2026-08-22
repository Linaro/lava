# QDL

The qdl deployment action downloads a flat build tarball to Qualcomm devices
using qdl [qdl](https://github.com/linux-msm/qdl).
It is possible to add a LAVA overlay to one of the partition images
within the tarball.
QDL deployment is required to boot into QDL mode and
flash the contents of the tarball onto the board.

```yaml
- deploy:
    rootfs_image: rootfs.img
    qcomflash:
      url: ...
      apply-overlay: true
    to: qdl
```

## qcomflash

The `qcomflash` block specifies the location of the tarball to be downloaded.
It uses the usual [download syntax](./index.md#artifacts).
The tarball should not be decompressed by the download action.
It is assumed that the archive is compressed.

## rootfs_image

This parameter points to a partition image where the LAVA overlay should be added.
The value should be a path relative to the main directory in the tarball.

## qcomflash

This parameter represents the tarball containing the build to be flashed to the device.

### apply-overlay

LAVA can apply the [overlay](../boot/common.md#transfer_overlay) to the image before flashing.
The overlay is applied to the [rootfs_image](#rootfs_image).

The overlay tarball is unpacked at the root (`/`) of the filesystem contained in
`rootfs_image`, so its contents land in `lava_test_results_dir` relative to that
filesystem root. `lava_test_results_dir` defaults to `/lava-<job_id>` for most
deployments and can be changed through the [job context](../../job.md#context),
but the same value is also the path the test shell scripts use on the booted
device, so both ends move together and it cannot be used to unpack the overlay
somewhere else.

This matters for images where the filesystem in `rootfs_image` is not the
filesystem root seen after boot, for example OSTree based images, where the
booted deployment lives further down the tree. There the overlay is written
outside of the booted root, the test shell scripts do not find it at
`lava_test_results_dir` and the test job fails.
