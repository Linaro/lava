# Install LAVA

Two installation methods are currently supported:

* [docker](#docker)
* [debian](#debian)

We advise to use docker image for a first test of LAVA.

For a production instance, both methods would be suitable.

## Docker

In order to install LAVA using the official docker images, we advise to use the
provided **docker-compose** file.

### Dependencies

Install the dependencies: `docker` and `docker-compose`:

```shell
sudo apt update
sudo apt install docker-compose
```

The ports needed by the lava services must be available on the host. You can
check if they are occupied with the below command. Stop the programs that using
the port if any.

```shell
sudo ss -tulpn | grep -E ':(69|80|111|2049|3079|5500|7101|8001|35543)\s'
```

### Install

1. Get the **docker-compose** files from [gitlab][lava-docker-compose].

    ```shell
    git clone https://gitlab.com/lava/pkg/docker-compose
    cd docker-compose/
    ```

2. Configure the `.env` file to set LAVA admin username and password. You will
need them for using and managing your LAVA instance.

    ```shell
    DC_LAVA_ADMIN_USERNAME=<your_user_name>
    DC_LAVA_ADMIN_PASSWORD=<your_user_password>
    ```

3. Start the services

    ```shell
    docker-compose pull
    docker-compose build
    docker-compose up
    ```

    !!! tip
        If `/dev/kvm` is unavailable on your host, comment out the `- /dev/kvm`
        line in the `docker-compose.yaml`.

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
