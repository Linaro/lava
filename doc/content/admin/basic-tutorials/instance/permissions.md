# User permissions

## Authorization

For how LAVA manage user permissions, see [authorization](../../../technical-references/authorization.md).

## Private instance

See [private instance](../../../technical-references/authorization.md#prviate-instance).

## Private devices/device-types

User access to devices and device types in LAVA can be configured from the Django
admin UI or via the XML-RPC API.

### Django admin UI

Navigate to the individual **device type** or **device** object in the Django
admin UI, find the **Group device (type) permissions** table, and add or remove
group permissions directly on the object.

### XML-RPC API

The XML-RPC methods are provided for managing device and device type permission
 (see `/api/help/`). You can use
 [lavacli](../../../user/basic-tutorials/lavacli.md) that based on the APIs to
 manage permissions.

#### Permission codenames:

| Object      | View              | Submit                 | Change              |
|-------------|-------------------|------------------------|---------------------|
| Device type | `view_devicetype` | `submit_to_devicetype` | `change_devicetype` |
| Device      | `view_device`     | `submit_to_device`     | `change_device`     |

#### Examples

Allow group `lkft` to view and submit to the `qemu` device type:

```shell
lavacli -i <instance> device-types perms add qemu lkft view_devicetype
lavacli -i <instance> device-types perms add qemu lkft submit_to_devicetype
```

Remove the submit permission:

```shell
lavacli -i <instance> device-types perms delete qemu lkft submit_to_devicetype
```

List permissions on the `qemu` device type:

```shell
lavacli -i <instance> device-types perms list qemu
```
