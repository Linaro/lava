# LTP

The [Linux Test Project (LTP)](https://github.com/linux-test-project/ltp)
provides tests to the open source community for validating reliability,
robustness, and stability of the Linux Kernel.

This example job demonstrates running the LTP `smoketest` suite on an `ampereone`
server. The `ltp.tar.xz` pre-built binaries are deployed to the root filesystem
as an overlay. A local NVMe partition mounted to `/scratch` is used as the LTP
TMPDIR.

```yaml
device_type: ampereone
job_name: arm64-ltp-smoke

visibility: public
priority: 80

timeouts:
  job:
    minutes: 60
  connection:
    minutes: 2
  actions:
    finalize:
      seconds: 60
    power-off:
      seconds: 60

context:
  arch: arm64
  extra_kernel_args: ' rw'

actions:
- deploy:
    to: tftp
    kernel:
      url: https://storage.tuxsuite.com/public/ampere/ci/builds/3BgK8gsSp9l33hXcgInsWQXEYEy/Image.gz
      compression: gz
      type: image
    nfsrootfs:
      url: https://storage.tuxboot.com/debian/20250722/trixie/arm64/rootfs.tar.xz
      compression: xz
      format: tar
      overlays:
        modules:
          url: https://storage.tuxsuite.com/public/ampere/ci/builds/3BgK8gsSp9l33hXcgInsWQXEYEy/modules.tar.xz
          compression: xz
          format: tar
          path: /usr/
        overlay-00:
          url: https://storage.tuxboot.com/overlays/debian/trixie/arm64/ltp/master/ltp.tar.xz
          compression: xz
          format: tar
          path: /
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
          format: Lava-Test Test Definition 1.0
          name: prep-tests
          description: Device preparation
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
    - from: url
      name: ltp-smoke
      path: automated/linux/ltp/ltp.yaml
      repository: https://github.com/Linaro/test-definitions/releases/download/2025.10.01/2025.10.tar.zst
      compression: zstd
      lava-signal: kmsg
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
    timeout:
      minutes: 5
```

See [ltp test definition](https://github.com/Linaro/test-definitions/blob/master/automated/linux/ltp/ltp.yaml)
for what each test parameter does.
