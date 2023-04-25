# Install LAVA

Two installation methods are currently supported:

* [docker](#docker)
* [debian](#debian)

We advice to use docker image for a first test of LAVA.

For a production instance, both methods would be suitable.

## Docker

In order to install LAVA using the official docker images, we advice to use the
provided **docker-compose** file.

### Dependencies

Install the dependencies: `docker` and `docker-compose`:

```shell
apt update
apt install docker-compose
```

### Install

Get the **docker-compose** files from [gitlab][lava-docker-compose] and use it.

```shell
git clone https://git.lavasoftware.org/lava/pkg/docker-compose
cd docker-compose/
docker-compose pull
docker-compose up
```

The newly created instance is now available at [localhost].

## Debian

In order to install LAVA using the Debian packages, we advice to use the
repositories that we manage to get the latest version.

!!! note "Supported Debian versions"
    LAVA is only supported on Debian *Bullseye* and *Bookworm*.

### Dependencies

In order to follow this tutorial, you would have to install some dependencies:

```shell
apt install ca-certificates gnupg2 wget
```

### Repository

Add the lavasoftware debian repository:

=== "Bullseye"
    ```shell
    wget https://apt.lavasoftware.org/lavasoftware.key.asc
    apt-key add lavasoftware.key.asc
    echo "deb https://apt.lavasoftware.org/release bullseye main" > /etc/apt/sources.list.d/lava.list
    echo "deb http://deb.debian.org/debian bullseye-backports main" > /etc/apt/sources.list.d/backports.list
    ```

=== "Bookworm"
    ```shell
    wget https://apt.lavasoftware.org/lavasoftware.key.asc
    apt-key add lavasoftware.key.asc
    echo "deb https://apt.lavasoftware.org/release bookworm main" > /etc/apt/sources.list.d/lava.list
    ```

### Install

Install **postgresql** and **lava** debian packages:

=== "Bullseye"
    ```shell
    apt update
    apt install postgresql
    pg_ctlcluster 13 main start
    apt install lava-server
    apt install -t bullseye-backports lava-dispatcher
    ```

=== "Bookworm"
    ```shell
    apt update
    apt install postgresql
    pg_ctlcluster 15 main start
    apt install lava-server lava-dispatcher
    ```

### Starting

Enable default LAVA server Apache configuration:

```shell
a2dissite 000-default
a2enmod proxy
a2enmod proxy_http
a2ensite lava-server.conf
systemctl restart apache2
```

You can start the different services:

```shell
systemctl start apache2
systemctl start postgresql
systemctl start lava-server-gunicorn
systemctl start lava-publisher
systemctl start lava-scheduler
systemctl start lava-worker
```

The newly created instance is now available at [localhost].

--8<-- "refs.txt"
