Docker packaging
================

This repository contains docker image definitions that will be used by lava ci
jobs to build the official lava-server and lava-dispatcher images.

The CI job for this repository is responsible for building, testing and
publishing the base Docker images on hub.lavasoftware.org/lava/pkg/lava/
These images will be used as base images for building official lava docker images.

The docker images will be available at hub.lavasoftware.org/lava/lava/

The [registry](https://git.lavasoftware.org/lava/lava/container_registry)
list the available images.

You can manually build and test the images, by running `./build.sh` which will
detect which architecture to build using `uname -m`.

In GitLab, base images are built and published for aarch64 and amd64
architectures.
