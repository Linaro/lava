# LAVA slave

Manage local lava jobs for attached DUTs.

## Command line

Run `/usr/bin/lava-slave`.

## Service

The systemd service is called `lava-slave`.

## Dependencies

lava-slave should be able to:

* connect to [lava-master](../lava-master)
* connect to [lava-logs](../lava-logs)

## Configuration

Daemon start options:

* `/etc/default/lava-slave`
* `/etc/lava-server/lava-slave`

## Logs

The logs are stored in `/var/log/lava-dispatcher/lava-slave.log`

The log rotation is configured in `/etc/logrotate.d/lava-slave-log`.

## Security

TODO: should activate encryption
