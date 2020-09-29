# Setting up remote worker

Test execution in LAVA is performed by 'lava-worker'. It can run on the same
physical hardware as 'lava-server' but also can run separately on different
physical host. The latter case is called 'remote worker'. Remote workers can
connect to server on local network or using Internet. Connection is established
over http/https protocol.

## lava-dispatcher settings

In order to point lava-worker to the correct server, it needs the following
settings:
```shell
URL="http://<lava-server-dns>/"
```

Location of the settings depends on the way lava-dispatcher is started.

When using standalone installation either from sources or from debian package,
settings can be found in `/etc/lava-dispatcher/lava-worker` file. In case
[docker-compose](https://git.lavasoftware.org/lava/pkg/docker-compose) is used
settings should be updated in .env file:

```shell
DC_LAVA_SERVER_HOSTNAME="<lava-server-dns>"
```

## connection encryption

It is advised to always encrypt the connection between server and workers. We
advice to use https instead of http for worker connection.

## http_proxy settings

Worker specific http_proxy settings should be defined on the server in
```shell
/etc/lava-server/dispatcher.d/<name>/env.yaml
```
It can be directly edited on the server host or created/updated using API calls:
 * ```scheduler.workers.set_env``` XML-RPC
 * POST on ```/api/v0.2/workers/``` REST API
 * PUT on ```/api/v0.2/workers/<hostname>/env``` REST API

## local devices connected to remote worker

All device dictionaries are stored on the server node and passed to workers
before starting test jobs. In case both workers and server are administered by
the same admin there should be no issues.

However in case remote worker admin is different than server admin, there needs
to be coordination of device dictionaries. It is advised that device dictionary
files are maintained in version control system. This way bad changes can be
reverted quickly and full instance recovery is possible without major problems.

Current APIs allow to upload device dictionaries directly to the server. These
are ```scheduler.devices.set_dictionary``` XML-RPC method and POST request on
```/api/v0.2/devices/<hostname>/dictionary``` REST API.

Alternatively server admins might decide to use a configuration tool (salt,
ansible, etc.) to copy files from version control to the lava-server host.

### database entries for device types and devices

Although all device specific settings are stored in device dictionary, there is
still a need to create a database entry. This can be done using django admin UI,
XML-RPC API ```scheduler.devices.add``` or issuing POST request on
```/api/v0.2/devices/```.

## local device types (not yet available in LAVA)

Devices on which test jobs are executed should be supported by LAVA. This means
that "device type" should be present in the server node. Device type is used to
render full device dictionary. There may be cases that remote workers include
devices that are not yet supported by LAVA. In such case the following actions
should be performed:

 * new device type should be added to LAVA code base
 * temporarily server node admins might add new device type on their host. This
   operation is depending on how server configuration is maintained. As with
   device dictionaries it is advised to use version control.

## dispatcher version

Currently lava-dispatcher version should be in sync with lava-server version.
In case of version mismatch, lava-worker connection will be rejected by
lava-server.

### upgrades

Currently LAVA doesn't support any mechanism for remote dispatcher updates. It
is responsibility of admins to perform the updates.

# remote dispatcher - host installation

The instructions assume installation from debian packages but should also be
valid for installation from sources. These steps should result in remote worker
registering with LAVA server.

## install required packages

```shell
apt-key adv --keyserver keyserver.ubuntu.com --recv-keys A791358F2E49B100
apt-get update
apt-get install lava-dispatcher lava-dispatcher-host
```

### installing from source

lava-dispatcher-host package installs udev rules file. In order to perform this
step when installing from source one needs to run:
```shell
lava-dispatcher-host rules install
```

## edit /etc/lava-dispatcher/lava-worker and update settings

```shell
URL="http://<lava-server-dns>/"
```

## start lava-dispatcher

```shell
systemctl start lava-worker
```

# remote dispatcher - docker installation

docker-compose file to setup an instance **lava-dispatcher** from scratch. In this
setup, every service will be running in a separate container.

## Usage

###  Requirements

In order to use this docker-compose file, you need:

* docker.io
* docker-compose

You can install the dependencies using:

```shell
apt install docker.io docker-compose
```

### Installing

You just need to fetch the sources:

```shell
git clone https://git.lavasoftware.org/lava/pkg/docker-compose
cd docker-compose
```

### Using it

#### Configuration (simple, for QEMU purposes)

All configuration is stored in `.env` file. Some of the steps are required
whilst others are optional.

* Change DC_LAVA_SERVER_HOSTNAME to <server_name>
  which points to the running LAVA server instance.
* Execute `make lava-dispatcher`; at this point multiple containers should be
  up and running and the worker should connect to the LAVA server instance of
  your choosing.
* Add a new device and set its' device template (alternatively you can update
  existing device to use this new worker)
  Example QEMU device template:
  ```jinja
  {% extends 'qemu.jinja2' %}
  {% set mac_addr = 'DF:AD:BE:EF:33:02' %}
  {% set memory = 1024 %}
  ```
  You can do this via [XMLRPC](https://validation.linaro.org/api/help/#scheduler.devices.set_dictionary), [lavacli](https://docs.lavasoftware.org/lavacli/) or [REST API](https://staging.validation.linaro.org/api/v0.2/devices/staging-qemu01/dictionary/) (if using version 2020.01 and higher).
* (optional) If the lab where this container runs is behind a proxy or you
  require any specific worker environment settings, you will need to update the
  proxy settings by setting the [worker environment](https://docs.lavasoftware.org/lava/proxy.html#using-the-http-proxy)
  You can do this via this [XMLRPC API call](https://validation.linaro.org/api/help/#scheduler.workers.set_env).

!!! note "Firewall"

    If the server instance is behind a firewall, you will need to create a
    port forwarding so that ports 80 and maybe 443 are open to the public.


#### Configuration (advanced, for physical DUT purposes)

If you're setting up a standalone dispatcher container, make sure you go
through the above configuration first, it is mandatory for this step.
In order to run test jobs on physical devices we will need a couple of
additional setup steps:

* PDU control:
  * The dispatcher docker container will already download pdu scripts from
    [lava-lab repo](https://git.linaro.org/lava/lava-lab.git/) which you can use
    in device configuration but if you use custom PDU scripts you need to
    provide them and copy them into `dispatcher/power-control` directory; they
    will be copied into `/root/power-control` path in the container.
  * If you need SSH keys for PDU control, copy the private key to the
    `dispatcher/ssh` directory and the public key on to the PDU
  * SSH config - if there's a need for a specific SSH configuration (like
    tunnel passthrough, proxy, strict host checking, kexalgorithm etc), create
    the config file with relevant settings and copy it into `dispatcher/ssh`
    dir; it will be copied to `/root/.ssh` directory on the dispatcher
    container.
* ser2net config - update `ser2net/ser2net.config` with the corresponding
  serial port and device settings
* Update/add [device dictionary](https://docs.lavasoftware.org/lava/glossary.html#term-device-dictionary) with power commands and connection command
* Add dispatcher_ip setting to the [dispatcher configuration](https://validation.linaro.org/api/help/#scheduler.workers.set_config). Alternatively you can use
[REST API](https://lava_server/api/v0.2/workers/docker_dispatcher_hostname/config/) if you are using version 2020.01 or higher:
  * `dispatcher_ip: <docker host ip address>`
* Disable/stop rpcbind service on host machine if it's running - docker service
  nfs will need port 111 available on the host.


### Running

In order to start the containers, run:

    docker-compose build lava-dispatcher
    docker-compose up lava-dispatcher

or, alternatively:

    make lava-dispatcher

