# OpenOCD

The `openocd` boot method is used to flash and boot devices using the
[OpenOCD](https://openocd.org/) tool. It takes no parameters.

```yaml
- boot:
    method: openocd
    timeout:
      minutes: 10
```

The method works by passing through the command line options defined in the
device type for the `openocd` command. It flashes the executable specified by
`binary` in the prior job deploy action. If `openocd_script` is also specified
in the deploy action, it uses that script file instead of the one specified by
the device type.

!!!note
    Both `binary` and `openocd_script` files must be downloaded by the
    preceding deploy action.

`board_selection_cmd` can be used in the device type to specify a command to
pass the board id/serial number to OpenOCD. See OpenOCD documentation for
details on the command to set the serial number for the interface your device
type is using.
