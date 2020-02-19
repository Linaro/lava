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

The services that generate events ([lava-logs](../lava-logs),
[lava-master](../lava-master) and
[lava-server-gunicorn](../lava-server-gunicorn)) should be able to write to the
local socket.

## Configuration

Daemon start options:

* `/etc/default/lava-publisher`
* `/etc/lava-server/lava-publisher`

Django configuration:

* `/etc/lava-server/instance.conf`
* `/etc/lava-server/settings.conf`

## Logs

The logs are stored in `/var/log/lava-server/lava-publisher.log`

The log rotation is configured in `/etc/logrotate.d/lava-publisher-log`.

## Security

TODO: should activate encryption
