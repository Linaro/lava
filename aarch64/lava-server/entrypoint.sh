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
    [[ "$LAVA_LOGS_PID" != "0" ]] && kill $LAVA_LOGS_PID
    echo "* lava-master \$$LAVA_MASTER_PID"
    [[ "$LAVA_MASTER_PID" != "0" ]] && kill $LAVA_MASTER_PID
    echo "* lava-publisher \$$LAVA_PUBLISHER_PID"
    [[ "$LAVA_PUBLISHER_PID" != "0" ]] && kill $LAVA_PUBLISHER_PID
    echo "* gunicorn \$$GUNICORN_PID"
    [[ "$GUNICORN_PID" != "0" ]] && kill $GUNICORN_PID
    echo "* apache2"
    /etc/init.d/apache2 stop

    echo "Waiting for:"
    echo "* lava-logs"
    [[ "$LAVA_LOGS_PID" != "0" ]] && wait $LAVA_LOGS_PID
    echo "* lava-master"
    [[ "$LAVA_MASTER_PID" != "0" ]] && wait $LAVA_MASTER_PID
    echo "* lava-publisher"
    [[ "$LAVA_PUBLISHER_PID" != "0" ]] && wait $LAVA_PUBLISHER_PID
    echo "* gunicorn"
    [[ "$GUNICORN_PID" != "0" ]] && wait $GUNICORN_PID

    echo "Killing postgresql"
    /etc/init.d/postgresql stop

    echo "Killing log reader"
    kill "$tail_pid"
    exit 0
}


#################
# Start helpers #
#################
start_apache2() {
    if [[ "$CAN_EXEC" == "1" ]]; then
        export APACHE_CONFDIR=/etc/apache2
        export APACHE_ENVVARS=/etc/apache2/envvars
        exec apache2ctl -DFOREGROUND
    else
        /etc/init.d/apache2 start
    fi
}


start_lava_logs() {
    LOGLEVEL=DEBUG
    [ -e /etc/default/lava-logs ] && . /etc/default/lava-logs
    [ -e /etc/lava-server/lava-logs ] && . /etc/lava-server/lava-logs
    if [[ "$CAN_EXEC" == "1" ]]; then
        exec /usr/bin/lava-server manage lava-logs --log-file - --level $LOGLEVEL $SOCKET $MASTER_SOCKET $IPV6 $ENCRYPT $MASTER_CERT $SLAVES_CERTS
    else
        /usr/bin/lava-server manage lava-logs --level $LOGLEVEL $SOCKET $MASTER_SOCKET $IPV6 $ENCRYPT $MASTER_CERT $SLAVES_CERTS &
        LAVA_LOGS_PID=$!
    fi
}


start_lava_master() {
    LOGLEVEL=DEBUG
    [ -e /etc/default/lava-master ] && . /etc/default/lava-master
    [ -e /etc/lava-server/lava-master ] && . /etc/lava-server/lava-master
    if [[ "$CAN_EXEC" == "1" ]]; then
        exec /usr/bin/lava-server manage lava-master --log-file - --level $LOGLEVEL $MASTER_SOCKET $IPV6 $ENCRYPT $MASTER_CERT $SLAVES_CERTS
    else
        /usr/bin/lava-server manage lava-master --level $LOGLEVEL $MASTER_SOCKET $IPV6 $ENCRYPT $MASTER_CERT $SLAVES_CERTS &
        LAVA_MASTER_PID=$!
    fi
}


start_lava_publisher() {
    if [[ "$CAN_EXEC" == "1" ]]; then
        exec /usr/bin/lava-server manage lava-publisher --log-file -
    else
        /usr/bin/lava-server manage lava-publisher &
        LAVA_PUBLISHER_PID=$!
    fi
}

