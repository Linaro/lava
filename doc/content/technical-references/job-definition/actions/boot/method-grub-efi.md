# GRUB EFI

The `grub-efi` boot method is used to boot a device via GRUB loaded from UEFI.

```yaml
- boot:
    method: grub-efi
    commands: nfs
    auto_login:
      login_prompt: "login:"
      username: root
    prompts:
    - 'root@stretch:'
```

!!! note
    In most cases, starting GRUB from UEFI requires using the
    [uefi-menu](./method-uefi-menu.md) method as well. Admins can refer to the
    [`mustang-grub-efi.jinja2`](https://gitlab.com/lava/lava/-/blob/master/etc/dispatcher-config/device-types/mustang-grub-efi.jinja2)
    device type template for an example of how to make selections from a UEFI
    menu to load GRUB.

## Parameters

This boot method shares the same job parameter supported by the
[grub](./method-grub.md) boot method.

## Example job

```yaml
job_name: mustang grub-efi example job
device_type: mustang

priority: medium
visibility: public

timeouts:
  job:
    minutes: 15
  connection:
    minutes: 2

actions:
- deploy:
    to: tftp
    kernel:
      url: https://example.com/vmlinuz-4.9.0-2-arm64
      type: zimage
    ramdisk:
      url: https://example.com/initrd.img-4.9.0-2-arm64
      compression: gz
    modules:
      url: https://example.com/modules.tar.gz
      compression: gz
    nfsrootfs:
      url: https://example.com/stretch-arm64-nfs.tar.gz
      compression: gz
    timeout:
      minutes: 5

- boot:
    method: grub-efi
    commands: nfs
    auto_login:
      login_prompt: "login:"
      username: root
    prompts:
    - 'root@stretch:'
    timeout:
      minutes: 5

- test:
    definitions:
    - repository: https://github.com/Linaro/test-definitions
      from: git
      path: automated/linux/smoke/smoke.yaml
      name: smoke-tests
    timeout:
      minutes: 5
```

--8<-- "refs.txt"
