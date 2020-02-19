# LAVA server gunicorn

`lava-server-gunicorn` is the web server that will handle http requests comming
from users.

This process will not serve static files that are handled directly by
[apache2](../apache2).

## Command line

Run `gunicorn lava-server.wsgi`

## Service

The systemd service is called `lava-server-gunicorn`.

## Dependencies

lava-logs should be able to:

* connect to the [postgresql](../postgresql) database
* open a socket on port `8000`

## Configuration

Daemon start options:

* `/etc/default/lava-server-gunicorn`
* `/etc/lava-server/lava-server-gunicorn`

Django configuration:

* `/etc/lava-server/instance.conf`
* `/etc/lava-server/settings.conf`

## Logs

The logs are stored in `/var/log/lava-server/gunicorn.log` and
`/var/log/lava-server/django.log`.

The log rotation is configured in `/etc/logrotate.d/lava-server-gunicorn-log`
and `/etc/logrotate.d/django-log`.

## Security

This process should be always behind a reverse proxy like
[apache2](../apache2).
