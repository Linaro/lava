# Docker device setup

LAVA can use docker as a DUT and run test under Docker.

## Create device-type

[Create the device type](common.md#create-device-type) using the name **`docker`**.

## Create device

1. [Add the device](common.md#add-device) using the following settings:
    * **Device Type:** `docker`
    * **Hostname:** A unique name (e.g., `docker-01`)
2. [Add the device configuration](common.md#add-device-configuration).

    For a standard docker device and a simple docker job, the following device
    dictionary should be sufficient:

    ```jinja
    {% extends "docker.jinja2" %}
    ```

## Submit a job

Submit this simple test job:

```yaml
--8<-- "jobs/docker.yaml"
```

--8<-- "refs.txt"
