# QEMU device setup

LAVA can use qemu as a DUT and run test inside QEMU.

## Create device-type

[Create the device type](common.md#create-device-type) using the name **`qemu`**.

## Create device

1. [Add the device](common.md#add-device) using the following settings:
    * **Device Type:** `qemu`
    * **Hostname:** A unique name (e.g., `qemu-01`)
2. [Add the device configuration](common.md#add-device-configuration).

    For a simple qemu job, this device dictionary would work:

    ```jinja
    {% extends "qemu.jinja2" %}

    {% set netdevice = "user" %}
    {% set memory = 1024 %}
    ```

    !!! tip
        If `/dev/kvm` is unavailable on the worker, add `{% set no_kvm = True %}` to
        the dictionary.

## Submit a job

Submit this simple test job:

```yaml
--8<-- "jobs/qemu.yaml"
```

The job page will look like [this](https://validation.linaro.org/scheduler/job/2009038).

--8<-- "refs.txt"
