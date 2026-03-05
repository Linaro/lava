# Musca

The `musca` deployment method allows deployment of software to Musca devices.
Currently, supported Musca devices are:

* [Musca-A](https://developer.arm.com/Tools%20and%20Software/Musca-A%20Test%20Chip%20Board)
* [Musca-B1](https://developer.arm.com/Tools%20and%20Software/Musca-B1%20Test%20Chip%20Board)
* [Musca-S1](https://developer.arm.com/Tools%20and%20Software/Musca-S1%20Test%20Chip%20Board)

```yaml
- deploy:
    to: musca
    images:
      test_binary:
        url: https://example.com/blinky.hex
```

The board is powered on and its mass storage device (MSD) is mounted. The test
binary is copied to the MSD and then the MSD is unmounted. When the board
processes it, the MSD will be re-exposed to the LAVA worker, at which point this
is re-mounted and LAVA will check for the presence of a ``FAIL.TXT`` file, in
case of errors.

## Setup

Some initial setup steps are required to ensure that the Musca device serves its
MSD when it is powered on. Check
[MSD COMMANDS](https://github.com/ARMmbed/DAPLink/blob/master/docs/MSD_COMMANDS.md)
for details on how to set up the board to auto-boot when it is programmed or
turned on. Ensure `DETAILS.TXT` on the MSD shows "Auto Reset" and "Auto Power"
are activated.

!!! note
    LAVA does not deploy firmware to the Musca board; firmware must be
    pre-installed on each device. Check the device pages for updating the firmware.

## images

### test_binary

The test binary to copy to the Musca mass storage device.

#### url

See [url](./index.md#url).
