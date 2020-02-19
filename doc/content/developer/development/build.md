# Building LAVA

LAVA can be distributed either as [Debian packages](#debian-packages) or [Docker images](#docker-images).

Both formats can be built locally from sources.

!!! tip "Version"
    The version will be computed based on `git describe`.
    Run `./lava_common/version.py` to print this version.

## Debian packages

Run the GitLab CI script to build the Debian packages:

```shell
.gitlab-ci/build/debian/10.sh
```

The packages will be available under `_build/`.

!!! warning "Uncommited changes"
    The script will refuse to build the packages is you have any uncommitted changes.

## Docker images

Run the GitLab CI script to build either the `lava-dispatcher` or `lava-server` image:

```shell
.gitlab-ci/build/docker.sh dispatcher
.gitlab-ci/build/docker.sh server
```

Images will be tagged with:

```
hub.lavasoftware.org/lava/lava/amd64/lava-dispatcher:<VERSION>
hub.lavasoftware.org/lava/lava/amd64/lava-server:<VERSION>
```

!!! tip "Base images"
    The script will create base images for both `lava-dispatcher` and `lava-server`.
    Bases images will be tagged with
    ```
    hub.lavasoftware.org/lava/lava/amd64/lava-dispatcher-base:<VERSION>
    hub.lavasoftware.org/lava/lava/amd64/lava-server-base:<VERSION>
    ```
