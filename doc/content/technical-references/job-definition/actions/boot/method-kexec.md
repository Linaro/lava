# Kexec

The `kexec` boot method replaces the running kernel with a new one using
[kexec](https://man7.org/linux/man-pages/man8/kexec.8.html), without going
through the bootloader.

The DUT must already be booted to a shell by a previous boot action, and
`kexec-tools` must be installed in this system.

```yaml
- boot:
    method: kexec
    kernel: /home/vmlinux
    dtb: /home/dtb
    initrd: /home/initrd
    kernel-config: /boot/config-*
    boot_message: Booting Linux
    options:
    - "--reuse-cmdline"
    prompts:
    - 'root@debian:~#'
```

LAVA sends the following commands to the DUT shell:

```shell
zgrep -i kexec /boot/config-* |grep -v '^#'
/sbin/kexec --load /home/vmlinux --dtb /home/dtb --initrd /home/initrd --reuse-cmdline
/sbin/kexec -e
```

LAVA then waits for the `boot_message`, the optional
[auto_login](common.md#auto_login) and the [prompts](common.md#prompts).

## boot_message

Required. The message printed by the new kernel when it starts, for example
`Booting Linux`.

## kernel

The path, on the DUT, to the kernel. Passed to `--load`.

Required, unless the `options` include the load arguments.

## dtb

Optional. The path, on the DUT, to the dtb. Passed to `--dtb`.

## initrd

Optional. The path, on the DUT, to the initrd. Passed to `--initrd`.

## options

Optional. A list of extra arguments added to the load command.

## command

Optional. The kexec binary to use. Defaults to `/sbin/kexec`.

## kernel-config

Optional. The path, on the DUT, to the kernel configuration.

## deploy

Optional, defaults to `false`. When `true`, LAVA first downloads the `kernel`,
`initrd` and `dtb` files from the LAVA worker to the DUT, using `wget`, to the
paths given in the boot action.

These files must have been downloaded by a previous deploy action under the same
names (`kernel`, `initrd` and `dtb`).

## on_panic

Optional, defaults to `false`. When `true`, the kernel is loaded as a crash
kernel (`--load-panic`) and LAVA triggers a kernel panic
(`echo c > /proc/sysrq-trigger`) instead of calling `kexec -e`. This can be used
to test kdump.

## transfer_overlay

See [transfer_overlay](common.md#transfer_overlay).

!!! tip "Timeout"
    If kexec fails, the device usually hangs. Use a short timeout for the
    `call-kexec` action:

    ```yaml
    timeouts:
      actions:
        call-kexec:
          seconds: 45
    ```
