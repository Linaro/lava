# LAVA logs

Receive and store the logs sent by lava-run.
The logs are streamed over the network.

## Command line

This daemon is part of lava-server and is started by: `lava-server manage lava-logs`

## Service

The systemd service is called `lava-logs`.

## Dependencies

lava-logs should be able to:

* connect to the [postgresql](../postgresql) database
* connect to the [lava-master](../lava-master) socket
* open a socket on port `5555`
* write the job logs in `/var/lib/lava-server/default/media/job-output/`

## Configuration

Daemon start options:

* `/etc/default/lava-logs`
* `/etc/lava-server/lava-logs`

Django configuration:

* `/etc/lava-server/instance.conf`
* `/etc/lava-server/settings.conf`

## Logs

The logs are stored in `/var/log/lava-server/lava-logs.log`

The log rotation is configured in `/etc/logrotate.d/lava-logs-log`.

## Security

TODO: should activate encryption
