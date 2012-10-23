#!/bin/sh

PATH=/lava/bin:/sbin:/bin:/usr/sbin:/usr/bin
DAEMON=/lava/bin/lava-test-runner
NAME="lava-test-runner"

case "$1" in
  start)
        echo -n "Starting $NAME: "
        start-stop-daemon -S -b -n $NAME --exec $DAEMON
        echo "done"
        ;;
  stop)
        echo -n "Stopping $NAME: "
        start-stop-daemon -K -n $NAME
        echo "done"
        ;;
  restart)
        $0 stop
        $0 start
        ;;
  *)
        echo "Usage: $NAME { start | stop | restart }" >&2
        exit 1
        ;;
esac

exit 0

