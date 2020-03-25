# Developer setup

In this document, we assume that you are developing on a Debian system. We also
assume that the version is Buster (or any more recent versions).

??? note "Other distributions"
    Even if we assume the use of Debian, you can also use any non-Debian
    distributions. Just adapt the steps above to match your distribution.

We currently recommend two methods for developing LAVA.

* [from the Debian packages](#from-debian-packages)
* [from sources](#from-sources)

Both methods are currently used by LAVA core developers. Choosing one or the other is a matter of taste.

## From Debian packages

Install the Debian packages:

```shell
apt-get install git postgresql
apt-get install lava-coordinator lava-dispatcher lava-server
```

Fetch the sources somewhere in your home directory.

```shell
cd ~/
git clone https://git.lavasoftware.org/lava/lava
cd ~/lava/
```

Remove the lava binaries and packages from the system directories:

```shell
# python libraries
rm -rf /usr/lib/python3/dist-packages/lava/
rm -rf /usr/lib/python3/dist-packages/lava_common/
rm -rf /usr/lib/python3/dist-packages/lava_dispatcher/
rm -rf /usr/lib/python3/dist-packages/lava_dispatcher_host/
rm -rf /usr/lib/python3/dist-packages/lava_rest_app/
rm -rf /usr/lib/python3/dist-packages/lava_results_app/
rm -rf /usr/lib/python3/dist-packages/lava_scheduler_app/
rm -rf /usr/lib/python3/dist-packages/lava_server/
rm -rf /usr/lib/python3/dist-packages/linaro_django_xmlrpc/

# binaries
rm -f /usr/bin/lava-coordinator
rm -f /usr/bin/lava-dispatcher-host
rm -f /usr/bin/lava-run
rm -f /usr/bin/lava-server
rm -f /usr/bin/lava-slave
```

Add symbolic links to your local clone:

```shell
# python libraries
cd /usr/lib/python3/dist-packages/
ln -s ~/lava/lava/ .
ln -s ~/lava/lava_common/ .
ln -s ~/lava/lava_dispatcher/ .
ln -s ~/lava/lava_dispatcher_host/ .
ln -s ~/lava/lava_rest_app/ .
ln -s ~/lava/lava_results_app/ .
ln -s ~/lava/lava_scheduler_app/ .
ln -s ~/lava/lava_server/ .
ln -s ~/lava/linaro_django_xmlrpc/ .

# binaries
cd /usr/bin/
ln -s ~/lava/lava/coordinator/lava-coordinator .
ln -s ~/lava/lava/dispatcher/lava-run .
ln -s ~/lava/lava/dispatcher/lava-slave .
ln -s ~/lava/lava_dispatcher_host/lava-dispatcher-host .
ln -s ~/lava/manage.py lava-server
```

Restart the services:

```shell
service lava-coordinator restart
service lava-logs restart
service lava-master restart
service lava-publisher restart
service lava-server-gunicorn restart
service lava-slave restart
```

LAVA is now accessible at [http://localhost/](http://localhost/)

## From sources

Install basic tools:

```shell
apt-get install black git nfs-kernel-server \
    postgresql postgresql-client \
    python3 python3-yaml python3-django-extensions python3-werkzeug \
    ruby-foreman
```

Fetch the sources somewhere in your home directory.

```shell
cd ~/
git clone https://git.lavasoftware.org/lava/lava
cd ~/lava/
```

Install `lava-dispatcher` and  `lava-server` dependencies:

```shell
apt-get install \
    $(python3 share/requires.py  -p lava-dispatcher -d debian -s buster -n) \
    $(python3 share/requires.py  -p lava-dispatcher -d debian -s buster -n -u) \
    $(python3 share/requires.py  -p lava-server -d debian -s buster -n) \
    $(python3 share/requires.py  -p lava-server -d debian -s buster -n -u)
```

Create the test database:

```shell
sudo -u postgres psql -c "CREATE ROLE devel NOSUPERUSER CREATEDB NOCREATEROLE INHERIT LOGIN ENCRYPTED PASSWORD 'devel'"
sudo -u postgres psql -c "CREATE DATABASE devel OWNER devel"
```

Apply the django migrations

```shell
python3 lava_server/manage.py migrate
```

Start the services

```shell
foreman start
```

LAVA is now accessible at [http://localhost:8000/](http://localhost:8000/)
