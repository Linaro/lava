# iPXE

The `ipxe` boot method is used to boot DUT using iPXE commands.

```yaml
- boot:
    method: ipxe
    commands: nfs
    prompts:
    - 'root@debian:~#'
```

!!! note
    A prior `tftp` deploy action is required.

## commands

See [commands](./common.md#commands).

## use_bootscript

See [use_bootscript](./method-bootloader.md#use_bootscript).

## Sample job

```yaml
device_type: x86

job_name: x86_64 iPXE sample job

timeouts:
  job:
    minutes: 30
  connection:
    minutes: 2

priority: medium
visibility: public

context:
  extra_nfsroot_args: ',vers=3'

actions:
- deploy:
    to: tftp
    kernel:
      url: https://storage.lavacloud.io/health-checks/x86/bzImage.bin
    nfsrootfs:
      url: https://storage.lavacloud.io/health-checks/x86/rootfs.tar.xz
      compression: xz
    timeout:
      minutes: 20

- boot:
    method: ipxe
    commands: nfs
    parameters:
      shutdown-message: "reboot: Restarting system"
    auto_login:
      login_prompt: 'login:'
      username: root
    prompts:
    - 'root@intel-core2-32:'
    timeout:
      minutes: 10

- test:
    definitions:
    - from: git
      repository: https://gitlab.com/lava/functional-tests.git
      path: posix/smoke-tests-basic.yaml
      name: smoke-tests
    timeout:
      minutes: 5
```

--8<-- "refs.txt"
