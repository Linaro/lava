Docker packaging
================

This repository contains docker image definitions that will be used by lava ci
jobs to build the official lava-server and lava-dispatcher images.

The CI job for this repository is responsible for building, testing and
publishing the base Docker images on hub.lavasoftware.org/lava/pkg/lava/
Theses images will be used as base images for buidlding official lava docker images.

The docker images will be available at hub.lavasoftware.org/lava/lava/

The [registry](https://git.lavasoftware.org/lava/lava/container_registry)
list the available images.

You can manually build and test the images, by running `./build.sh`
