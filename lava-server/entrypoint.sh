#!/usr/bin/env bash
set -e

# Keep track of the PIDs
GUNICORN_PID=0
LAVA_LOGS_PID=0
LAVA_MASTER_PID=0
LAVA_PUBLISHER_PID=0

# Signal handler
handler() {
    tail_pid="${!}"
    echo "Killing:"
    echo "* lava-logs \$$LAVA_LOGS_PID"
    kill $LAVA_LOGS_PID
    echo "* lava-master \$$LAVA_MASTER_PID"
    kill $LAVA_MASTER_PID
    echo "* lava-publisher \$$LAVA_PUBLISHER_PID"
    kill $LAVA_PUBLISHER_PID
    echo "* gunicorn \$$GUNICORN_PID"
    kill $GUNICORN_PID
    echo "* apache2"
    /etc/init.d/apache2 stop

    echo "Waiting for:"
    echo "* lava-logs"
    wait $LAVA_LOGS_PID || true
    echo "* lava-master"
    wait $LAVA_MASTER_PID || true
    echo "* lava-publisher"
    wait $LAVA_PUBLISHER_PID || true
    echo "* gunicorn"
    wait $GUNICORN_PID || true

    echo "Killing postgresql"
    /etc/init.d/postgresql stop

    echo "Killing log reader"
    kill "$tail_pid"
    wait "$tail_pid"
    exit 0
}

# setup handlers
trap 'handler' SIGTERM

# Start all services
echo "Starting postgresql"
/etc/init.d/postgresql start
echo "done"
echo

echo "Applying migrations"
lava-server manage migrate
echo "done"
echo

echo "Starting gunicorn3"
gunicorn3 lava_server.wsgi&
GUNICORN_PID=$!
echo "done"
echo

echo "Starting apache2"
/etc/init.d/apache2 start
echo "done"
echo

echo "Starting lava-logs"
lava-server manage lava-logs&
LAVA_LOGS_PID=$!
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

# Wait for signals
cd /var/log/lava-server
while true
do
  tail -f --retry django.log gunicorn.log lava-logs.log lava-master.log lava-publisher.log & wait ${!}
done
