# VEMSD

The `vemsd` (Versatile Express MicroSD) deployment method is used to write a
new recovery image to the ARM Versatile Express Hardware Platforms like Juno.

```yaml
- deploy:
    to: vemsd
    recovery_image:
      url: https://storage.lavacloud.io/health-checks/juno-r2/20.01-oe-uboot.zip
      compression: zip
```

Note that the image is unpacked onto the filesystem of the VEMSD by the
deployment method, however, the actual flashing is deferred and executed
automatically during the next boot.

## recovery_image

The image ready to be unpacked onto the MicroSD.

### url

See [url](./index.md#url)

### compression

If the image is compressed, the compression method **must** be specified.

See [compression](./index.md#compression)
