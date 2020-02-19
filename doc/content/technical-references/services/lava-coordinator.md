# LAVA coordinator

This service is receiving, storing and dispatching multinode messages.

Only one instance of this process should be running for a given lava instance. Usually, this instance is running on the server but this is not required.

## Command line

Run `/usr/bin/lava-coordinator`

## Service

The systemd service is called `lava-coordinator`.

## Dependencies

The process should be able to:

* open a socket on port `3079`

The process should be visible to every dispatchers.

## Configuration

Daemon start options:

* `/etc/default/lava-coordinator`

In order to connect to the coordinator, configuration file
`/etc/lava-coordinator/lava-coordinator.conf` should be copied on each
dispatcher.

## Logs

The logs are stored in `/var/log/lava-coordinator.log`

The log rotation is configured in `/etc/logrotate.d/lava-coordinator-log`.

## Security

It's currently adviced to restrict connections to the private network.
