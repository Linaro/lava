#!/bin/sh
set -e
virtualenv --no-site-packages --clear /tmp/foo
. /tmp/foo/bin/activate
# 3rd party dependencies
pip install simplejson django python-openid django-openid-auth django-pagination docutils
# For launch-control itself
pip install versiontools
pip install linaro-json
pip install linaro-dashboard-bundle
# For testing
pip install django-testscenarios
# Client side tools
pip install launch-control-tool
