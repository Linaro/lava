# Apache2

Apache2 is the reverse proxy that will be visible from the outside world.

This service is responsible for:

* forwarding http requests to [gunicorn](../lava-server-gunicorn)
* serving static files
* ssl termination

## Command line

This service is usually only manage via systemd.

## Service

The systemd service is called `apache2`.

## Dependencies

apache2 should be able to:

* open a socket on port `80`
* open a socket on port `443` (if configured)

## Configuration

The apache2 configuration is split in many files.

The configuration specific to lava is stored in
`/etc/apache2/sites-available/lava-server.conf`.

## Logs

The logs for thr lava-server virtual host are stored in
`/var/log/apache2/lava-server.log`

The log rotation is configured in `/etc/logrotate.d/apache2`.

## Security

TODO: should activate SSL
