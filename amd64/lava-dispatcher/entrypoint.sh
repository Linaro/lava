#!/bin/sh

set -e

[ -n "$1" ] && exec "$@"

# Set default variables
LOGGER_URL=${LOGGER_URL:-tcp://localhost:5555}
LOGLEVEL=${LOGLEVEL:-DEBUG}
LOGFILE=${LOGFILE:--}
MASTER_URL=${MASTER_URL:-tcp://localhost:5556}

# Import variables
[ -e /etc/lava-dispatcher/lava-slave ] && . /etc/lava-dispatcher/lava-slave

exec /usr/bin/lava-slave --level "$LOGLEVEL" --log-file "$LOGFILE" --master "$MASTER_URL" --socket-addr $LOGGER_URL $IPV6 $ENCRYPT $MASTER_CERT $SLAVE_CERT $DISPATCHER_HOSTNAME
