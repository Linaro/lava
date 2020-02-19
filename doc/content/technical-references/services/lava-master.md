# LAVA master

This process is at the sametime the master and the scheduler. lava-master is
responsible for:

* keep track of remote [lava-slave](../lava-slave)
* schedule jobs
* start and cancel jobs
* keep track of jobs state

## Command line

This daemon is part of lava-server and is started by: `lava-server manage lava-master`

## Service

The systemd service is called `lava-master`.

## Dependencies

lava-logs should be able to:

* connect to the [postgresql](../postgresql) database
* visible to [lava-logs](../lava-master)
* visible to [lava-slave](../lava-slave)
* open a socket on port `5556`

## Configuration

Daemon start options:

* `/etc/default/lava-master`
* `/etc/lava-server/lava-master`

Django configuration:

* `/etc/lava-server/instance.conf`
* `/etc/lava-server/settings.conf`

## Logs

The logs are stored in `/var/log/lava-server/lava-master.log`

The log rotation is configured in `/etc/logrotate.d/lava-master-log`.

## Security

TODO: should activate encryption
