# Recovery

The `recovery` boot method switches the DUT into or out of recovery mode. It is
used together with the [recovery deploy method](../deploy/to-recovery.md).

```yaml
- boot:
    method: recovery
    commands: recovery
    timeout:
      minutes: 5
```

## commands

Required. Either:

* `recovery`: power off the DUT, run the `recovery_mode_command` from the
  device dictionary and power on the DUT.
* `exit`: power off the DUT, run the `recovery_exit_command` from the device
  dictionary and power on the DUT.

The DUT is powered on and not reset, so the effect of the recovery commands is
kept until the `exit` boot action.

No serial connection is opened: the DUT output is not read.
