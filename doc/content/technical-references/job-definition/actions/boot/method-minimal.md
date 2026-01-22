# Minimal

The `minimal` method is used to power-on the DUT and to let the DUT boot without
any interaction.

```yaml
- boot
    method: minimal
    prompts:
    - 'root@debian:~#'
```

## reset

By default, LAVA will reset the board power when executing this action. You can
skip this step by setting `reset: false`.

```yaml
- boot
    method: minimal
    reset: false
```

This can be useful when testing bootloader in interactive tests and then
booting to the OS without resetting the device.

## pre_power_command

`pre_power_command` defined in the device dictionary can be used to activate or
deactivate external hardware before applying power to the device. Set
`pre_power_command: true` to execute the command.

```yaml
- boot
    method: minimal
    pre_power_command: true
```

## pre_os_command

`pre_os_command` defined in the device dictionary can be used to activate or
deactivate external hardware before booting the OS. Set `pre_os_command: true`
to execute the command.

```yaml
- boot
    method: minimal
    pre_os_command: true
```
