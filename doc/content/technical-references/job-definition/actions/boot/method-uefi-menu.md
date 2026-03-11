# UEFI Menu

The `uefi-menu` method selects a pre-defined menu entry in the UEFI
configuration for the device. In most cases this is used to execute a different
bootloader. For example, a `fastboot` device can execute `fastboot` from a menu
item, or a device could execute a PXE menu item to download and execute GRUB.

```yaml
- boot:
    method: uefi-menu
    commands: fastboot
    prompts:
    - 'root@debian:~#'
```

!!! warning
    Although it *is* possible to create new menu entries in UEFI each time a
    test job starts, this has proven to be unreliable on the device types tested
    so far. If the build of UEFI is not able to download a bootloader using PXE,
    then experiment with creating a UEFI menu item that executes a local file,
    and place a build of GRUB on local storage. Build the GRUB binary using
    `grub-mkstandalone` to ensure that all modules are available.

UEFI menus renumber themselves each time an item is added or removed, so LAVA
must match the *description* of the menu item and then identify the correct
selector to send the right character to execute that menu option. This means
admins must create the same menu structures on each device of the same device
type and correlate the text content of the menu with the
[device-type templates](../../../configuration/device-type-template.md).

To use `uefi-menu`, the device must offer a menu from which items can be
selected using a standard regular expression (`a-zA-Z0-9\s\:`). For example:

```text
[1] bootloader
[2] boot from eMMC
[3] Boot Manager
[4] Reboot
```

The device-type template needs to specify the `separator` (whitespace in the
example above) and how to identify the **item** matching the requested selector:

```yaml
- boot:
    method: uefi-menu
    parameters:
      item_markup:
      - "["
      - "]"
      item_class: '0-9'
      separator: ' '
```

This allows LAVA to match a menu item matching `\[[0-9]\] ['a-zA-Z0-9\s\:']`
and select the correct selector when the menu item string matches one (and only
one) line output by the UEFI menu. In this example the selector must be a digit.

## commands

The template must also specify which menu item to select, according to the
`commands` set in the test job:

```yaml
- boot:
    method: uefi-menu
    commands: fastboot
```

The device type template would then need:

```yaml
- boot:
    method: uefi-menu
    parameters:
      fastboot:
      - select:
          items:
          - 'boot from eMMC'
```

See also [commands](./common.md#commands).

## line_separator

Specifies the line ending sent to the UEFI console. Supported values are `dos`
(the default, `\r\n`) and `unix` (`\n`). Overrides the value set in device type.

```yaml
- boot:
    method: uefi-menu
    line_separator: unix
```

!!! warning
    This documentation may be outdated. If you use the boot method and see any
    issues, please submit an update. [Contact](../../../../introduction/contact.md)
    the LAVA dev team if help needed.

--8<-- "refs.txt"
