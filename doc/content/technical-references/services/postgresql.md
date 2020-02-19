# PostgreSQL

Store the different objects like Device, DeviceType, TestJob, ...

## Command line

This service is usually only manage via systemd.

## Service

The systemd service is called `postgresql`.

## Logs

The logs are stored under `/var/log/posqtgresql/`

The log rotation is configured in `/etc/logrotate.d/postgresql-common`.
