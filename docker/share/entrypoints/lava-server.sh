#!/usr/bin/env bash

set -e

[ -n "$1" ] && exec "$@"

#############
# Variables #
#############
GUNICORN_PID=0
LAVA_COORDINATOR=0
LAVA_LOGS_PID=0
LAVA_MASTER_PID=0
LAVA_PUBLISHER_PID=0


##################
# Signal handler #
##################
handler() {
    tail_pid="${!}"
    echo "Killing:"
    echo "* lava-coordinator \$$LAVA_COORDINATOR_PID"
    [ "$LAVA_COORDINATOR_PID" != "0" ] && kill $LAVA_COORDINATOR_PID
    echo "* lava-logs \$$LAVA_LOGS_PID"
    [ "$LAVA_LOGS_PID" != "0" ] && kill $LAVA_LOGS_PID
    echo "* lava-master \$$LAVA_MASTER_PID"
    [ "$LAVA_MASTER_PID" != "0" ] && kill $LAVA_MASTER_PID
    echo "* lava-publisher \$$LAVA_PUBLISHER_PID"
    [ "$LAVA_PUBLISHER_PID" != "0" ] && kill $LAVA_PUBLISHER_PID
    echo "* gunicorn \$$GUNICORN_PID"
    [ "$GUNICORN_PID" != "0" ] && kill $GUNICORN_PID
    echo "* apache2"
    apache2ctl stop

    echo "Waiting for:"
    echo "* lava-coordinator"
    [ "$LAVA_COORDINATOR_PID" != "0" ] && wait $LAVA_COORDINATOR_PID || true
    echo "* lava-logs"
    [ "$LAVA_LOGS_PID" != "0" ] && wait $LAVA_LOGS_PID || true
    echo "* lava-master"
    [ "$LAVA_MASTER_PID" != "0" ] && wait $LAVA_MASTER_PID || true
    echo "* lava-publisher"
    [ "$LAVA_PUBLISHER_PID" != "0" ] && wait $LAVA_PUBLISHER_PID || true
    echo "* gunicorn"
    [ "$GUNICORN_PID" != "0" ] && wait $GUNICORN_PID || true

    echo "Killing postgresql"
    /etc/init.d/postgresql stop

    echo "Killing log reader"
    [ -n "$tail_pid" ] && kill "$tail_pid"
    exit 0
}


#####################
# Check file owners #
#####################
check_owners() {
    files=$(find /etc/lava-server/dispatcher-config/ /var/lib/lava-server/default/media/ -not -user lavaserver)
    if [ "$files" ]; then
        echo "The following files should belong to 'lavaserver' user:"
        echo "$files"
        exit 1
    fi
    files=$(find /etc/lava-server/dispatcher-config/ /var/lib/lava-server/default/media/ -not -group lavaserver)
    if [ "$files" ]; then
        echo "The following files should belong to 'lavaserver' group:"
        echo "$files"
        exit 1
    fi
}


#################
# Start helpers #
#################
start_apache2() {
    export APACHE_CONFDIR=/etc/apache2
    export APACHE_ENVVARS=/etc/apache2/envvars
    if [ "$CAN_EXEC" = "1" ]; then
        exec apache2ctl -DFOREGROUND
    else
        apache2ctl -DFOREGROUND &
    fi
}


start_lava_coordinator() {
    LOGLEVEL="DEBUG"
    LOGFILE="/var/log/lava-coordinator.log"
    [ -e /etc/default/lava-coordinator ] && . /etc/default/lava-coordinator
    [ -e /etc/lava-coordinator/lava-coordinator ] && . /etc/lava-coordinator/lava-coordinator
    if [ "$CAN_EXEC" = "1" ]; then
        exec /usr/bin/lava-coordinator --logfile - --loglevel "$LOGLEVEL"
    else
        /usr/bin/lava-coordinator --logfile "$LOGFILE" --loglevel "$LOGLEVEL" &
        LAVA_COORDINATOR_PID=$!
    fi
}


start_lava_logs() {
    LOGLEVEL=DEBUG
    [ -e /etc/default/lava-logs ] && . /etc/default/lava-logs
    [ -e /etc/lava-server/lava-logs ] && . /etc/lava-server/lava-logs
    if [ "$CAN_EXEC" = "1" ]; then
        exec /usr/bin/lava-server manage lava-logs --log-file - --level "$LOGLEVEL" $SOCKET $MASTER_SOCKET $IPV6 $ENCRYPT $MASTER_CERT $SLAVES_CERTS
    else
        /usr/bin/lava-server manage lava-logs --level "$LOGLEVEL" $SOCKET $MASTER_SOCKET $IPV6 $ENCRYPT $MASTER_CERT $SLAVES_CERTS &
        LAVA_LOGS_PID=$!
    fi
}


start_lava_master() {
    LOGLEVEL=DEBUG
    [ -e /etc/default/lava-master ] && . /etc/default/lava-master
    [ -e /etc/lava-server/lava-master ] && . /etc/lava-server/lava-master
    if [ "$CAN_EXEC" = "1" ]; then
        exec /usr/bin/lava-server manage lava-master --log-file - --level "$LOGLEVEL" $MASTER_SOCKET $IPV6 $ENCRYPT $MASTER_CERT $SLAVES_CERTS $EVENT_URL
    else
        /usr/bin/lava-server manage lava-master --level "$LOGLEVEL" $MASTER_SOCKET $IPV6 $ENCRYPT $MASTER_CERT $SLAVES_CERTS $EVENT_URL &
        LAVA_MASTER_PID=$!
    fi
}


