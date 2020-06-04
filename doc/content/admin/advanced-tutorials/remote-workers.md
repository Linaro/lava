# Setting up remote worker

Test execution in LAVA is performed by 'lava-dispatcher'. It can run on the same
physical hardware as 'lava-master' but also can run separately on different
physical host. The latter case is called 'remote worker'. Remote workers can
connect to master on local network or using Internet. Connection is established
usinc ZMQ protocol.

## lava-dispatcher settings

In order to point dispatcher to the correct master, it needs the following
settings:
```
MASTER_URL="tcp://<lava-master-dns>:5556"
LOGGER_URL="tcp://<lava-logger-dns>:5555"
```
Location of the settings depends on the way lava-dispatcher is started. When
using standalone installation either from sources or from debian package,
settings can be found in /etc/lava-dispatcher/lava-slave file. In case
[docker-compose](https://git.lavasoftware.org/lava/pkg/docker-compose) is used
settings should be updated in .env file:
```
DC_LAVA_MASTER_HOSTNAME=<lava-master-dns>
DC_LAVA_LOGS_HOSTNAME=<lava-logger-dns>
```

## connection encryption

It is advised to always encrypt the connection between master and workers. The
following settings are required to make this happen:
```
ENCRYPT="--encrypt"
MASTER_CERT="--master-cert /etc/lava-dispatcher/certificates.d/<master.key>"
SLAVE_CERT="--slave-cert /etc/lava-dispatcher/certificates.d/<slave.key_secret>"
```

In case of running dispatcher using docker-compose, the following settings should
be updated in .env file:
```
DC_LAVA_MASTER_ENCRYPT="--encrypt"
DC_MASTER_CERT="--master-cert /etc/lava-dispatcher/certificates.d/<master.key>"
DC_SLAVES_CERT="--slave-cert /etc/lava-dispatcher/certificates.d/<slave.key_secret>"
```

### certificate exchange

Public worker certificates should be available to the lava-master and lava-logs
processes. They are used to encrypt connection between master or logs and
workers. Also master certificates should be available to the lava-dispatcher
process so proper SSL handshake can be performed. This usually isn't a problem
when LAVA instance (master, logs and workers) is managed by the same
administrator(s). However in case administrators of master and workers are
different they should arrange certificate exchange. Only public certificates
need to be sent. API endpoints that allow automatic certificate exchange exist
in both REST and XMLRPC apis. The XML-RPC methods are ```scheduler.workers.get_certificate```, ```scheduler.workers.set_certificate``` for slave certificates and ```system.get_master_certificate``` for master certificate. The REST API endpoints are ```/api/v0.2/workers/<hostname>/certificate/``` for slave certificates which supports GET and POST requests and ```/api/v0.2/system/certificate/``` for master certificate (this one support only GET requests). The certificates can
also be exchanged manually.


### worker certificate generation

LAVA provides a helper script for generating the certificate. Using the script
depends on the installation model. In case of host installation (from source,
debian) admin should call the following script:
```
/usr/share/lava-dispatcher/create_certificate.py foo_slave_1
```
foo_slave_1 is a name of the certificate files. This can be any string in case
of standalone installation.

In case docker-compose is used to run dispatcher, certificate generation can be
achieved in a following way:
```
docker run -v $PWD:/tmp/certs --rm lavasoftware/lava-dispatcher /usr/share/lava-common/create_certificate.py --directory  /tmp/certs slave
```

The slave.key, slave.key_secret and master.key should be than copied to
dispatcher/certs directory. master.key comes from the lava-master that
lava-dispatcher is connecting to. In the current implementation of [docker-compose](https://git.lavasoftware.org/lava/pkg/docker-compose)
slave.key and master.key certificate names are hardcoded. As mentioned above
it should be obtained via API on the master.

## http_proxy settings

Worker specific http_proxy settings should be defined on the master in
```
/etc/lava-server/dispatcher.d/<name>/env.yaml
```
It can be directly edited on the master host or created/updated using API calls:
 * ```scheduler.workers.set_env``` XML-RPC
 * POST on ```/api/v0.2/workers/``` REST API
 * PUT on ```/api/v0.2/workers/<hostname>/env``` REST API

## local devices connected to remote worker

All device dictionaries are stored on the master node and passed to workers
before starting test jobs. In case both workers and master are administered by
the same admin there should be no issues. However in case remote worker admin is
different than master admin, there needs to be coordination of device
dictionaries. It is advised that device dictionary files are maintained in
version control system. This way bad changes can be reverted quickly and full
instance recovery is possible without major problems.

Current APIs allow to upload device dictionaries directly to the master. These
are ```scheduler.devices.set_dictionary``` XML-RPC method and POST request on
```/api/v0.2/devices/<hostname>/dictionary``` REST API.

Alternatively master admins might decide to use a configuration tool (salt,
ansible, etc.) to copy files from version control to the lava-master host.

### database entries for device types and devices

Although all device specific settings are stored in device dictionary, there is
still a need to create a database entry. This can be done using django admin UI,
XML-RPC API ```scheduler.devices.add``` or issuing POST request on
```/api/v0.2/devices/```.

## local device types (not yet available in LAVA)

Devices on which test jobs are executed should be supported by LAVA. This means
that "device type" should be present in the master node. Device type is used to
render full device dictionary. There may be cases that remote workers include
devices that are not yet supported by LAVA. In such case the following actions
should be performed:
 * new device type should be added to LAVA code base
 * temporarily master node admins might add new device type on their host. This
   operation is depending on how master configuration is maintained. As with
   device dictionaries it is advised to use version control.

## dispatcher version

Currently lava-dispatcher version should be in sync with lava-master version. It
is possible that older lava-dispatcher will work with more recent lava-master.
This is however not officially supported.

### upgrades

Currently LAVA doesn't support any mechanism for remote dispatcher updates. It
is responsibility of admins to perform the updates.

# remote dispatcher - host installation

The instructions assume installation from debian packages but should also be
valid for installation from sources. These steps should result in remote worker
registering with LAVA master.

## install required packages

```
apt-key adv --keyserver keyserver.ubuntu.com --recv-keys A791358F2E49B100
apt-get update
apt-get install lava-dispatcher lava-dispatcher-host
```

### installing from source

lava-dispatcher-host package installs udev rules file. In order to perform this
step when installing from source one needs to run:
```
lava-dispatcher-host install-udev-rules
```

## create slave certificates
```
/usr/share/lava-dispatcher/create_certificate.py slave_name
```

## obtain master certificate

Both XMLRPC and REST APIs provide endpoints to get the master certificate from
the LAVA master exist as described above.
Alternatively one can contact LAVA master admin. It is assumed that the
certificate file name is master.key.

## edit /etc/lava-dispatcher/lava-slave and update settings

```
MASTER_URL="tcp://<lava-master-dns>:5556"
LOGGER_URL="tcp://<lava-master-dns>:5555"
ENCRYPT="--encrypt"
MASTER_CERT="--master-cert /etc/lava-dispatcher/certificates.d/master.key"
SLAVE_CERT="--slave-cert /etc/lava-dispatcher/certificates.d/slave_name.key_secret"
```

## start lava-dispatcher

```
systemctl start lava-slave
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

    apt install docker.io docker-compose

### Installing

You just need to fetch the sources:

    git clone https://git.lavasoftware.org/lava/pkg/docker-compose
    cd docker-compose

### Using it

#### Configuration (simple, for QEMU purposes)

All configuration is stored in `.env` file. Some of the steps are required
whilst others are optional.

* Change DC_LAVA_MASTER_HOSTNAME and DC_LAVA_LOGS_HOSTNAME to <server_name>
  which points to the running LAVA master instance.
* (optional) set DC_LAVA_MASTER_ENCRYPT to `--encrypt` if the master instance
  is using encryption for master-slave communication.
* (optional) [Create certificates](https://validation.linaro.org/static/docs/v2/pipeline-server.html#create-certificates) on the slave.
  `sudo /usr/share/lava-dispatcher/create_certificate.py foo_slave_1`
  This can be done in three ways:
  * by running "docker exec -it docker-compose_lava-dispatcher_1 bash"
  (for this to work you'd need to build and run the containers first - see
  below).
  * by using published container images:
  `docker run -v $PWD:/tmp/certs --rm lavasoftware/lava-dispatcher /usr/share/lava-common/create_certificate.py --directory  /tmp/certs foo_slave_1`
  * alternatively you can create the certificates on system which has LAVA
    packages already installed.
* (optional) Copy public certificate from master and the private slave
  certificate created in previous step to directory `dispatcher/certs/` of this
  project using the APIs described above. Currently the key names should be the
  default ones (master.key and slave.key_secret).
* Execute `make lava-dispatcher`; at this point multiple containers should be
  up and running and the worker should connect to the LAVA server instance of
  your choosing.
* Add a new device and set its' device template (alternatively you can update
  existing device to use this new worker)
  Example QEMU device template:
  ```
  {% extends 'qemu.jinja2' %}
  {% set mac_addr = 'DF:AD:BE:EF:33:02' %}
  {% set memory = 1024 %}
  ```
  You can do this via [XMLRPC](https://validation.linaro.org/api/help/#scheduler.devices.set_dictionary), [lavacli](https://docs.lavasoftware.org/lavacli/) or [REST API](https://staging.validation.linaro.org/api/v0.2/devices/staging-qemu01/dictionary/) (if using version 2020.01 and higher).
* (optional) If the lab where this container runs is behind a proxy or you
  require any specific worker environment settings, you will need to update the
  proxy settings by setting the [worker environment](https://docs.lavasoftware.org/lava/proxy.html#using-the-http-proxy)
  You can do this via this [XMLRPC API call](https://validation.linaro.org/api/help/#scheduler.workers.set_env).
  In case the worker sits behind a proxy, you will also need to set
  `SOCKS_PROXY=--socks-proxy <address>:port` in the `.env` configuration file
  Furthermore, you will need to add a proxy settings to the `.env` file for
  docker resource downloads (http_proxy, ftp_proxy and https_proxy environment
  variable).

`Note: If the master instance is behind a firewall, you will need to create a
port forwarding so that ports 5555 and 5556 are open to the public.`


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

