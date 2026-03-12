# Depthcharge

The `depthcharge` boot method is used to boot a device using
[Depthcharge](https://chromium.googlesource.com/chromiumos/platform/depthcharge/),
the bootloader used by ChromeOS devices. LAVA waits for the Depthcharge command
line interface, and then sends the configured boot commands.

```yaml
- boot:
    method: depthcharge
    commands: nfs
    prompts:
    - 'root@debian:~#'
    timeout:
      minutes: 5
```

See [Depthcharge](../../../configuration/device-dictionary.md#depthcharge) for
supported device configurations.

!!! note
    A prior `tftp` deploy action is required.

## commands

See [commands](./common.md#commands).

The boot method provides the following additional placeholders that can be used
in the boot commands defined in the device type or job definition.

| Placeholder | Description |
| --- | --- |
| `{DEPTHCHARGE_KERNEL}` | TFTP path to the FIT image (if available) or kernel image |
| `{CMDLINE}` | TFTP path to the generated `cmdline` file |
| `{DEPTHCHARGE_RAMDISK}` | TFTP path to the ramdisk (empty when using a FIT image) |

## extra_kernel_args

Extra kernel command line arguments to append to the kernel `cmdline` defined
in the device type.

```yaml
- boot:
    method: depthcharge
    commands: nfs
    extra_kernel_args: "debug loglevel=7"
```

## Example job

```yaml
device_type: acer-cbv514-1h-34uz-brya
job_name: depthcharge NFS boot example

timeouts:
  job:
    minutes: 30
  connection:
    minutes: 2

priority: medium
visibility: public

actions:
- deploy:
    to: tftp
    kernel:
      url: https://example.com/bzImage
    modules:
      url: https://example.com/modules.tar.xz
      compression: xz
    ramdisk:
      url: https://example.com/bullseye-rootfs-amd64-initramfs.gz
      compression: gz
    nfsrootfs:
      url: https://example.com/bullseye-rootfs-amd64.tar.gz
      compression: gz
    timeout:
      minutes: 10

- boot:
    method: depthcharge
    commands: nfs
    auto_login:
        login_prompt: 'login:'
        username: user
        password_prompt: 'Password:'
        password: user
        login_commands:
          - sudo su
    prompts:
      - 'root@health'
      - 'user@health'
    timeout:
      minutes: 5

- test:
    definitions:
    - from: git
      repository: https://gitlab.com/lava/functional-tests.git
      path: posix/smoke-tests-basic.yaml
      name: smoke-tests
    timeout:
      minutes: 5
```
