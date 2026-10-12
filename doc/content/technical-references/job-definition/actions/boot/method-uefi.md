# UEFI

The `uefi` boot method boots the DUT using commands sent to the UEFI shell.

To boot by selecting entries in the UEFI menu instead, see
[UEFI Menu](method-uefi-menu.md).

```yaml
- boot:
    method: uefi
    commands: nfs
    prompts:
    - 'root@genericarmv8:~#'
```

LAVA resets the device and, if needed, selects the UEFI shell in the UEFI menu.
LAVA then interrupts the shell startup when the `shell_interrupt_prompt` is
printed and sends the commands one by one, waiting for the `bootloader_prompt`
after each command.

## commands

Either the name of a set of commands defined in the device-type template, or a
list of commands.

Placeholders like `{KERNEL}` or `{DTB}` are replaced by LAVA. See
[placeholder substitution](common.md#placeholder-substitution).

## shell_menu

Optional. The name of the menu entries, defined in the device-type template, to
select in order to drop to the UEFI shell. Overrides the `shell_menu` from the
device configuration.

Newer firmware usually starts the shell without any menu interaction. Set
`shell_menu` to an empty string to skip the menu:

```yaml
- boot:
    method: uefi
    commands: nfs
    shell_menu: ''
    prompts:
    - 'root@genericarmv8:~#'
```

## auto_login

See [auto_login](common.md#auto_login).

## prompts

See [prompts](common.md#prompts).

## transfer_overlay

See [transfer_overlay](common.md#transfer_overlay).

## Device configuration

The device-type template must define the `uefi` boot method with the following
parameters:

| Parameter | Description |
| --------- | ----------- |
| `bootloader_prompt` | Required. The UEFI shell prompt, for example `Shell>` |
| `shell_interrupt_prompt` | Required. The message printed before starting the shell |
| `shell_interrupt_string` | Required. The string sent to interrupt the shell startup |
| `shell_menu` | Optional. The name of the menu entries to select to drop to the shell |

When `shell_menu` is used, the menu parameters (`interrupt_prompt`,
`interrupt_string`, `menu_prompt`, `menu_boot_message`, `item_markup`,
`item_class`, `separator`, `label_class`...) are the same as for
[UEFI Menu](method-uefi-menu.md).

```yaml
actions:
  boot:
    methods:
      uefi:
        parameters:
          bootloader_prompt: 'Shell>'
          shell_interrupt_prompt: 'any other key to continue'
          shell_interrupt_string: ' '
          shell_menu: shell
          interrupt_prompt: The default boot selection will start in
          interrupt_string: ' '
          menu_boot_message: 'UEFI Interactive Shell'
          menu_prompt: 'Start:'
          item_markup:
          - '['
          - ']'
          item_class: '0-9'
          separator: ' '
          line_separator: dos
          label_class: 'a-zA-Z0-9\s\:'
        shell:
        - select:
            items:
            - 'Shell'
        nfs:
          commands:
          - norkern console=ttyAMA0,115200n8 root=/dev/nfs rw ...
```

See `vexpress.jinja2` for an example.
