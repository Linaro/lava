# Boot Testing

LAVA supports a large number of
[deploy methods](../../technical-references/job-definition/actions/deploy/index.md)
and
[boot methods](../../technical-references/job-definition/actions/boot/common.md),
making it easy to validate that a firmware, kernel, or root filesystem boots
correctly across many different hardware platforms.

## Boot test

A typical boot test deploys an image, boots the device, waits for a login prompt:

```yaml
job_name: Boot test
device_type: qemu

timeouts:
  job:
    minutes: 20

priority: medium
visibility: public

context:
  arch: amd64

actions:
- deploy:
    to: tmpfs
    images:
      rootfs:
        image_arg: -drive format=qcow2,file={rootfs}
        url: https://storage.lavacloud.io/health-checks/qemu/tmpfs/debian-buster.qcow2.zst
        compression: zstd
    timeout:
      minutes: 20

- boot:
    method: qemu
    media: tmpfs
    prompts:
    - 'root@debian:~#'
    auto_login:
      login_prompt: "login:"
      username: root
    timeout:
      minutes: 5
```

## Boot duration

LAVA records how long the `auto_login` action takes using the `lava/login-action`
test case in job results, allowing teams to track boot duration over time. This
makes it easy to detect regressions in boot performance across kernel or
firmware changes.

For more precise measurement, if supported by the booted OS, `systemd-analyze`
can be used:

```yaml
- test:
    interactive:
    - name: systemd-analyze
      prompts:
      - 'root@(.*):'
      script:
      - command: 'systemd-analyze'
      - command: 'systemd-analyze blame --no-pager | head -20'
    timeout:
      minutes: 5
```
