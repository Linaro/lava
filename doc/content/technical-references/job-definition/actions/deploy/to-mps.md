# MPS

The `mps` deployment method is used to write a recovery image and test binaries
to the MPS devices. The support is similar to the [VEMSD](./to-vemsd.md).

```yaml
  - deploy:
      to: mps
      images:
        recovery_image:
          url: mps2_sse200_an512.tar.gz
          compression: gz
        test_binary_1:
          url: tfm_sign.bin
        test_binary_2:
          url: mcuboot.bin
```

## recovery_image

The image ready to be unpacked onto the USB filesystem of the MPS device.

## test_binary

Download test binary to MPS device and rename if required.

Multiple test binaries can be flashed in the same deploy action by listing all
of them. The keys should start with `test_binary_`.

### rename

Renames the test_binary if required.

If the `recovery_image` expects to flash a specific image and the file
downloaded is not named this way, this option will save it with a different
name on the board.

If not specified, the test_binary is copied as-is, no renaming takes place.

```yaml
  - deploy:
      to: mps
      images:
        recovery_image:
          url: mps2_sse200_an512.tar.gz
          compression: gz
        test_binary_1:
          url: tfm_sign_20191121.bin
          rename: tfm_sign.bin
```

## url

See [url](./index.md#url)

## compression

If the image is compressed, the compression method **must** be specified.

See [compression](./index.md#compression)
