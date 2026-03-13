# Overlay

The `overlay` deployment method creates the LAVA overlay without downloading
or flashing any images. The overlay is a tarball that contains LAVA helper
scripts and test definitions needed for running tests in LAVA test shell on the
DUT.

```yaml
- deploy:
    to: overlay
```

## Use case

The method is useful when the DUT is booted with a pre-installed OS. The overlay
can be transfer to the running OS using
[`transfer_overlay`](../boot/common.md#transfer_overlay) in the subsequent boot
method.

## Example job

[Flashing and testing rzn1 FW using a pre-installed OS](../boot/method-dfu.md#u-boot-dfu)

--8<-- "refs.txt"
