#!/bin/sh
ROOT="$(bzr root)"
export DASHBOARD_URL=http://localhost:8000

if [ "x$1" = "x--force" ]; then
    shift
    rm -f $ROOT/dashboard_server/database.db 
fi

if [ -e $ROOT/dashboard_server/database.db ]; then
    echo "Whoops, you already have a db, please move it aside first"
    echo "You can use --force to *REMOVE* your database automatically"
    exit 1
else
    echo "Setting up hacking environment: "
    echo " * creating fresh database"
    $ROOT/dashboard_server/manage.py syncdb --noinput -v0
    for FIXTURE_PATHNAME in $ROOT/dashboard_app/fixtures/hacking_*.json; do
        FIXTURE=$(basename $FIXTURE_PATHNAME .json)
        echo " * importing data: $FIXTURE"
        $ROOT/dashboard_server/manage.py loaddata -v0 $FIXTURE
    done
    echo " * starting development server in the background"
    # Django debug server uses some thread magic to do autoreload the problem
    # is that it seems to spawn (multiprocessing?) another process that we
    # cannot kill (yay for services on linux). Now that's a cheesy way to kill
    # both reliably (or so it seems, I cannot explain it really). So yes, we
    # spawn an xterm and sleep for a while. Shell engineering...
    xterm -e $ROOT/dashboard_server/manage.py runserver &
    SERVER_PID=$!
    echo " * waiting for server to start up"
    sleep 5
    for BUNDLE_PATHNAME in $ROOT/example_bundles/*.json; do
        BUNDLE=$(basename $BUNDLE_PATHNAME .json)
        echo " * importing bundle: $BUNDLE"
        lc-tool put $BUNDLE_PATHNAME >/dev/null
    done
    for BUNDLE_PATHNAME in $ROOT/example_bundles/templates/*.json; do
        BUNDLE=$(basename $BUNDLE_PATHNAME .json)
        echo " * importing bundle template: $BUNDLE"
        for i in $(seq 1 20); do
            sed "$BUNDLE_PATHNAME" -e "s!@TEMPLATE@!$(printf %04d $i)!g" > "$i-$BUNDLE"
            lc-tool put "$i-$BUNDLE" >/dev/null
            rm -f "$i-$BUNDLE"
        done
    done
    echo " * shutting down development server"
    kill -TERM $SERVER_PID
    echo "All done!"
    echo "Remeber, username: admin"
    echo "         password: admin"
fi

