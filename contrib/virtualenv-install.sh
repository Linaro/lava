#!/bin/sh

virtualenv --no-site-packages --clear /tmp/foo
. /tmp/foo/bin/activate
pip install launch-control
pip install launch-control-tool

