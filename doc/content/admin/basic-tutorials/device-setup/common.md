# Device setup

## Available methods

The following methods can be used to add, update and delete device types and
devices in LAVA.

!!!note
    Only one method is required - choose the option that works best for you.

### Admin interface

The LAVA admin interface is a web-based graphical interface accessible through
your browser. It provides easy to use forms for managing device types and
devices. A user with admin permission is required to access it. To access it,
navigate to `/admin/lava_scheduler_app/`.

### Command line

One of the following tools can be used for managing device types and devices
from the command line:

#### lavacli

The `lavacli` utility is the recommended command line tool for interacting with
the LAVA server. Refer to [lavacli](../../../user/basic-tutorials/lavacli.md)
for usage details and setup steps.

#### lava-server

The `lava-server manage` command offers a suite of sub-commands for managing
LAVA server. Because it interacts directly with the database and system
configuration files, it must be executed as root on the server itself.

## Create device type

A device type can be created using one of the following methods. For detailed
usage of the methods, refer to [Available methods](#available-methods).

### From admin interface

1. Navigate to `/admin/lava_scheduler_app/devicetype/add/` in your browser.
2. Input device type `Name` which is the only required field. It must match
exactly the device type name provided in device specific setup guide
(e.g., `docker`, `qemu`, `avh`).

### Via command line

=== "lavacli"
    ```shell
    lavacli device-types add <device-type>
    ```
=== "lava-server"
    ```shell
    lava-server manage device-types add <device-type>
    ```

## Create device

### Add device

A device can be created using one of the following methods. For detailed usage
of the methods, refer to [Available methods](#available-methods).

#### From admin interface

1. Navigate to `/admin/lava_scheduler_app/device/add/` in your browser.
2. Provide the following information:

    * **hostname**: unique identifier for the device
    * **device-type**: the device type name provided in device setup guide
    * **worker host**: the worker that this device is attached to

#### Via command line

=== "lavacli"
    ```shell
    lavacli devices add --type <device-type> --worker <worker> <hostname>
    ```
=== "lava-server"
    ```shell
    lava-server manage devices add \
        --device-type <device-type> \
        --worker <worker> \
        <hostname>
    ```

### Add device configuration

Before a device can accept jobs, it requires a device configuration that defines
its specific characteristics. The device configuration is a [Jinja2][jinja2]
template file that extends a base device type template and can override or add
device specific configurations. For example, serial connection command and
power reset, off, and on commands.

The device configuration file must be placed at
`/etc/lava-server/dispatcher-config/devices/<hostname>.jinja2` on the LAVA server.
It can be copied or uploaded to this location using one of the following methods.
For detailed usage of the methods, refer to [Available methods](#available-methods).

Before running the command below:

* Replace the `<hostname>` with the actual device hostname.
* Create the device configuration file `<hostname>.jinja2`. Refer to device
specific setup guides for examples.

=== "lavacli"
    ```shell
    lavacli devices dict set <hostname> <hostname>.jinja2
    ```
=== "lava-server"
    ```shell
    cp <filename> /etc/lava-server/dispatcher-config/devices/<hostname>.jinja2
    chown lavaserver:lavaserver /etc/lava-server/dispatcher-config/devices/<hostname>.jinja2
    ```

### Change device health

After a device configuration file added, now it is time to put the device online
by changing its health using one of the following methods. For detailed usage of
the methods, refer to [Available methods](#available-methods).

#### From admin interface

1. Navigate to `/admin/scheduler/device/<hostname>` in your browser.
2. Find the `Status` section, change the `Health` field to either `Unknown` or
`Good`.

#### Via command line

Replace `<health>` with either `UNKNOWN` or `GOOD`.

=== "lavacli"
    ```shell
    lavacli devices update --health <health> <hostname>
    ```
=== "lava-server"
    ```shell
    lava-server manage devices update --health <health> <hostname>
    ```

A device in unknown health is already ready to accept and run test jobs. If a
[health check](../../../technical-references/configuration/health-check.md)
job is configured, the device will be tested automatically. A successful health
check run sets the device health to `Good`, while a failed run sets it to `Bad`.

For more information about device state and health, refer to
[device state and health](../../../technical-references/state-machine.md#devices).

--8<-- "refs.txt"
