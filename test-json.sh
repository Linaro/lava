#!/bin/sh
# Ugly hack
# Run the test suite twice, once for each JSON backend
JSON_IMPL=json ./test.py || echo "Tests failed for JSON_IMPL=json"
JSON_IMPL=simplejson ./test.py || echo "Tests failed for JSON_IMPL=simplejson"
