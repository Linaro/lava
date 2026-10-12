# Barebox

The `barebox` boot method boots the downloaded files using
[barebox](https://www.barebox.org/) bootloader commands.

```yaml
- boot:
    method: barebox
    commands: nfs
    auto_login:
      login_prompt: 'login:'
      username: root
    prompts:
    - 'root@debian:'
    timeout:
      minutes: 3
```

LAVA resets the device, interrupts barebox when the `interrupt_prompt` is
printed, then sends the commands one by one, waiting for the
`bootloader_prompt` after each command.

## commands

Either the name of a set of commands defined in the device-type template, or a
list of commands.

The `base-barebox.jinja2` template defines:

| Command | Description |
| ------- | ----------- |
| `tftp` | Boot using `boot net` |
| `nfs` | Boot kernel and dtb via TFTP, mount the root filesystem via NFS |
| `ramdisk` | Boot kernel, ramdisk and dtb via TFTP |

```yaml title="Custom commands"
- boot:
    method: barebox
    commands:
    - bootm -v -o /mnt/tftp/{DTB} /mnt/tftp/{KERNEL}
    prompts:
    - 'root@debian:'
```

Placeholders like `{KERNEL}`, `{DTB}`, `{RAMDISK}`, `{SERVER_IP}` or
`{NFSROOTFS}` are replaced by LAVA. See
[placeholder substitution](common.md#placeholder-substitution).

## auto_login

See [auto_login](common.md#auto_login).

## prompts

See [prompts](common.md#prompts).

## transfer_overlay

See [transfer_overlay](common.md#transfer_overlay).

## Device configuration

The device-type template must extend `base-barebox.jinja2`. The following
variables can be set in the device dictionary:

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `bootloader_prompt` | `barebox` | Prompt printed by barebox |
| `interrupt_prompt` | `stop autoboot` | Message printed by barebox before booting |
| `load_addr` | | Kernel load address used by `bootm` |
| `initrd_load_addr` | | Ramdisk load address used by `bootm` |
