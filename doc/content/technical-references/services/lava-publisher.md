# LAVA publisher

Receive and forward events coming from lava services.

## Command line

This daemon is part of lava-server and is started by: `lava-server manage lava-publisher`.

## Service

The systemd service is called `lava-publisher`.

## Dependencies

lava-publisher should be able to:

* open a socket on `/tmp/lava.events`
* open a socket on port `5500`
* open a socket on port `8001`

The services that generate events
([lava-server-gunicorn](./lava-server-gunicorn.md)) should be able to write to
the local socket.

## Configuration

Daemon start options:

* `/etc/default/lava-publisher`
* `/etc/lava-server/lava-publisher`

Django configuration:

* `/etc/lava-server/settings.conf`
* `/etc/lava-server/settings.yaml`
* `/etc/lava-server/settings.d/*.yaml`

## Logs

The logs are stored in `/var/log/lava-server/lava-publisher.log`

The log rotation is configured in `/etc/logrotate.d/lava-publisher-log`.
