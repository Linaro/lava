#!/bin/sh

echo "Testing script for Launch Control"
export DEVEL_DB
for DEVEL_DB in sqlite pgsql; do
    echo " * removing old uploaded content"
    rm -rf dashboard_server/media/$DEVEL_DB
    echo " * running tests for $DEVEL_DB"
    ./dashboard_server/manage.py test -v0 --failfast
    echo " * listing leftover attachments and bundles "
    find dashboard_server/media/$DEVEL_DB/bundles
    find dashboard_server/media/$DEVEL_DB/attachments
done
