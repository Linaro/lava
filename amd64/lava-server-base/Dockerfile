FROM debian:stretch-slim

LABEL maintainer="Rémi Duraffort <remi.duraffort@linaro.org>"

ENV DEBIAN_FRONTEND noninteractive

RUN echo 'deb http://deb.debian.org/debian stretch-backports main' > /etc/apt/sources.list.d/backports.list && \
    mkdir -p /usr/share/man/man1 /usr/share/man/man7 && \
    addgroup --system --gid 200 lavaserver && \
    adduser --system --home /var/lib/lava-server/home/ --uid 200 --gid 200 --shell /bin/sh lavaserver && \
    apt-get update -q && \
    apt-get install --no-install-recommends --yes wget gnupg ca-certificates && \
    wget https://apt.lavasoftware.org/lavasoftware.key.asc && \
    apt-key add lavasoftware.key.asc && \
    rm lavasoftware.key.asc && \
    echo "deb http://apt.lavasoftware.org/daily stretch-backports main" > /etc/apt/sources.list.d/lava-daily.list && \
    apt-get update -q && \
    apt-get install --no-install-recommends --yes adduser apache2 gunicorn3 iproute2 libjs-excanvas libjs-jquery libjs-jquery-flot libjs-jquery-typeahead postgresql postgresql-client postgresql-common python3-setuptools systemd-sysv && \
    apt-get install --no-install-recommends --yes python3-nose python3-voluptuous && \
    apt-get install --no-install-recommends --yes python3-dateutil python3-django python3-django-restricted-resource python3-djangorestframework python3-docutils python3-jinja2 python3-nose python3-psycopg2 python3-simplejson python3-tap python3-tz python3-voluptuous python3-yaml python3-zmq && \
    apt-get install --no-install-recommends --yes -t stretch-backports python3-django-auth-ldap python3-django-tables2 python3-junit.xml python3-requests && \
    apt-get install --no-install-recommends --yes ntp openssh-client && \
    apt-get install --no-install-recommends --yes libjs-sphinxdoc && \
    rm -rf /var/lib/apt/lists/*
