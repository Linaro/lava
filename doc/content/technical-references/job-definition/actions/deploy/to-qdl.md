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
    overlay_path: /home
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

## overlay_path

This parameter names the path inside the [rootfs_image](#rootfs_image)
where the LAVA overlay should be added.
The value should be in line with the variable `lava_test_results_dir` defined in the job context.

## qcomflash

This parameter represents the tarball containing the build to be flashed to the device.

### apply-overlay

LAVA can apply the [overlay](../boot/common.md#transfer_overlay) to the image before flashing.
The overlay is applied to the [overlay_path](#overlay_path).
