# Running the LAVA dispatcher in a Docker container

Running a LAVA dispatcher in a Docker container requires quite a few special
options, to ensure that the dispatcher has access to system resources that
are, in most Docker use cases, invisible to containers. This is automated by
the `lava-docker-worker` program, provided by the `lava-dispatcher-host`
package.

`lava-docker-worker` should support all use cases that the regular LAVA worker
supports In particular, `lava-docker-work` **does support** running other
docker containers, QEMU/KVM, and other regular device types, as long as the
required user space tools are included in the LAVA worker docker image.

## 1: install and configure lava-dispatcher-host

**lava-dispatcher-host needs to be installed in the host machine** (bare metal)
for the LAVA dispatcher to work inside a container, as well as Docker itself.

### Debian package

If you are using the Debian package, just installing it will do all necessary
setup.

### Other means

If you are installing lava-dispatcher-host in some other way, you need to run
the following command, as root:

```
# lava-dispatcher-host rules install
```

This step needs to be repeated when lava-dispatcher-host is upgraded, to make
sure you have the most up to date udev rules file for it.

## 2: start lava-docker-worker

### Debian package

To run the Docker Dispatcher, first edit
`/etc/lava-dispatcher-host/lava-docker-worker` and set the connection
parameters. At least URL and TOKEN are probably needed:

```
WORKER_NAME="--name myworker"

# ...

# Server connection
URL="https://my.lava.server/"
TOKEN="--token 0123456789012345678901234567890123456789"
```

Make sure Docker get installed from Docker's official repo. At the time of
writing this doc, Docker version `18.09.1` installed from Debian's official
repo doesn't work with `lava-docker-worker`.

```
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
```

??? tip "Debian Testing/Sid User"
    Install `docker.io` instead if the above docker CE installation script
    doesn't support your distribution.

    ```shell
    apt-get install docker.io
    ```

Then enable and start the `lava-docker-worker` service:

```
sudo systemctl enable lava-docker-worker.service
sudo systemctl start lava-docker-worker.service
```

### Other means

If you installed LAVA in a way that doesn't provide a lava-docker-worker
systemd service, you can just run `lava-docker-worker` as any user that can run
docker. You need to pass the relevant arguments to have it connect to your LAVA
server:

```
$ lava-docker-worker --url https://my.lavaserver.com/ --token 0123456789012345678901234567890123456789
```

## 3: build customized image

To build customized image for additional packages you might require, first edit
`/etc/lava-dispatcher-host/lava-docker-worker` and set the BUILD_DIR parameter
to a directory with a Dockerfile inside.

```
# Docker build directory
# Should be set to a directory with a Dockerfile inside.
BUILD_DIR="/etc/lava-dispatcher-host/build"
```

Then restart the `lava-docker-worker` service.

```
sudo systemctl restart lava-docker-worker.service
```

!!! note "Base image"

    A new `Dockerfile.lava` will be generated with the base image that matches
    your LAVA server version for building your customized image. All the `FROM`
    commands defined in your `Dockerfile` will be ignored.

## 4: provide custom tools in the container

If either of `/usr/share/lava-docker-worker` or
`/usr/local/share/lava-docker-worker` exists, they are bind monted into the
container by default, and if there is a `bin` subdirectory in any of then, that
gets added to the default $PATH.

Additionally, you can mount other host directories inside the container by
using the --mount option.  Edit `/etc/lava-dispatcher-host/lava-docker-worker`
and set the MOUNTS option:

```
MOUNTS="--mount /path/to/tools/bin:/usr/local/bin"
```

## 5: verifying device sharing

On cgroups v2 hosts, LAVA shares devices with job containers through a BPF
program compiled on the host. Kernel or systemd changes (for example
`ProtectKernelModules=true`) can silently break it. To verify that the host
can compile the BPF device filter and share a device with a
container, run:

```
sudo lava-dispatcher-host check
```

The check:

* rejects cgroups v1 hosts: only cgroups v2 is supported;
* verifies that `docker`, `bpftool` and the bcc python bindings are installed;
* verifies that kernel headers are reachable (the `kheaders` kernel module
  or installed kernel headers) and that the BPF device filter compiles;
* pulls a small image (`debian:trixie-slim` by default, override with
  `--image`), starts a throwaway container named
  `lava-dispatcher-host-check-<pid>`, attaches the device filter to it, and
  with a temporary loop device shows that the container cannot access the
  device until it is added to the filter.

Use `--device /dev/ttyUSB0` to test with a real device instead of a loop
device. The check removes the container and the loop device afterwards, even
when it fails.

Exit code 0 means device sharing works. Any failure prints the reason and
exits with 1. Run the check after installing or upgrading
`lava-dispatcher-host` on cgroups v2 hosts.
