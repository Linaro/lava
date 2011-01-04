#!/bin/sh

virtualenv --no-site-packages --clear /tmp/foo
. /tmp/foo/bin/activate
pip install simplejson && \
pip install launch-control-tool && \
pip install launch-control && \
pip install django-testscenarios && \
echo "All packages installed okay"
