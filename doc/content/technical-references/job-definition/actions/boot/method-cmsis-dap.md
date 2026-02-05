# cmsis-dap

The `cmsis-dap` boot method takes no parameters. It is used to flash and boot
a device by copying the images to the USB Mass Storage device exposed by the
[CMSIS-DAP](https://arm-software.github.io/CMSIS-DAP/latest/) interface.

```yaml
- boot
    method: cmsis-dap
    timeout:
      minutes: 10
```
