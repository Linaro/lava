# GDB

The `gdb` boot method loads and starts a binary on the DUT using `gdb`, usually
through a debug probe driven by [OpenOCD](https://openocd.org/). It is used for
microcontroller (MCU) boards.

```yaml
- deploy:
    to: tmpfs
    images:
      zephyr:
        url: https://example.com/zephyr.elf
      openocd_script:
        url: https://example.com/cc3220_xds110.cfg

- boot:
    method: gdb
    commands: openocd
    timeout:
      minutes: 2
```

LAVA:

1. resets the device, if a `hard_reset_command` is defined
2. waits for the USB serial device and connects to it
3. starts `gdb` with the `arguments` defined for these `commands`
4. sends each gdb command
5. sends `continue` to start the binary

When the boot action ends, LAVA stops `gdb`.

## commands

Required. The name of a set of gdb commands defined in the device-type template,
for example `openocd`.

The downloaded files can be used in the arguments and commands with an upper
case placeholder named after the image key. For example, `images.zephyr` is
available as `{ZEPHYR}` and `images.openocd_script` as `{OPENOCD_SCRIPT}`.

See [placeholder substitution](common.md#placeholder-substitution).

## container

Optional. The docker image in which `gdb` is run. It overrides the container
defined in the device-type template.

This is only allowed when docker is enabled for these commands in the
device configuration (`docker_use`).

```yaml
- boot:
    method: gdb
    commands: openocd
    container: ti-openocd-small
```

The directories of the downloaded files are mounted in the container at the same
path.

## Device configuration

The gdb binary and the commands are defined in the device-type template:

```yaml
actions:
  boot:
    methods:
      gdb:
        parameters:
          command: gdb-multiarch
          wait_before_continue: 5
        openocd:
          arguments:
          - "{ZEPHYR}"
          commands:
          - target remote | openocd -c "gdb_port pipe" -f {OPENOCD_SCRIPT}
          - monitor reset halt
          - load
          - set remotetimeout 10000
          docker:
            use: false
            container: ti-openocd
            devices: []
```

* `command`: the gdb binary to run
* `wait_before_continue`: seconds to wait before sending `continue`
* `arguments`: the list of arguments passed to gdb
* `commands`: the list of commands sent to gdb
* `docker`: run gdb in a docker container (`use`), with the given default
  `container` and the `devices` to share with the container

See `cc3220SF.jinja2` for an example. In this template, the following
variables can be set in the device dictionary:

| Variable | Default |
| -------- | ------- |
| `wait_before_continue` | `5` |
| `docker_use` | `False` |
| `docker_container` | `ti-openocd` |
| `docker_devices` | `[]` |
