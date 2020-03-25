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
apt-get update
apt-get install docker.io docker-compose git
```

??? tip "Old Debian version"
    On old Debian versions, docker should be installed from the official docker repository.
    ```shell
    apt-get install apt-transport-https ca-certificates gnupg2 wget
    wget https://download.docker.com/linux/debian/gpg
    apt-key add gpg
    echo "deb [arch=amd64] https://download.docker.com/linux/debian buster stable" > /etc/apt/sources.list.d/docker.list
    apt-get update
    apt-get install docker-ce
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
    LAVA is only supported on Debian *Buster* and *Bullseye*.

### Dependencies

In order to folow this tutorial, you would have to install some dependencies:

```shell
apt-get install apt-transport-https ca-certificates gnupg2 wget
```

### Repository

Add the lavasoftware debian repository:

```shell
wget https://apt.lavasoftware.org/lavasoftware.key.asc
apt-key add lavasoftware.key.asc
echo "deb https://apt.lavasoftware.org/release buster main" > /etc/apt/sources.list.d/lava.list
```

### Install

Install **postgresql** and **lava** debian packages:

```shell
apt-get update
apt-get install postgresql
pg_ctlcluster 11 main start
apt-get install lava
```

### Starting

You can start the different services:

```shell
service apache2 start
service postgresql start
service lava-server-gunicorn start
service lava-publisher start
service lava-master start
service lava-logs start
service lava-slave start
```

The newly created instance is now available at [localhost].

--8<-- "refs.txt"