start_lava_publisher() {
    if [ "$CAN_EXEC" = "1" ]; then
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
    if [ "$CAN_EXEC" = "1" ]; then
        exec /usr/bin/gunicorn3 lava_server.wsgi --log-level "$LOGLEVEL" --log-file - -u lavaserver -g lavaserver --workers "$WORKERS" --worker-tmp-dir /dev/shm $RELOAD $BIND
    else
        /usr/bin/gunicorn3 lava_server.wsgi --log-level "$LOGLEVEL" --log-file "$LOGFILE" -u lavaserver -g lavaserver --workers "$WORKERS" --worker-tmp-dir /dev/shm $RELOAD $BIND &
        GUNICORN_PID=$!
    fi
}


########
# Main #
########

# setup handlers
trap 'handler' INT QUIT TERM

# List of services to start
SERVICES=${SERVICES-"apache2 lava-coordinator lava-logs lava-master lava-publisher gunicorn postgresql"}
echo "$SERVICES" | grep -q apache2 && APACHE2=1 || APACHE2=0
echo "$SERVICES" | grep -q lava-coordinator && LAVA_COORDINATOR=1 || LAVA_COORDINATOR=0
echo "$SERVICES" | grep -q lava-logs && LAVA_LOGS=1 || LAVA_LOGS=0
echo "$SERVICES" | grep -q lava-master && LAVA_MASTER=1 || LAVA_MASTER=0
echo "$SERVICES" | grep -q lava-publisher && LAVA_PUBLISHER=1 || LAVA_PUBLISHER=0
echo "$SERVICES" | grep -q gunicorn && GUNICORN=1 || GUNICORN=0
echo "$SERVICES" | grep -q postgresql && POSTGRESQL=1 || POSTGRESQL=0

# Is the database needed?
NEED_DB=$((LAVA_LOGS+LAVA_MASTER+GUNICORN+POSTGRESQL))
# Migrate if LAVA_DB_MIGRATE is undefined and lava-master is running in this
# container.
[ "$LAVA_MASTER" = "1" ] && MIGRATE_DEFAULT="yes" || MIGRATE_DEFAULT="no"
LAVA_DB_MIGRATE=${LAVA_DB_MIGRATE:-$MIGRATE_DEFAULT}
# Should we use "exec"?
CAN_EXEC=$((APACHE2+LAVA_LOGS+LAVA_MASTER+LAVA_PUBLISHER+GUNICORN+POSTGRESQL))
# Should we check for file owners?
LAVA_CHECK_OWNERS=${LAVA_CHECK_OWNERS:-1}

echo "Creating instance.conf (if needed)"
/usr/share/lava-server/postinst.py --config
echo "done"
echo

# Start requested services
if [ "$POSTGRESQL" = "1" ]
then
    echo "Starting postgresql"
    /etc/init.d/postgresql start
    echo "done"
    echo
    echo "Setup the database"
    /usr/share/lava-server/postinst.py --db
    echo "done"
    echo
fi

if [ "$NEED_DB" != "0" ]
then
    lava-server manage wait database
    if [ "$LAVA_DB_MIGRATE" = "yes" ]
    then
        echo "Applying migrations"
        lava-server manage migrate --no-input
    else
        echo "Waiting for migrations"
        lava-server manage wait migrations
    fi
    echo "done"
    echo
fi

if [ "$LAVA_SITE" != "" ]
then
    echo "Setting lava site: $LAVA_SITE"
    lava-server manage site update --name "$LAVA_SITE" --domain "$LAVA_SITE"
    echo "done"
    echo
fi

# Run user scripts. The database is running and migrations has been run.
for f in $(find /root/entrypoint.d/ -type f); do
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

if [ "$GUNICORN" = "1" ]
then
    echo "Checking file permissions"
    if [ "$LAVA_CHECK_OWNERS" = "1" ]
    then
        check_owners
        echo "done"
    else
        echo "skipped"
    fi
    echo
    echo "Starting gunicorn3"
    start_lava_server_gunicorn
    echo "done"
    echo
fi

if [ "$APACHE2" = "1" ]
then
    echo "Starting apache2"
    start_apache2
    echo "done"
    echo
fi

if [ "$LAVA_COORDINATOR" = "1" ]
then
    echo "Starting lava-coordinator"
    start_lava_coordinator
    echo "done"
    echo
fi

if [ "$LAVA_LOGS" = "1" ]
then
    echo "Checking file permissions"
    if [ "$LAVA_CHECK_OWNERS" = "1" ]
    then
        check_owners
        echo "done"
    else
        echo "skipped"
    fi
    echo
    echo "Starting lava-logs"
    start_lava_logs
    echo "done"
    echo
fi


if [ "$LAVA_PUBLISHER" = "1" ]
then
    echo "Starting lava-publisher"
    start_lava_publisher
    echo "done"
    echo
fi

if [ "$LAVA_MASTER" = "1" ]
then
    echo "Starting lava-master"
    start_lava_master
    echo "done"
    echo
fi

################
# Wait forever #
################
cd /var/log/lava-server
while true
do
  tail -F django.log gunicorn.log lava-logs.log lava-master.log lava-publisher.log /var/log/lava-coordinator.log /var/log/apache2/lava-server.log & wait ${!}
done
