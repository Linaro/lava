# Running the LAVA dispatcher in a Docker container

Running a LAVA dispatcher in a Docker container requires quite a few special
options, to ensure that the dispatcher has access to system resources that
are, in most Docker use cases, invisible to containers. This is automated by
the `lava-docker-worker` program, provided by the `lava-dispatcher-host`
package.

## 1: install and configure lava-dispatcher-host

**lava-dispatcher-host needs to be installed in the host machine** (bare metal)
for the LAVA dispatcher to work inside a container.

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

To run the Docker Dispatcher, just run `lava-docker-worker` as any user that
can run docker. You need to pass the relevant arguments to have it connect to
your LAVA server:

```
$ lava-docker-worker --url https://my.lavaserver.com/
```
