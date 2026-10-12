# Docker

The `docker` boot method starts a container from the image deployed by a
[docker deploy action](../deploy/to-docker.md). The container is started on the
LAVA worker and removed at the end of the job.

```yaml
- boot:
    method: docker
    command: bash
    prompts:
    - 'root@lava:'
    timeout:
      minutes: 2
```

The container hostname is always `lava`, so the prompt is usually `root@lava:`.

## command

Required. The command to run when starting the container, usually a shell like
`bash` or `sh`.

## prompts

The list of prompts to wait for after starting the container. Required when the
boot action is followed by a test action. See [prompts](common.md#prompts).

## downloads-namespace

The files downloaded by a [downloads deploy action](../deploy/to-downloads.md)
are made available in the container under `/lava-downloads`.

By default, LAVA uses the files downloaded in the namespace of the boot action.
Use `downloads-namespace` to use the files from another namespace:

```yaml
- deploy:
    namespace: build
    to: downloads
    images:
      kernel:
        url: https://example.com/Image
- deploy:
    namespace: container
    to: docker
    image: debian:trixie
- boot:
    namespace: container
    method: docker
    command: bash
    downloads-namespace: build
    prompts:
    - 'root@lava:'
```

## Device configuration

The following variables can be set in the
[device dictionary](../../../configuration/device-dictionary.md) to change how
the container is started:

| Variable | Default | `docker run` option |
| -------- | ------- | ------------------- |
| `docker_remote` | `''` | `--host` |
| `docker_cpus` | `0.0` (no limit) | `--cpus` |
| `docker_memory` | `0` (no limit) | `--memory` |
| `docker_privileged` | `False` | `--privileged` |
| `docker_capabilities` | `[]` | `--cap-add` for each item |
| `docker_devices` | `[]` | `--device` for each item |
| `docker_networks` | `[]` | `--network` for each item |
| `docker_volumes` | `[]` | `--volume` for each item |
| `docker_extra_arguments` | `[]` | each item is added as is |

```jinja
{% extends 'docker.jinja2' %}
{% set docker_cpus = 2 %}
{% set docker_memory = '4g' %}
{% set docker_volumes = ['/srv/data:/data:ro'] %}
```

When `docker_remote` is set, the container is started on the remote docker
daemon and the LAVA overlay is mounted using NFS from the LAVA worker.

See also [docker device setup](../../../../admin/basic-tutorials/device-setup/docker.md).
