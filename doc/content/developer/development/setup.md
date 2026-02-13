# Developer setup

In this document, we assume that you are developing on a Debian system. We also
assume that the version is Bullseye (or any more recent versions).

??? note "Other distributions"
    Even if we assume the use of Debian, you can also use any non-Debian
    distributions. Just adapt the steps above to match your distribution.

We currently recommend three methods for developing LAVA.

* [using uv and pyproject.toml](#using-uv) (recommended)
* [from the Debian packages](#from-debian-packages)
* [from sources](#from-sources)

## Using uv

[uv](https://docs.astral.sh/uv/) is the recommended way to set up a
development environment. LAVA provides a `pyproject.toml` with optional
dependency groups for each component.

Available dependency groups:

* `dispatcher` -- dependencies for `lava-dispatcher`
* `server` -- dependencies for `lava-server`
* `dispatcher-host` -- dependencies for `lava-dispatcher-host`
* `coordinator` -- dependencies for `lava-coordinator`
* `full` -- all of the above
* `test` -- test dependencies (pytest, coverage, etc.)
* `dev` -- development tools (black, isort, pylint, mypy, etc.)
* `docs` -- documentation build dependencies (sphinx)

Fetch the sources and install dependencies:

```shell
git clone https://gitlab.com/lava/lava
cd lava/
uv sync --extra dev
```

### Running the development server

LAVA uses PostgreSQL in production, but for local development you can
use SQLite:

```shell
export DATABASE_URL="sqlite:////tmp/lava.sqlite3"
uv run --extra server manage.py migrate
uv run --extra server manage.py collectstatic --noinput
uv run --extra server manage.py createsuperuser
uv run --extra server manage.py runserver
```

LAVA is now accessible at [http://localhost:8000/](http://localhost:8000/)

### Running tests and linters

```shell
uv run python -m pytest tests/
uv run black --check .
uv run isort --check .
```

!!! note
    Production deployments use Debian packages, not pip or uv. The
    `pyproject.toml` dependency groups are provided for development
    convenience only. System-level files (systemd units, configuration
    in `/etc`, etc.) are handled by the Debian packaging and `setup.py`,
    not by `pyproject.toml`.

### Using pip

Alternatively, you can use pip in a virtual environment:

```shell
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## From Debian packages

Install the Debian packages:

```shell
apt-get install git postgresql
apt-get install lava-coordinator lava-dispatcher lava-server
```

Fetch the sources somewhere in your home directory.

```shell
cd ~/
git clone https://gitlab.com/lava/lava
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
rm -f /usr/bin/lava-worker
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
ln -s ~/lava/lava/dispatcher/lava-worker .
ln -s ~/lava/lava_dispatcher_host/lava-dispatcher-host .
ln -s ~/lava/manage.py lava-server
```

Install the lava-dispatcher-host udev rules:

```shell
lava-dispatcher-host rules install
```

Restart the services:

```shell
systemctl restart lava-coordinator
systemctl restart lava-publisher
systemctl restart lava-scheduler
systemctl restart lava-server-gunicorn
systemctl restart lava-worker
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
git clone https://gitlab.com/lava/lava
cd ~/lava/
```

Install `lava-dispatcher` and  `lava-server` dependencies:

```shell
apt-get install \
    $(python3 share/requires.py  -p lava-common -d debian -s bullseye -n) \
    $(python3 share/requires.py  -p lava-dispatcher -d debian -s bullseye -n) \
    $(python3 share/requires.py  -p lava-dispatcher -d debian -s bullseye -n -u) \
    $(python3 share/requires.py  -p lava-dispatcher-host -d debian -s bullseye -n) \
    $(python3 share/requires.py  -p lava-server -d debian -s bullseye -n) \
    $(python3 share/requires.py  -p lava-server -d debian -s bullseye -n -u)
```

Create the test database:

```shell
sudo -u postgres psql -c "CREATE ROLE devel NOSUPERUSER CREATEDB NOCREATEROLE INHERIT LOGIN ENCRYPTED PASSWORD 'devel'"
sudo -u postgres psql -c "CREATE DATABASE devel OWNER devel"
```

Apply the django migrations

```shell
python3 manage.py migrate
```

Install the lava-dispatcher-host udev rules

```shell
$(pwd)/lava_dispatcher_host/lava-dispatcher-host rules install
```

The above will make the installed udev rules call the lava-dispatcher-host
program inside your source directory. If you move your source directory to a
different location, you will have to install the rules again.

Start the services

```shell
foreman start
```

LAVA is now accessible at [http://localhost:8000/](http://localhost:8000/)
