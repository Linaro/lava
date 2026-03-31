# Kselftest

The Linux kernel contains a set of "self tests" under the
`tools/testing/selftests/` directory. These are intended to be small tests to
exercise individual code paths in the kernel.

You can use LAVA to deploy a kernel with matching kselftest binaries and run
these tests on both virtual and physical hardware.

This example job runs the `arm64` kselftest on an `ampereone` server. The matching
kselftest binaries are deployed as an overlay into the NFS root filesystem.

```yaml
device_type: ampereone
job_name: arm64-kselftest
visibility: public
priority: 27

timeouts:
  job:
    minutes: 120
  connection:
    minutes: 2
  actions:
    finalize:
      seconds: 60
    power-off:
      seconds: 60

context:
  arch: arm64
  extra_kernel_args: ' rw kvm-arm.mode=nvhe'

actions:
- deploy:
    to: tftp
    kernel:
      url: https://storage.tuxsuite.com/public/ampere/ci/builds/3BgK8l8H3lwyccIe08ogX16JPj2/Image.gz
      compression: gz
      type: image
    nfsrootfs:
      url: https://storage.tuxboot.com/debian/20250722/trixie/arm64/rootfs.tar.xz
      compression: xz
      format: tar
      overlays:
        kselftest:
          url: https://storage.tuxsuite.com/public/ampere/ci/builds/3BgK8l8H3lwyccIe08ogX16JPj2/kselftest.tar.xz
          compression: xz
          format: tar
          path: /opt/kselftests/default-in-kernel/
        modules:
          url: https://storage.tuxsuite.com/public/ampere/ci/builds/3BgK8l8H3lwyccIe08ogX16JPj2/modules.tar.xz
          compression: xz
          format: tar
          path: /usr/
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
    - from: url
      name: kselftest-arm64
      path: automated/linux/kselftest/kselftest.yaml
      repository: https://github.com/Linaro/test-definitions/releases/download/2025.10.01/2025.10.tar.zst
      compression: zstd
      lava-signal: kmsg
      parameters:
        ENVIRONMENT: production
        KSELFTEST_PATH: /opt/kselftests/default-in-kernel
        SHARD_INDEX: 1
        SHARD_NUMBER: 1
        SKIPFILE: skipfile-lkft.yaml
        SKIP_INSTALL: 'true'
        TST_CMDFILES: arm64
    timeout:
      minutes: 60
```

See [kselftest test definition](https://github.com/Linaro/test-definitions/blob/master/automated/linux/kselftest/kselftest.yaml)
for what each test parameter does.
