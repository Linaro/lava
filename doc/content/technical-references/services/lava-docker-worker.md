# LAVA docker worker

Start lava-worker inside a docker container, matching the server version.

## Command line

Run `/usr/bin/lava-docker-worker`.

## Service

The systemd service is called `lava-docker-worker`.

## Dependencies

lava-docker-worker should be able to:

* use docker

## Configuration

Daemon start options:

* `/etc/default/lava-docker-worker`
* `/etc/lava-server/lava-docker-worker`

## Logs

The logs are stored in `/var/log/lava-dispatcher-host/lava-docker-worker.log`

The log rotation is configured in `/etc/logrotate.d/lava-docker-worker-log`.

## Security

TODO: should activate encryption
