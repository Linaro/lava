#!/bin/sh

set -e

[ -n "$@" ] && exec $@ || :

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
LAVA_PUBLISHER_PID=$!
echo "done"
echo

echo "Starting lava-master"
lava-server manage lava-master&
LAVA_MASTER_PID=$!
echo "done"
echo

echo "Wait for a signal"
/bin/sleep infinity
echo "leaving"
