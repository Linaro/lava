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
log. When the command fails its output is kept out of the log too, so a
command that printed its value and then failed cannot leak it. The secret is masked in
the logs, exported to the environment of later commands on the dispatcher, and
written to the `secrets` file of the overlay by later deploy actions.

The action runs without a shell. If the tool does not expand
`$WIFI_SSID` itself, wrap the command in bash:
`bash -c 'tool --ssid "$WIFI_SSID"'`.

!!! note "Empty output"
    If the command prints nothing, no secret is created.

With `create_secret` set, the device command's `do` must be a single command
(not a list) and its output must be a single line, or the job fails. The
command's stderr is captured together with its stdout, so a tool that writes
warnings there must redirect them inside a bash wrapper, e.g.
`bash -c 'tool 2>/dev/null'`, or they end up in the secret.

!!! note "Secret value length"
    Masking replaces the secret value wherever it appears in the job log. A
    very short value such as `1` or `OK` masks that substring across the whole
    log, so pick a value long enough not to collide.

`create_secret` works with the admin-defined and power commands listed below
too.

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
