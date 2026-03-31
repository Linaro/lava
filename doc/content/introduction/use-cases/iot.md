# IoT

LAVA supports testing IoT and embedded devices using a set of deployment and
boot methods designed for resource-constrained hardware.

## Supported boot methods

- [DFU](../../technical-references/job-definition/actions/boot/method-dfu.md)
- [Musca](../../technical-references/job-definition/actions/boot/method-musca.md)
- [CMSIS-DAP](../../technical-references/job-definition/actions/boot/method-cmsis-dap.md)
- [JLink](../../technical-references/job-definition/actions/boot/method-jlink.md)
- [OpenOCD](../../technical-references/job-definition/actions/boot/method-openocd.md)
- [pyOCD](../../technical-references/job-definition/actions/boot/method-pyocd.md)

## Test monitors

Many IoT devices do not have a login shell. Instead, the firmware produces
structured output on the serial console. LAVA test
[monitors](../../technical-references/job-definition/actions/test.md#monitors)
action can be used to parse these output against expected patterns to determine
`pass/fail/skip/unknown` results without requiring an interactive shell.

## Example jobs

- [TF-M test on musca-b](../../technical-references/job-definition/actions/boot/method-musca.md#job-example)
- [Zephyr test on arduino101](../../technical-references/job-definition/actions/boot/method-dfu.md#hardware-dfu)
