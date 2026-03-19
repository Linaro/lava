# Job Schema

A LAVA job definition is a YAML file that describes the test job to execute. It
specifies what device to use, how to deploy software, how to boot, and what
tests to run.

In general, the schema used for the job definition is constrained. The schema
requires that specific elements must exist in specific formats. The LAVA server
performs basic schema validation when the job is submitted. Full validation is
performed on the LAVA worker at runtime during the job validation phase.

This page documents the top-level elements supported in LAVA job definitions,
with links to more detailed schemas.

## job_name

**Required** `string` (1–200 characters)

Name of the job, sometime called `description`.

```yaml
job_name: network-smoke-test
```

## device_type

`string` (1–50 characters)

**Required** by single node jobs. These jobs will fail to validate if no device
type is given.

```yaml
device_type: qemu
```

For [multinode](../../user/advanced-tutorials/multinode.md) jobs, the device type
is defined per-role inside the `lava-multinode` protocol block.

!!! note
    The device type **must** exist on the LAVA instance for the submission to
    be accepted by the scheduler.

## tags

`list[str]`

A list of device tags that the assigned device must have. This is used to
select a specific subset of devices of the given device type.

```yaml
tags:
- usb-eth
```

## timeouts

**Required** `dict`

See [Timeouts](./timeouts.md)

## visibility

**Required** `string` or `dict`

Controls who can view the job and its results.

```yaml
visibility: "public"
```

```yaml
visibility:
  group:
  - developers
  - project
```

Supported values:

| Value        | Description                                    |
| ------------ | ---------------------------------------------- |
| `"public"`   | Visible to everyone, including anonymous users |
| `"personal"` | Visible only to the submitter                  |
| `group`      | Visible to members of the specified group(s)   |

## priority

`string` or `int`

Controls the scheduling priority of the job.

```yaml
priority: high
```

Supported values:

| Value              | Description                                |
| ------------------ | ------------------------------------------ |
| `"high"`           | High priority                              |
| `"medium"`         | Medium priority (default)                  |
| `"low"`            | Low priority                               |
| `0`–`100`          | Higher value means higher priority         |

## context

`dict`

Allows individual jobs to override selected device configuration values. The
keys must be from the set of allowed context variables.

??? "Allowed context variables"
    - `arch`
    - `boot_character_delay`
    - `boot_console`
    - `boot_retry`
    - `boot_root`
    - `booti_dtb_addr`
    - `booti_kernel_addr`
    - `booti_ramdisk_addr`
    - `bootloader_prompt`
    - `bootm_dtb_addr`
    - `bootm_kernel_addr`
    - `bootm_ramdisk_addr`
    - `bootz_dtb_addr`
    - `bootz_kernel_addr`
    - `bootz_ramdisk_addr`
    - `console_device`
    - `cpu`
    - `custom_kernel_args`
    - `deploy_character_delay`
    - `extra_kernel_args`
    - `extra_nfsroot_args`
    - `extra_options`
    - `failure_retry`
    - `guestfs_driveid`
    - `guestfs_interface`
    - `guestfs_size`
    - `kernel_loglevel`
    - `kernel_start_message`
    - `lava_test_results_dir`
    - `machine`
    - `memory`
    - `menu_interrupt_prompt`
    - `model`
    - `monitor`
    - `mustang_menu_list`
    - `netdevice`
    - `no_kvm`
    - `no_network`
    - `serial`
    - `test_character_delay`
    - `tftp_mac_address`
    - `uboot_altbank`
    - `uboot_extra_error_message`
    - `uboot_needs_interrupt`
    - `vga`

Check device type and action documentation for the detailed usages.

## environment

`dict`

See [environment](./environment.md)

## secrets

`dict[str: str]`

A dictionary of secret values.

```yaml
secrets:
  API_USER: kernel-ci
  API_KEY: b43614a9583f9c74b989914a91d1cfd9
```

Remote artifact tokens with `Token name` and `Token string` paires can be added
on your profile page. The value of a secret can be the `Token name` so the real
token does not need to appear in the job definition. LAVA replaces that name
with the actual `Token string` for the job runs.

In the following example,  LAVA uses `token-name` to show the job definition and
replaces it with the actual `Token string` for the job run.

```yaml
secrets:
  API_KEY: token-name
```

This dictionary will be written to the LAVA overlay using the `secrets` file
name. The file can be discovered and sourced from a test shell:

```shell
lava_dir="$(find /lava-* -maxdepth 0 -type d | grep -E '^/lava-[0-9]+' 2>/dev/null | sort | tail -1)"
source "$lava_dir/secrets"
```

!!! note
    `/lava-*` is the default LAVA overlay path; adjust it when needed.

!!! warning "Avoid secret leaks"
    - Use per-user remote artifact tokens whenever possible.
    - Always set job visibility to `personal` so only you can see the secrets.
    - Do not print the secret values in test log.
    - A compromise of the DUT or its filesystem can leak your secrets. Do not
    use this feature with highly sensitive credentials — use a proper secrets
    management system instead.

## metadata

`dict`

An arbitrary set of key-value pairs attached to the job. The data can be
retrieved via LAVA APIs.

```yaml
metadata:
  build-url: https://ci.example.com/builds/42
  toolchain: clang-r377782b
```

## actions

**Required** `list`

A list of actions blocks to execute. Every action block supports these optional
parameters:

| Key                      | Type       | Description                         |
| ------------------------ | ---------- | ----------------------------------- |
| `timeout`                | `dict`     | Timeout for this action             |
| `timeouts`               | `dict`     | Per-child-action timeout            |
| `namespace`              | `string`   | Namespace for this action           |
| `connection-namespace`   | `string`   | Namespace to use for the connection |
| `failure_retry`          | `int`      | Number of times to retry on failure |
| `failure_retry_interval` | `int`      | Seconds to wait between retries     |
| `repeat`                 | `int`      | Number of times to repeat           |

The supported action types are:

### deploy

`dict`

See [Deploy action](./actions/deploy/index.md) for image deployment.

### boot

`dict`

See [Boot action](./actions/boot/common.md) for booting a device.

### test

`dict`

See [Test action](./actions/test.md) for running tests.

### command

`dict`

See [Command action](./actions/command.md) for executing a pre-defined command
on the LAVA worker.

## notify

`dict`

See [Notifications](./notifications.md)

## protocols

`dict`

See [Protocols](./protocols.md)
