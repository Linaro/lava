FROM debian:stretch-backports

LABEL maintainer="Rémi Duraffort <remi.duraffort@linaro.org>"

ENV DEBIAN_FRONTEND noninteractive

RUN apt-get update -q

RUN apt-get install --no-install-recommends --yes adduser apache2 gunicorn3 iproute2 libjs-excanvas libjs-jquery libjs-jquery-cookie libjs-jquery-flot libjs-jquery-typeahead libjs-jquery-ui libjs-jquery-watermark postgresql postgresql-client postgresql-common python3-setuptools systemd-sysv
RUN apt-get install --no-install-recommends --yes python3-dateutil python3-django python3-django-restricted-resource python3-djangorestframework python3-docutils python3-jinja2 python3-junit.xml python3-nose python3-psycopg2 python3-simplejson python3-tap python3-tz python3-voluptuous python3-yaml python3-zmq
RUN apt-get install --no-install-recommends --yes -t stretch-backports python3-django-auth-ldap python3-django-tables2 python3-requests
RUN apt-get install --no-install-recommends --yes ntp openssh-client
RUN apt-get install --no-install-recommends --yes libjs-sphinxdoc
