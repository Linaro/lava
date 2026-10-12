# Schroot

The `schroot` boot method enters a
[schroot](https://wiki.debian.org/Schroot) session using the connection opened
by a previous [SSH](method-ssh.md) boot action. The following test actions are
executed inside the schroot.

```yaml
- boot:
    method: ssh
    connection: ssh
    prompts:
    - 'root@debian:~#'

- boot:
    method: schroot
    connection: ssh
    schroot: unstable
    prompts:
    - 'root@debian:~#'
```

`schroot` must be installed on the LAVA worker.

## connection

Required. Must be `ssh`.

## schroot

Required. The name of the schroot to enter.

## prompts

See [prompts](common.md#prompts).

## Device configuration

The `ssh.jinja2` device-type template defines the `schroot` boot method. The
following variables can be set in the device dictionary:

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `schroot` | | Command used to enter the schroot |
| `schroot_name_list` | `['unstable', 'sid']` | Names of the available schroots |

The `schroot` block can be overridden with an empty block in the device
dictionary to remove the schroot support.
