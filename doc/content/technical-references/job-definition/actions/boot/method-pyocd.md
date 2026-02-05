# pyOCD

The `pyocd` boot method is used to flash and boot devices using the
[pyOCD](https://pyocd.io/) tool. It takes no parameters.

```yaml
- boot:
    method: pyocd
    timeout:
      minutes: 10
```

The boot method requires configuration on the device type level. The supported
configurations are:

* `command` - executable command to invoke
* `options` - list of options to pass to the executable
* `connect_before_flash` - if `true`, connect to device before running pyocd
flash command, otherwise after the command (default is `false`)
