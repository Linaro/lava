# Device-type template

The device-type template is a [jinja2][jinja2] template that will be extended
by [device dictionaries](./device-dictionary.md). The resulting file is the
device configuration file.

This [yaml][yaml] file is used by `lava-dispatcher` to know how to flash, boot
and communicate with a specific device.

# Configuration file

The device-type templates that are supported and provided by LAVA are stored
in `/usr/share/lava-server/device-types/`.

Admins could also provide their own device-type template using lavacli:

```shell
lavacli device-types template set qemu qemu.jinja2
```

Device-types provided by admins will be stored in
`/etc/lava-server/dispatcher-config/device-types/<name>.jinja2`.

LAVA will always look first in `/etc/lava-server/dispatcher-config/device-types/` and fallback to `/usr/share/lava-server/device-types/`.

This mean that admins can override every device-type templates, including the
ones provided by LAVA.

--8<-- "refs.txt"
