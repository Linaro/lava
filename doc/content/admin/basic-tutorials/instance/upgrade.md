# Upgrade LAVA

## When to upgrade

We advice to always upgrade to the latest released version. Only the latest
release will include new features and bug fixes (including security issues).

## How to upgrade

Currently, LAVA does not allow for zero-downtime upgrade.

We advice to put the instance in maintenance before any upgrade.

!!! example "Maintenance mode"

    === "docker-compose"
        ```shell
        docker-compose exec lava-server lava-server manage maintenance
        ```

    === "debian"
        ```shell
        lava-server manage maintenance
        ```

    === "lavacli"
        ```shell
        lavacli system maintenance
        ```


### Docker

When a new version of LAVA is released, a Docker image is published on [docker hub][lava-docker-hub].

In order to upgrade, admins should just pull the latest **docker-compose
configuration**:

```shell
git pull --rebase
```

The restarting docker-compose will enough:

```shell
docker-compose pull
docker-compose up
```

??? tip "Downtime during upgrade"
    The current setup does not allow for zero-downtime upgrade without a
    management layer like [docker swarm](https://docs.docker.com/engine/swarm/)
    or [kubernetes](https://kubernetes.io/).

### Debian

When a new version of LAVA is released, a new Debian package is published on
the official [Debian repository][lava-debian].

You can upgrade using **apt**:

```shell
apt-get update
apt-get upgrade
```

??? tip "Downtime during upgrade"
    Zero-downtime upgrade is not possible with the current Debian packages.
    During the upgrade, every services will be stopped while upgrading.

## Upgrade notifications

Different version compatibility in LAVA between server and worker
instances is not guaranteed at the moment.

When a LAVA server instance is upgraded, if the specific flag in settings is
provided, the system will send out email notifications reminding admins that
the worker instances need to be upgraded as well.

```yaml
"MASTER_UPGRADE_NOTIFY": false
```

The default value for this flag is False so admin action is required in order
to use this feature.

Each user that has a 'change_worker' permission over the at least one worker
(which is not of the same version as the LAVA server) will get an email
with the list of workers which require an upgrade.
If the user is superuser, he will be regarded as having permission over all the
workers in the system, so that kind of user will get the full list of the
workers which require an upgrade.


## Rollback

!!! warning "TODO"

--8<-- "refs.txt"
