#!/usr/bin/env bash

set -e

[ -n "$1" ] && exec "$@"

#############
# Variables #
#############
GUNICORN_PID=0
LAVA_CELERY_WORKER_PID=0
LAVA_COORDINATOR_PID=0
LAVA_PUBLISHER_PID=0
LAVA_SCHEDULER_PID=0


##################
# Signal handler #
##################
handler() {
    tail_pid="${!}"
    echo "Killing:"
    echo "* lava-celery-worker \$$LAVA_CELERY_WORKER_PID"
    [ "$LAVA_CELERY_WORKER_PID" != "0" ] && kill $LAVA_CELERY_WORKER_PID
    echo "* lava-coordinator \$$LAVA_COORDINATOR_PID"
    [ "$LAVA_COORDINATOR_PID" != "0" ] && kill $LAVA_COORDINATOR_PID
    echo "* lava-publisher \$$LAVA_PUBLISHER_PID"
    [ "$LAVA_PUBLISHER_PID" != "0" ] && kill $LAVA_PUBLISHER_PID
    echo "* lava-scheduler \$$LAVA_SCHEDULER_PID"
    [ "$LAVA_SCHEDULER_PID" != "0" ] && kill $LAVA_SCHEDULER_PID
    echo "* gunicorn \$$GUNICORN_PID"
    [ "$GUNICORN_PID" != "0" ] && kill $GUNICORN_PID
    echo "* apache2"
    apache2ctl stop

    echo "Waiting for:"
    echo "* lava-celery-worker"
    [ "$LAVA_CELERY_WORKER_PID" != "0" ] && wait $LAVA_CELERY_WORKER_PID || true
    echo "* lava-coordinator"
    [ "$LAVA_COORDINATOR_PID" != "0" ] && wait $LAVA_COORDINATOR_PID || true
    echo "* lava-publisher"
    [ "$LAVA_PUBLISHER_PID" != "0" ] && wait $LAVA_PUBLISHER_PID || true
    echo "* lava-scheduler"
    [ "$LAVA_SCHEDULER_PID" != "0" ] && wait $LAVA_SCHEDULER_PID || true
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


start_lava_celery_worker() {
    USER="lavaserver"
    GROUP="lavaserver"
    LOGLEVEL=${CELERY_LOGLEVEL:-INFO}
    LOGFILE="/var/log/lava-server/lava-celery-worker.log"
    CONCURRENCY=${CELERY_CONCURRENCY:-}
    AUTOSCALE=${CELERY_AUTOSCALE:-}
    ARGS=${CELERY_ARGS:-}
    [ -e /etc/default/lava-celery-worker ] && . /etc/default/lava-celery-worker
    [ -e /etc/lava-server/lava-celery-worker ] && . /etc/lava-server/lava-celery-worker
    if [ "$CAN_EXEC" = "1" ]; then
        exec /usr/bin/python3 -m celery -A lava_server worker --uid $USER --gid $GROUP --loglevel $LOGLEVEL $CONCURRENCY $AUTOSCALE $ARGS
    else
        setsid /usr/bin/python3 -m celery -A lava_server worker --uid $USER --gid $GROUP --loglevel $LOGLEVEL --logfile $LOGFILE $CONCURRENCY $AUTOSCALE $ARGS &
        LAVA_CELERY_WORKER_PID=$!
    fi
}

start_lava_coordinator() {
    LOGLEVEL=${COORDINATOR_LOGLEVEL:-DEBUG}
    LOGFILE="/var/log/lava-coordinator.log"
    [ -e /etc/default/lava-coordinator ] && . /etc/default/lava-coordinator
    [ -e /etc/lava-coordinator/lava-coordinator ] && . /etc/lava-coordinator/lava-coordinator
    if [ "$CAN_EXEC" = "1" ]; then
        exec /usr/bin/lava-coordinator --logfile - --loglevel "$LOGLEVEL"
    else
        setsid /usr/bin/lava-coordinator --logfile "$LOGFILE" --loglevel "$LOGLEVEL" &
        LAVA_COORDINATOR_PID=$!
    fi
}


start_lava_publisher() {
    LOGLEVEL=${PUBLISHER_LOGLEVEL:-DEBUG}
    HOST=${PUBLISHER_HOST:-*}
    PORT=${PUBLISHER_PORT:-8001}

    [ -e /etc/default/lava-publisher ] && . /etc/default/lava-publisher
    [ -e /etc/lava-server/lava-publisher ] && . /etc/lava-server/lava-publisher
    if [ "$CAN_EXEC" = "1" ]; then
        exec /usr/bin/lava-server manage lava-publisher --log-file - --level "$LOGLEVEL" --host "$HOST" --port "$PORT"
    else
        setsid /usr/bin/lava-server manage lava-publisher --level "$LOGLEVEL" --host "$HOST" --port "$PORT" &
        LAVA_PUBLISHER_PID=$!
    fi
}


start_lava_scheduler() {
    LOGLEVEL=${SCHEDULER_LOGLEVEL:-DEBUG}
    EVENT_URL=${SCHEDULER_EVENT_URL:-}
    IPV6=${SCHEDULER_IPV6:-}

    [ -e /etc/default/lava-scheduler ] && . /etc/default/lava-scheduler
    [ -e /etc/lava-server/lava-scheduler ] && . /etc/lava-server/lava-scheduler
    if [ "$CAN_EXEC" = "1" ]; then
        exec /usr/bin/lava-server manage lava-scheduler --log-file - --level "$LOGLEVEL" $EVENT_URL $IPV6
    else
        setsid /usr/bin/lava-server manage lava-scheduler --level "$LOGLEVEL" $EVENT_URL $IPV6 &
        LAVA_SCHEDULER_PID=$!
    fi
}


start_lava_server_gunicorn() {
    BIND=${GUNICORN_BIND:-}
    LOGLEVEL=${GUNICORN_LOGLEVEL:-DEBUG}
    TIMEOUT=${GUNICORN_TIMEOUT:-}
    WORKER_CLASS=${GUNICORN_WORKER_CLASS:-eventlet}
    WORKERS=${GUNICORN_WORKERS:-4}
    LOGFILE="/var/log/lava-server/gunicorn.log"
    EXTRA_ARGS=${GUNICORN_EXTRA_ARGS:-}

    [ -e /etc/default/lava-server-gunicorn ] && . /etc/default/lava-server-gunicorn
    [ -e /etc/lava-server/lava-server-gunicorn ] && . /etc/lava-server/lava-server-gunicorn
    if [ "$CAN_EXEC" = "1" ]; then
        exec /usr/bin/gunicorn3 lava_server.wsgi --log-level "$LOGLEVEL" --log-file - -u lavaserver -g lavaserver --worker-class "$WORKER_CLASS" --workers "$WORKERS" --worker-tmp-dir /dev/shm $RELOAD $BIND $TIMEOUT $EXTRA_ARGS
    else
        setsid /usr/bin/gunicorn3 lava_server.wsgi --log-level "$LOGLEVEL" --log-file "$LOGFILE" -u lavaserver -g lavaserver --worker-class "$WORKER_CLASS" --workers "$WORKERS" --worker-tmp-dir /dev/shm $RELOAD $BIND $TIMEOUT $EXTRA_ARGS &
        GUNICORN_PID=$!
    fi
}


########
# Main #
########

# setup handlers
trap 'handler' INT QUIT TERM

# List of services to start
# By default lava-celery-worker is not started because no broker is included
SERVICES=${SERVICES-"apache2 lava-coordinator lava-publisher lava-scheduler gunicorn postgresql"}
echo "$SERVICES" | grep -q apache2 && APACHE2=1 || APACHE2=0
echo "$SERVICES" | grep -q lava-celery-worker && LAVA_CELERY_WORKER=1 || LAVA_CELERY_WORKER=0
echo "$SERVICES" | grep -q lava-coordinator && LAVA_COORDINATOR=1 || LAVA_COORDINATOR=0
echo "$SERVICES" | grep -q lava-publisher && LAVA_PUBLISHER=1 || LAVA_PUBLISHER=0
echo "$SERVICES" | grep -q lava-scheduler && LAVA_SCHEDULER=1 || LAVA_SCHEDULER=0
echo "$SERVICES" | grep -q gunicorn && GUNICORN=1 || GUNICORN=0
echo "$SERVICES" | grep -q postgresql && POSTGRESQL=1 || POSTGRESQL=0

# Is the database needed?
NEED_DB=$((LAVA_SCHEDULER+GUNICORN+POSTGRESQL))
# Migrate if LAVA_DB_MIGRATE is undefined and lava-scheduler is running in this
# container.
[ "$LAVA_SCHEDULER" = "1" ] && MIGRATE_DEFAULT="yes" || MIGRATE_DEFAULT="no"
LAVA_DB_MIGRATE=${LAVA_DB_MIGRATE:-$MIGRATE_DEFAULT}
# Should we use "exec"?
CAN_EXEC=$((APACHE2+LAVA_CELERY_WORKER+LAVA_COORDINATOR+LAVA_PUBLISHER+LAVA_SCHEDULER+GUNICORN+POSTGRESQL))
# Should we check for file owners?
LAVA_CHECK_OWNERS=${LAVA_CHECK_OWNERS:-1}

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
    /usr/share/lava-server/postinst.py --config --db
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

if [ "$LAVA_ADMIN_USERNAME" != "" ] && [ "$LAVA_ADMIN_PASSWORD" != "" ]
then
    echo "Creating lava admin: $LAVA_ADMIN_USERNAME"
    lava-server manage users details "$LAVA_ADMIN_USERNAME" || lava-server manage users add --passwd "$LAVA_ADMIN_PASSWORD" --staff --superuser "$LAVA_ADMIN_USERNAME"
    echo "done"
    echo
fi

if [ "$LAVA_ADMIN_TOKEN" != "" ] && [ "$LAVA_ADMIN_USERNAME" != "" ]
then
    echo "Creating lava token for: ${LAVA_ADMIN_USERNAME} with secret ${LAVA_ADMIN_TOKEN}"
    lava-server manage tokens add --secret "$LAVA_ADMIN_TOKEN" --user "$LAVA_ADMIN_USERNAME" || true
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

if [ "$LAVA_CELERY_WORKER" = "1" ]
then
    echo "Starting lava-celery-worker"
    start_lava_celery_worker
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

if [ "$LAVA_PUBLISHER" = "1" ]
then
    echo "Starting lava-publisher"
    start_lava_publisher
    echo "done"
    echo
fi

if [ "$LAVA_SCHEDULER" = "1" ]
then
    echo "Starting lava-scheduler"
    start_lava_scheduler
    echo "done"
    echo
fi


################
# Wait forever #
################
cd /var/log/lava-server
while true
do
  tail -F django.log gunicorn.log lava-celery-worker.log lava-publisher.log lava-scheduler.log /var/log/lava-coordinator.log /var/log/apache2/lava-server.log & wait ${!}
done
