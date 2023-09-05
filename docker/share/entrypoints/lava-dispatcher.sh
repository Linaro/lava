#!/bin/sh

set -e

[ -n "$1" ] && exec "$@"

# Set default variables
URL=${URL:-http://localhost/}
LOGLEVEL=${LOGLEVEL:-DEBUG}
LOGFILE=${LOGFILE:--}

# Add lava-docker-worker directories to PATH
for d in "/usr/share/lava-docker-worker" "/usr/local/share/lava-docker-worker"; do
    if [ -d "${d}/bin" ]; then
        export PATH="${d}/bin:${PATH}"
    fi
done

# Import variables
[ -e /etc/lava-dispatcher/lava-worker ] && . /etc/lava-dispatcher/lava-worker

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

exec /usr/bin/lava-worker --level "$LOGLEVEL" --log-file "$LOGFILE" --url "$URL" $TOKEN $WORKER_NAME $WS_URL $HTTP_TIMEOUT $JOB_LOG_INTERVAL
