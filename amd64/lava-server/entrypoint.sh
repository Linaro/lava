#!/usr/bin/env bash

set -e

[ -n "$1" ] && exec "$@"

#############
# Variables #
#############
GUNICORN_PID=0
LAVA_LOGS_PID=0
LAVA_MASTER_PID=0
LAVA_PUBLISHER_PID=0


##################
# Signal handler #
##################
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
    exit 0
}


#################
# Start helpers #
#################
start_lava_logs() {
    LOGLEVEL=DEBUG
    [ -e /etc/default/lava-logs ] && . /etc/default/lava-logs
    [ -e /etc/lava-server/lava-logs ] && . /etc/lava-server/lava-logs
    /usr/bin/lava-server manage lava-logs --level $LOGLEVEL $SOCKET $MASTER_SOCKET $IPV6 $ENCRYPT $MASTER_CERT $SLAVES_CERTS &
    LAVA_LOGS_PID=$!
}


start_lava_master() {
    LOGLEVEL=DEBUG
    [ -e /etc/default/lava-master ] && . /etc/default/lava-master
    [ -e /etc/lava-server/lava-master ] && . /etc/lava-server/lava-master
    /usr/bin/lava-server manage lava-master --level $LOGLEVEL $MASTER_SOCKET $IPV6 $ENCRYPT $MASTER_CERT $SLAVES_CERTS &
    LAVA_MASTER_PID=$!
}


start_lava_server_gunicorn() {
    LOGLEVEL="DEBUG"
    WORKERS="4"
    LOGFILE="/var/log/lava-server/gunicorn.log"
    [ -e /etc/default/lava-server-gunicorn ] && . /etc/default/lava-server-gunicorn
    [ -e /etc/lava-server/lava-server-gunicorn ] && . /etc/lava-server/lava-server-gunicorn
    /usr/bin/gunicorn3 lava_server.wsgi --log-level $LOGLEVEL --log-file $LOGFILE -u lavaserver -g lavaserver --workers $WORKERS $RELOAD &
    GUNICORN_PID=$!
}


#######################
# wait for postgresql #
#######################
check_pgsql() {
    lava-server manage shell -c "import sys
from django.db import connections
try:
  connections['default'].cursor()
except Exception:
  sys.exit(1)
sys.exit(0)"
}

wait_postgresql() {
    until check_pgsql
    do
        echo -n "."
        sleep 1
    done
}


########
# Main #
########

# setup handlers
trap 'handler' INT QUIT TERM

# Start all services
echo "Starting postgresql"
/etc/init.d/postgresql start
echo "done"
echo

echo "Waiting for postgresql"
wait_postgresql
echo "[done]"
echo

echo "Applying migrations"
lava-server manage migrate
echo "done"
echo

echo "Starting gunicorn3"
start_lava_server_gunicorn
echo "done"
echo

echo "Starting apache2"
/etc/init.d/apache2 start
echo "done"
echo

echo "Starting lava-logs"
start_lava_logs
echo "done"
echo

echo "Starting lava-publisher"
lava-server manage lava-publisher &
LAVA_PUBLISHER_PID=$!
echo "done"
echo

echo "Starting lava-master"
start_lava_master
echo "done"
echo

################
# Wait forever #
################
cd /var/log/lava-server
while true
do
  tail -f --retry django.log gunicorn.log lava-logs.log lava-master.log lava-publisher.log & wait ${!}
done
