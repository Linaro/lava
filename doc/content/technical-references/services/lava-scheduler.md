# LAVA scheduler

This process is is responsible for scheduling jobs on devices.

## Command line

This daemon is part of lava-server and is started by: `lava-server manage lava-scheduler`

## Service

The systemd service is called `lava-scheduler`.

## Dependencies

lava-scheduler should be able to:

* connect to the [postgresql](./postgresql.md) database
* connect to [lava-publisher](./lava-publisher.md) PUB socket.

## Configuration

Daemon start options:

* `/etc/default/lava-scheduler`
* `/etc/lava-server/lava-scheduler`

Django configuration:

* `/etc/lava-server/settings.conf`
* `/etc/lava-server/settings.yaml`
* `/etc/lava-server/settings.d/*.yaml`

## Logs

The logs are stored in `/var/log/lava-server/lava-scheduler.log`

The log rotation is configured in `/etc/logrotate.d/lava-scheduler-log`.