start_lava_server_gunicorn() {
    LOGLEVEL="DEBUG"
    WORKERS="4"
    LOGFILE="/var/log/lava-server/gunicorn.log"
    [ -e /etc/default/lava-server-gunicorn ] && . /etc/default/lava-server-gunicorn
    [ -e /etc/lava-server/lava-server-gunicorn ] && . /etc/lava-server/lava-server-gunicorn
    if [[ "$CAN_EXEC" == "1" ]]; then
        exec /usr/bin/gunicorn3 lava_server.wsgi --log-level $LOGLEVEL --log-file - -u lavaserver -g lavaserver --workers $WORKERS $RELOAD $BIND
    else
        /usr/bin/gunicorn3 lava_server.wsgi --log-level $LOGLEVEL --log-file $LOGFILE -u lavaserver -g lavaserver --workers $WORKERS $RELOAD $BIND &
        GUNICORN_PID=$!
    fi
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


###########################
# wait for the migrations #
###########################
check_migration() {
    migrations=$(lava-server manage showmigrations --plan)
    if [[ "$?" != "0" ]]
    then
        return 1
    fi
    return $(echo $migrations | grep "\[ \]" | wc -l)
}

wait_migration() {
    until check_migration
    do
        echo "."
        sleep 1
    done
}


########
# Main #
########

# setup handlers
trap 'handler' INT QUIT TERM

# List of services to start
SERVICES=${SERVICES-"apache2 lava-logs lava-master lava-publisher gunicorn postgresql"}
[[ "$SERVICES" == *"apache2"* ]] && APACHE2=1 || APACHE2=0
[[ "$SERVICES" == *"lava-logs"* ]] && LAVA_LOGS=1 || LAVA_LOGS=0
[[ "$SERVICES" == *"lava-master"* ]] && LAVA_MASTER=1 || LAVA_MASTER=0
[[ "$SERVICES" == *"lava-publisher"* ]] && LAVA_PUBLISHER=1 || LAVA_PUBLISHER=0
[[ "$SERVICES" == *"gunicorn"* ]] && GUNICORN=1 || GUNICORN=0
[[ "$SERVICES" == *"postgresql"* ]] && POSTGRESQL=1 || POSTGRESQL=0

# Is the database needed?
NEED_DB=$((LAVA_LOGS+LAVA_MASTER+GUNICORN+POSTGRESQL))
# Migrate if LAVA_DB_MIGRATE is undefined and lava-master is running in this
# container.
[[ "$LAVA_MASTER" == "1" ]] && MIGRATE_DEFAULT="yes" || MIGRATE_DEFAULT="no"
LAVA_DB_MIGRATE=${LAVA_DB_MIGRATE:-$MIGRATE_DEFAULT}
# Should we use "exec"?
CAN_EXEC=$((APACHE2+LAVA_LOGS+LAVA_MASTER+LAVA_PUBLISHER+GUNICORN+POSTGRESQL))

# Start requested services
if [[ "$POSTGRESQL" == "1" ]]
then
    echo "Starting postgresql"
    /etc/init.d/postgresql start
    echo "done"
    echo
fi

if [[ "$NEED_DB" != "0" ]]
then
    echo "Waiting for postgresql"
    wait_postgresql
    echo "done"
    echo
    if [[ "$LAVA_DB_MIGRATE" == "yes" ]]
    then
        echo "Applying migrations"
        lava-server manage migrate
    else
        echo "Waiting for migrations"
        wait_migration
    fi
    echo "done"
    echo
fi

if [[ "$GUNICORN" == "1" ]]
then
    echo "Starting gunicorn3"
    start_lava_server_gunicorn
    echo "done"
    echo
fi

if [[ "$APACHE2" == "1" ]]
then
    echo "Starting apache2"
    start_apache2
    echo "done"
    echo
fi

if [[ "$LAVA_LOGS" == "1" ]]
then
    echo "Starting lava-logs"
    start_lava_logs
    echo "done"
    echo
fi


if [[ "$LAVA_PUBLISHER" == "1" ]]
then
    echo "Starting lava-publisher"
    start_lava_publisher
    echo "done"
    echo
fi

if [[ "$LAVA_MASTER" == "1" ]]
then
    echo "Starting lava-master"
    start_lava_master
    echo "done"
    echo
fi

for f in /root/entrypoint.d/*; do
    case "$f" in
        *.sh)
            echo "$0: running ${f}"
            "${f}"
            ;;
        *)
        echo "$0: ignoring ${f}"
        ;;
    esac
done

################
# Wait forever #
################
cd /var/log/lava-server
while true
do
  tail -f --retry django.log gunicorn.log lava-logs.log lava-master.log lava-publisher.log & wait ${!}
done
