# Configure LAVA

## Creating a superuser

Admins can create superuser accounts from the command line:

=== "Docker"

    ```shell
    docker-compose exec lava-server lava-server manage createsuperuser
    ```

=== "Debian"
    ```shell
    lava-server manage createsuperuser
    ```

## Settings

### Configuration files

LAVA settings are stored in **yaml** in:

* `/etc/lava-server/settings.conf`
* `/etc/lava-server/settings.yaml`
* `/etc/lava-server/settings.d/*.yaml`

LAVA will load the files in this exact order. Files in the `settings.d`
directory will be alphabetically ordered.

!!! tip "Merging files"
    If a variable is defined in two files, the value from the last file will
    override the value from the first one.

In a fresh installation, LAVA installer will automatically create some setting files
for you:

* `/etc/lava-server/settings.d/00-secret-key.yaml`: django [SECRET_KEY]
* `/etc/lava-server/settings.d/00-database.yaml`: django [DATABASES]

You can then create some file to customize your instance.
The list of available values is listed in:

* [Django settings](https://docs.djangoproject.com/en/3.2/ref/settings/)
* [LAVA settings](https://git.lavasoftware.org/lava/lava/-/blob/master/lava_server/settings/common.py)

!!! warning "Legacy configuration"
    In previous LAVA versions, the settings where saved in three files:

    * `/etc/lava-server/settings.conf` (json)
    * `/etc/lava-server/secret_key.conf` (json)
    * `/etc/lava-server/instance.conf` (ini)

    LAVA will still load this files prior to load the new setting files.

!!! tip "Applying changes"
    When updating the settings, you should restart **every** LAVA services.


### Environment variables

Admins can also pass settings via environment variables. This is mainly used in
cloud setup like docker-compose or k8s.

The following variables are supported:

* `ALLOWED_HOSTS`
* `DATABASE_URL` (see django-url documentation)
* `INSTANCE_NAME`
* `SECRET_KEY`
* `LAVA_SETTINGS_*` (without the `LAVA_SETTINGS_` prefix).

In order to add complex types, admins can use `LAVA_JSON_SETTINGS`. This
variable should contain a dictionary of settings as a json string base64
encoded.

```python
import base64
import json

data = {
  "WORKER_AUTO_REGISTER_NETMASK": ["::1"]
}
print(base64.b64encode(json.dumps(data).encode("utf-8")).decode("utf-8"))
```

In order to use it, add to the environment: `LAVA_JSON_SETTINGS="eyJXT1JLRVJfQVVUT19SRUdJU1RFUl9ORVRNQVNLIjogWyI6OjEiXX0="`.

## Worker configuration

### Devices

The device dictionaries are stored into `/etc/lava-server/dispatcher-config/devices/`.
The files should belong to `lavaserver` user and group.

More information in the [technical reference](../../../technical-references/configuration/device-dictionary.md).

### Device-types

The device-type templates are stored into `/etc/lava-server/dispatcher-config/device-types/`
The files should belong to `lavaserver` user and group.

For supported device-types, the templates provided by LAVA are stored in
`/usr/share/lava-server/device-types`. LAVA looks for the template first in
`/etc/lava-server/dispatcher-config/device-types/` and then fallback to
`/usr/share/lava-server/device-types`.

More information in the [technical reference](../../../technical-references/configuration/device-type-template.md).

### Health-checks

The health-checks are stored into `/etc/lava-server/dispatcher-config/health-checks/`
The files should belong to `lavaserver` user and group.

More information in the [technical reference](../../../technical-references/configuration/health-check.md).

### Dispatcher

!!! warning "TODO"

--8<-- "refs.txt"
