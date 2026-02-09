# QEMU

LAVA provides three QEMU-based boot methods.

| Boot Method | Media   | Description |
| ----------- | ------- | ----------- |
| `qemu`      | `tmpfs` | Boots downloaded image directly using QEMU |
| `qemu-nfs`  | `nfs`   | Boots kernel with NFS-deployed root filesystem |
| `qemu-iso`  | `img`   | Boots downloaded ISO installer using QEMU |

These methods run the QEMU command line on the worker. Certain elements of the
command line are available for modification using the [job context](#job-context).

The version of QEMU installed on the worker is a choice made by the admin.
Generally, this will be the same as the version of QEMU available from Debian in
the same suite as the rest of the packages installed on the worker.
Information on the available versions of QEMU in Debian is available at
[tracker.debian.org/pkg/qemu](https://tracker.debian.org/pkg/qemu).

## Job context

The `context` section at the top level of the job definition allows
customization of the QEMU command line. The available options depend on the
device type template configuration. For example, many admins restrict the
available memory of each QEMU device, so the `memory` option in the job context
may be ignored.

```yaml
context:
  arch: aarch64
  cpu: cortex-a57
  machine: virt
  memory: 2048
  netdevice: user
  extra_options:
  - -smp
  - 1
  - -global
  - virtio-blk-device.scsi=off
  - -device virtio-scsi-device,id=scsi
  - --append "console=ttyAMA0 root=/dev/vda rw"
```

Common context options:

* `arch` (Required) - Target architecture (e.g., `amd64`, `aarch64`)
* `cpu` - CPU model (e.g., `cortex-a57`)
* `machine` - Machine type (e.g., `virt` for `aarch64`)
* `memory` - Memory allocation in MB
* `netdevice` - Network device type (e.g., `tap`, `user`)
* `extra_options` - List of additional QEMU command line options

!!! note
    The `arch` parameter in the context section is required  for all QEMU boot
    methods. It is used to determine which `qemu-system-<arch>` binary to
    execute.

## qemu

The `qemu` method is used to boot the downloaded images from the `tmpfs`
deployment action using QEMU.

```yaml
- boot:
    method: qemu
    media: tmpfs
    prompts:
    - 'root@debian:'
    auto_login:
      login_prompt: 'login:'
      username: root
```

### media

When booting QEMU image files directly, the `media` needs to be specified as
`tmpfs`.

### docker

QEMU can be run inside a Docker container. This is useful when the required
QEMU version or configuration is not available on the worker.

```yaml
- boot:
    method: qemu
    media: tmpfs
    docker:
      image: qemu-image:latest
      binary: qemu-system-aarch64
    prompts:
    - 'root@debian:'
```

The `docker` option accepts the following parameters:

* `image` (required) - the docker image to use
* `local` (optional) - whether the image is local (`docker pull` is skipped if
  `local: true` and the image exists on the local)
* `binary` (optional) - QEMU binary path inside the container

### Job example

```yaml
--8<-- "jobs/qemu.yaml"
```


## qemu-nfs

The `qemu-nfs` method is used to boot a downloaded `kernel` with a root
filesystem deployed on the worker via NFS.

```yaml
- boot:
    method: qemu-nfs
    auto_login:
      login_prompt: 'login:'
      username: 'root'
    prompts:
      - 'root@jessie:~#'
```

### media

When booting a QEMU image using NFS, the `media` is implicitly `nfs`. The
deploy action should use `to: nfs`.

!!! note
    When using `qemu-nfs`, the hostname element of the prompt may vary
    according to the worker running QEMU. Use a regex pattern like
    `'root@(.*):'` to match the prompt.

### netdevice

This boot method requires access to the NFS service running on the worker to
mount the root filesystem. Therefore, `netdevice` must be set to `tap` in
either the job context or the device dictionary.

If no network bridge configured for the tap interface yet, see
[Configure bridged network](../../../../admin/basic-tutorials/device-setup/qemu.md#configure-bridged-network).

### Job example

```yaml
--8<-- "jobs/qemu-nfs.yaml"
```

## qemu-iso

The `qemu-iso` method is used to boot a downloaded installer from the deployment
action using QEMU. This is typically used for automated OS installations.

```yaml
- boot:
    method: qemu-iso
    media: img
    auto_login:
      login_prompt: 'login:'
      username: root
      password_prompt: 'Password:'
      password: root
    prompts:
    - 'root@debian:'
```

### media

When booting an installer using QEMU, the `media` needs to be specified as
`img`. The deploy action should use `to: iso-installer`.

### netdevice

This boot method requires access to the TFTP service running on the worker for
loading the preseed file and the Internet for OS installation. Therefore,
`netdevice` must be set to `tap` in either the job context or the device
dictionary.

If no network bridge configured for the tap interface yet, see
[Configure bridged network](../../../../admin/basic-tutorials/device-setup/qemu.md#configure-bridged-network).

### Job example

```yaml
--8<-- "jobs/qemu-iso.yaml"
```
