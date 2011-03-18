#!/bin/sh

# Select development database backend (either sqlite or pgsql)
export DEVEL_DB=${DEVEL_DB:-sqlite}

# Use different port for postgresql so that both can co-exist
if [ "$DEVEL_DB" = "pgsql" ]; then
    PORT=8001
else
    PORT=8000
fi
# Setup dashboard URL for lc-tool 
export DASHBOARD_URL=http://localhost:$PORT
# Find root directory
ROOT="$(bzr root)"

# Check if we should really wipe existing data
if [ "x$1" = "x--force" ]; then
    USED_FORCE=yes
fi

if [ "$USED_FORCE" != "yes" ] && [ "$DEVEL_DB" = "sqlite" ] && [ -e $ROOT/dashboard_server/development.db ]; then
    echo "Whoops, you already have a db, please move it aside first"
    echo "You can use --force to *REMOVE* your database automatically"
    exit 1
elif [ "$USED_FORCE" != "yes" ] && [ "$DEVEL_DB" = "pgsql" ]; then
    echo "PostgreSQL support is not so good yet, you have to pass --force"
    echo "to let us know you want to wipe the devel database"
    exit 1
else
    echo "Setting up hacking environment: "
    if [ "$USED_FORCE" = "yes" ]; then
        if [ "$DEVEL_DB" = "sqlite" ]; then
            echo " * removing SQLite development database" 
            rm -f $ROOT/dashboard_server/development.db 
        else
            echo " * removing PostgreSQL development database"
            # Wipe postgres database 'devel' owned by user 'devel' with password 'devel'
            PGPASSWORD=devel dropdb   --username devel --host localhost --no-password devel
            echo " * creating fresh PostgreSQL development database"
            PGPASSWORD=devel createdb --username devel --host localhost --no-password --encoding UTF-8 devel
        fi
        echo " * removing MEDIA files"
        rm -rf dashboard_server/media/$DEVEL_DB/
    fi
    echo " * building cache of static files (as symlinks)"
    $ROOT/dashboard_server/manage.py build_static --link --noinput --verbosity=0
    echo " * creating fresh database"
    $ROOT/dashboard_server/manage.py syncdb --noinput -v0
    for FIXTURE_PATHNAME in $ROOT/dashboard_app/fixtures/hacking_*.json; do
        FIXTURE=$(basename $FIXTURE_PATHNAME .json)
        echo " * importing data: $FIXTURE"
        $ROOT/dashboard_server/manage.py loaddata -v0 $FIXTURE
    done
    echo " * starting development server in the background"
    # Django debug server uses some thread magic to do autoreload. The problem
    # is that it seems to spawn (multiprocessing?) another process that we
    # cannot kill (yay for services on linux). Now that's a cheesy way to kill
    # both reliably (or so it seems, I cannot explain it really). So yes, we
    # spawn an xterm and sleep for a while. Shell engineering...
    xterm -e $ROOT/dashboard_server/manage.py runserver 0.0.0.0:$PORT &
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
    echo
    echo "To get started run:"
    echo "   DEVEL_DB=$DEVEL_DB $ROOT/dashboard_server/manage.py runserver 0.0.0.0:$PORT"
    echo
    echo "Remeber, username: admin"
    echo "         password: admin"
fi

