# LAVA celery worker

Run the celery worker for lava.

## Command line

This daemon is started by celery using `python3 -m celery`.

## Service

The systemd service is called `lava-celery-worker`.

## Dependencies

lava-celery-worker should be able to:

* connect to the celery broker (rabbitmq, redis, ...)
* connect to the [postgresql](./postgresql.md) database

## Configuration

Daemon start options:

* `/etc/default/lava-celery-worker`
* `/etc/lava-server/lava-celery-worker`

Django configuration:

* `/etc/lava-server/settings.conf`
* `/etc/lava-server/settings.yaml`
* `/etc/lava-server/settings.d/*.yaml`

## Logs

The logs are stored in `/var/log/lava-server/lava-celery-worker.log`

The log rotation is configured in `/etc/logrotate.d/lava-celery-worker-log`.
