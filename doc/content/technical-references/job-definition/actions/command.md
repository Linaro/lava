# Command action

The `command` action is used to execute a pre-defined command on the dispatcher
itself. A typical use case would be to set the bootmode for a board by
controlling a relay.

## Job definition

In order to use the action, the action block should only define the name of the
command to execute:

```yaml
actions:
- command:
    name: set_boot_to_nand
```

## Device dictionary

Admins should add the commands to the device dictionary:

```jinja
{% set user_commands = {'set_boot_to_qspi': {'do': 'webrelay --relay 1 on',
                                             'undo': 'webrelay --relay 1 off'},
                        'set_boot_to_nand': {'do': 'webrelay --relay 1 off',
                                             'undo': 'webrelay --relay 1 off'}} %}
```

Admins can define two commands:

* `do`: called when running the action
* `undo`: called when finalizing the job

!!! note "Failing jobs"
    When an action of a job is failing, the full job will be terminated.

    In such case, the `do` command of every subsequent actions will not be
    called. However, the job will be finalized and every `undo` commands will be
    called.

## Power commands

When defined, the power commands are automatically added to the list of available commands:

* `hard_reset`
* `pre_power_command`
* `pre_os_command`
* `power_on`
* `power_off`
* `recovery_mode`
* `recovery_exit`

!!! warn "`undo` is undefined"
    When using such commands, LAVA will not run any `undo` command.
