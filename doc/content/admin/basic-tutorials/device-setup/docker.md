# Docker device setup

LAVA can use docker as a DUT and run test under Docker.

## Create device-type

Create a device-type in the [admin interface](/admin/lava_scheduler_app/devicetype/add/).

The only relevant information is the device-type name that should be **docker**.

??? tip "Command line"

    ```shell tab="lavacli"
    lavacli device-types add docker
    ```

    ```shell tab="lava-server"
    lava-server manage device-types add docker
    ```

## Create device

Create a docker device in the [admin interface](/admin/lava_scheduler_app/device/add/):

* hostname: name of the device
* device-type: **docker**
* worker host: worker that will run the job

??? tip "Command line"

    ```shell tab="lavacli"
    lavacli devices add --type docker --worker <worker> <hostname>
    ```

    ```shell tab="lava-server"
    lava-server manage devices add \
        --device-type docker \
        --worker <worker> \
        <hostname>
    ```

## Device configuration

In order to submit jobs to the newly created device, LAVA requires a device
dictionary. For a simple docker job, this device dictionary would work:

```jinja
{% extend "docker.jinja2" %}
```

This file should be pushed to the LAVA server under
`/etc/lava-server/dispatcher-config/devices/<hostname>.jinja2`.

!!! tip "Command line"

    ```shell tab="lavacli"
    lavacli devices dict set <hostname> <filename>
    ```

    ```bash tab="lava-server"
    cp <filename> /etc/lava-server/dispatcher-config/devices/<hostname>.jinja2
    chown lavaserver:lavaserver /etc/lava-server/dispatcher-config/devices/<hostname>.jinja2
    ```

## Activate the device

By default, a new device is put in maintenance.

As the device is now configure, admins can put it online in the [device page](/scheduler/device/<hostname>).

??? tip "Command line"

    ```shell tab="lavacli"
    lavacli devices update --health UNKNOWN <hostname>
    ```

    ```bash tab="lava-server"
    lava-server manage devices update --health UNKNOWN <hostname>
    ```

## Submit a job

Submit this simple test job:

```yaml
--8<-- "jobs/docker.yaml"
```

--8<-- "refs.txt"
