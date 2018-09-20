#!/bin/sh

set -e

[ -n "$1" ] && exec $@

echo "Starting postgresql"
service postgresql start
echo "done"
echo

echo "Starting gunicorn3"
gunicorn3 lava_server.wsgi&
echo "done"
echo

echo "Starting apache2"
service apache2 start
echo "done"
echo

echo "Starting lava-logs"
lava-server manage lava-logs&
echo "done"
echo

echo "Starting lava-publisher"
lava-server manage lava-publisher&
echo "done"
echo

echo "Starting lava-master"
lava-server manage lava-master&
echo "done"
echo

echo "Wait for a signal"
cd /var/log/lava-server
tail -f --retry django.log gunicorn.log lava-logs.log lava-master.log lava-publisher.log
echo "leaving"
