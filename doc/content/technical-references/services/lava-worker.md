# LAVA worker

Manage local lava jobs for attached DUTs.

## Command line

Run `/usr/bin/lava-worker`.

## Service

The systemd service is called `lava-worker`.

## Dependencies

lava-worker should be able to:

* connect to [lava-server-gunicorn](./lava-server-gunicorn.md)

## Configuration

Daemon start options:

* `/etc/default/lava-worker`
* `/etc/lava-server/lava-worker`

## Logs

The logs are stored in `/var/log/lava-dispatcher/lava-worker.log`

The log rotation is configured in `/etc/logrotate.d/lava-worker-log`.

## Security

TODO: should activate encryption
