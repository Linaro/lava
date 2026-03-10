# GRUB

The `grub` boot method is used to boot a device using the configured grub boot
commands in device type or job definition.

```yaml
- boot:
    method: grub
    commands: ramdisk
    prompts:
    - 'root@debian:~#'
    timeout:
      minutes: 5
```

## commands

See [commands](./common.md#commands).

## use_bootscript

See [use_bootscript](./method-bootloader.md#use_bootscript).

## reset

Defaults to `true`. When `false`, LAVA will not reset the device at the start
of the boot action.

This can be used when the device has already been booted into the bootloader by
a previous action.

```yaml
- boot:
    method: grub
    commands: ramdisk
    reset: false
```

## boot_finished

A string or list of strings that LAVA will wait for when no `prompts` are set.
This can be used with an OS installer that does not present a login prompt.
After the string is matched the device is powered off.

```yaml
- boot:
    method: grub
    commands: ramdisk
    boot_finished:
    - 'Installation complete'
    - 'reboot: Restarting system'
```

## Example job

```yaml
job_name: 'ampereone grub boot example job'
device_type: ampereone

priority: medium
visibility: public

timeouts:
  actions:
    finalize:
      seconds: 60
    power-off:
      seconds: 60
  connection:
    minutes: 2
  job:
    minutes: 65
  queue:
    hours: 72

context:
  extra_kernel_args: ' rw'

actions:
- deploy:
    to: tftp
    kernel:
      compression: gz
      type: image
      url: https://example.com/Image.gz
    nfsrootfs:
      compression: xz
      format: tar
      overlays:
        modules:
          compression: xz
          format: tar
          path: /usr/
          url: https://example.com/modules.tar.xz
        overlay-00:
          compression: xz
          format: tar
          path: /
          url: https://storage.tuxboot.com/overlays/debian/trixie/arm64/ltp/master/ltp.tar.xz
      url: https://storage.tuxboot.com/debian/20250722/trixie/arm64/rootfs.tar.xz
    os: debian
    timeout:
      minutes: 30

- boot:
    method: grub
    commands: nfs
    auto_login:
      login_prompt: 'login:'
      username: root
    prompts:
    - root@(.*):[/~]#
    - '/ #'
    timeout:
      minutes: 30

- test:
    definitions:
    - from: inline
      name: prep-inline
      path: inline/prep.yaml
      repository:
        metadata:
          description: Device preparation
          format: Lava-Test Test Definition 1.0
          name: prep-tests
        run:
          steps:
          - export STORAGE_DEV=/dev/nvme0n1p2
          - mkfs.ext4 -F "$STORAGE_DEV" || lava-test-raise "mkfs.ext4 $STORAGE_DEV
            failed; job exit"
          - mkdir -p /scratch && mount "$STORAGE_DEV" /scratch || lava-test-raise
            "mount $STORAGE_DEV failed; job exit"
          - df -h
          - mount
    timeout:
      minutes: 5

- test:
    definitions:
    - compression: zstd
      from: url
      lava-signal: kmsg
      name: ltp-smoke
      parameters:
        ENVIRONMENT: production
        KIRK_WORKERS: 1
        LTP_INSTALL_PATH: /opt/ltp/
        LTP_TMPDIR: /scratch
        RUNNER: kirk
        SHARD_INDEX: 1
        SHARD_NUMBER: 1
        SKIPFILE: skipfile-lkft.yaml
        SKIP_INSTALL: 'true'
        TIMEOUT_MULTIPLIER: 5
        TST_CMDFILES: smoketest
      path: automated/linux/ltp/ltp.yaml
      repository: https://github.com/Linaro/test-definitions/releases/download/2025.10.01/2025.10.tar.zst
    timeout:
      minutes: 5
```

--8<-- "refs.txt"
