# Command action

The `command` action is used to execute a pre-defined command on the dispatcher
itself. A typical use case would be to set the boot mode for a board by
controlling a relay.

## Job definition

In order to use the action, the action block should only define the name of the
command to execute:

```yaml
actions:
- command:
    name: set_boot_to_nand
```

## Creating a secret

Set `create_secret` to store the output of the `do` command as a
[job secret](../job.md#secrets):

```yaml
actions:
- command:
    name: generate_wifi_ssid
    create_secret: WIFI_SSID
- command:
    name: generate_wifi_ap
    create_secret: WIFI_PASSPHRASE
```

`create_secret` must be a valid environment variable name (letters, digits and
underscores, not starting with a digit). It must not start with `LAVA_` (that
prefix is reserved for the job environment) and it must not be `PATH` (the
value would break every later command of the job).

The output is stripped of surrounding whitespace and is not shown in the job
log. The secret is then masked in the logs, exported to the environment of
later commands on the dispatcher, and written to the `secrets` file of the
overlay by later deploy actions. In this example, `generate_wifi_ap` can use
`$WIFI_SSID`.

!!! note "Empty output"
    If the command prints nothing, no secret is created.

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

!!! warning "`undo` is undefined"
    When using such commands, LAVA will not run any `undo` command.
