# Boot Action

The `boot` action is used to boot the device using the deployed files.
Depending on the parameters in the job definition, this could be by executing a
command on the dispatcher (e.g., `qemu-system-x86_64`) or by connecting to the
device over serial or SSH. Depending on the power state of the device and the
device configuration, the device may be powered up or reset to provoke the
boot.

Every `boot` action **must** specify a [method](#method) which determines how
to boot the deployed files on the device. Depending on the method, other
parameters may be required.

Boot actions which result in a POSIX-type login or shell must specify a list of
expected [prompts](#prompts) which will be matched against the output to
determine the endpoint of the boot process. There are no default prompts. The
job definition writer is responsible for providing a list of all possible
prompts.

Boot is a top level action that is part of the `actions` list. Here is a common
example of boot action from the test job definition:

```yaml
actions:
- boot:
    timeout:
      minutes: 15
    method: u-boot
    commands: nfs
    auto_login:
      login_prompt: 'login:'
      username: root
      password_prompt: "Password:"
      password: "secret"
    prompts:
    - 'root@device:~#'
```

## timeout

See [Action timeout](../../timeouts.md#action-timeout)

## method

The boot `method` determines how the device is booted and which commands and
prompts are used to determine a successful boot. Each method is documented
separately.

## commands

For the following bootloader-based boot methods, one of the key definitions in
the device type template is the list of boot `commands` that the device needs.
These are sets of specific commands that will be run to boot the device.

- `bootloader`
- `depthcharge`
- `ipxe`
- `grub`
- `grub-efi`
- `u-boot`

The `commands` parameter can be specified in two ways:

1. **A predefined command set name** — predefined in the device type template,
such as `nfs`, `ramdisk` and `usb`. See your device dictionary for the full
list.
2. **[A list of custom boot commands](#custom-boot-commands)** — specified
directly in the job definition

### Placeholder substitution

The commands typically include placeholders. At runtime, LAVA substitutes them
with dynamic data. For example, this is the raw predefined U-Boot commands for
booting from `nfs`:

```yaml
commands:
- "usb start"
- "setenv autoload no"
- "setenv initrd_high 0xffffffff"
- "setenv fdt_high 0xffffffff"
- "dhcp"
- "setenv serverip {SERVER_IP}"
- "tftp {KERNEL_ADDR} {KERNEL}"
- "tftp {RAMDISK_ADDR} {RAMDISK}"
- "tftp {TEE_ADDR} {TEE}"
- "setenv initrd_size ${filesize}"
- "tftp {DTB_ADDR} {DTB}"
- "setenv bootargs ' root=/dev/nfs rw nfsroot={NFS_SERVER_IP}:{NFSROOTFS},tcp,hard earlycon=uart8250,mmio32,0x3f215040 ip=dhcp'"
- "{BOOTX}"
```

!!! note
    In some cases, the boot commands list in the template may not provide
    **all** of the commands used; lines will also be generated from other data
    in the template. For example, the command `setenv kernel_addr_r '0x82000000'`
    might be generated from load addresses which match the type of kernel being
    deployed.

The final parsed and expanded boot commands are reported in the job logs:

```text
- usb start
- setenv autoload no
- setenv initrd_high 0xffffffff
- setenv fdt_high 0xffffffff
- dhcp
- setenv serverip 192.168.18.116
- tftp 0x01000000 347/tftp-deploy-lf41516b/kernel/zImage
- tftp 0x04000000 347/tftp-deploy-lf41516b/ramdisk/ramdisk.cpio.gz.uboot
- setenv initrd_size ${filesize}
- tftp 0x03f00000 347/tftp-deploy-lf41516b/dtb/bcm2837-rpi-3-b-plus.dtb
- setenv bootargs ' root=/dev/nfs rw nfsroot=192.168.18.116:/var/lib/lava/dispatcher/tmp/347/extract-nfsrootfs-bzt0mf_r,tcp,hard earlycon=uart8250,mmio32,0x3f215040 ip=dhcp'
- bootz 0x01000000 0x04000000 0x03f00000
```

### Custom boot commands

During testing and development, it can be useful to override the boot commands
from the device-type template. These custom commands must still **include the
placeholders** so that LAVA can substitute paths and values:

```yaml
- boot:
    method: ipxe
    commands:
    - dhcp net0
    - set console console=ttyS0,115200n8 lava_mac={LAVA_MAC}
    - set extraargs ip=dhcp root=/dev/sda1 rw
    - kernel tftp://{SERVER_IP}/{KERNEL} ${extraargs} ${console}
    - initrd tftp://{SERVER_IP}/{RAMDISK}
    - boot
```

!!! warning
    This support is recommended for corner cases that can't be fixed at the
    device-type level. LAVA will raise a warning each time custom commands are
    used. Abuse of this feature can potentially stop devices from working in
    subsequent tests, or even damage them permanently.

    If you need to use these commands regularly, request that a label be created
    in the device type for this command set, or propose a patch.

### Extra kernel arguments

A test job may require extra kernel command line options. The
[job context](../../../../introduction/glossary.md#job-context) can be used to
append strings to the kernel command line:

!!! note
    `context` is a top-level element of the LAVA job definition, not part of
    the `boot` section.

```yaml
context:
  extra_kernel_args: vsyscall=native
```

The parameter values need to be separated by whitespace and will be added to
the command line with a prefix and suffix of a single space.

The possible values which can be used are determined solely by the support
available within the kernel provided to the DUT.

### nfsroot arguments

To append values to the NFS options, use `extra_nfsroot_args`:

```yaml
context:
  extra_nfsroot_args: ",rsize=4096 nfsrootdebug"
```

!!! note
    `extra_nfsroot_args` are appended directly to the existing NFS flags
    `nfsroot={NFS_SERVER_IP}:{NFSROOTFS},tcp,hard`. If the appended string
    contains an extra flag, it must come first and the string must start with
    a comma. Other options can be separated by a space.

    Example result: `nfsroot=10.0.0.1:/nfs,tcp,hard,rsize=4096 nfsrootdebug`

See also: [Kernel documentation for NFSROOT](https://www.kernel.org/doc/Documentation/filesystems/nfs/nfsroot.txt)

## auto_login

Some systems require the test job to specify a username and optionally a
password to login. These values must be specified in the test job definition.
If the system boots directly to a prompt without needing a login, the
`auto_login` section can be omitted.

### login_prompt

The prompt to match when the system requires a login. This prompt needs to be
unique across the entire boot sequence, so typically includes `:` and should
be quoted:

```yaml
- boot:
    auto_login:
      login_prompt: 'login:'
      username: root
```

!!! note
    If `login_prompt` is not matched during boot, LAVA will send control
    characters to the shell assuming a kernel alert occurred. This may result
    in incorrect login attempts, but LAVA will automatically retry after
    recognizing the `Login incorrect` message.

### username

Whenever a `login_prompt` is specified, a `username` is also required. The
username should either be `root` or a user with passwordless `sudo` access.

### password_prompt

If the login requires a password as well as a username, the `password_prompt`
must be specified:

```yaml
- boot:
    auto_login:
      login_prompt: 'login:'
      username: root
      password_prompt: 'Password:'
      password: rootme
```

!!! note
    If `password_prompt` is not matched during login, or a password is required
    but not provided, LAVA will recognize the `Login timed out` message, stop
    the job execution, and log the error.

### password

Whenever a `password_prompt` is specified, a `password` is also required.

### login_commands

A list of commands to run after the initial login and before setting the shell
prompt. This is typically used to switch from a regular user to root:

```yaml
- boot:
    auto_login:
      login_prompt: 'login:'
      username: user
      password_prompt: 'Password:'
      password: pass
      login_commands:
      - sudo su
```

!!! note
    No interactive input (such as a password) can be provided with
    `login_commands`.

## prompts

After login (or directly from boot if no login is required), LAVA needs to
match the first prompt offered by the booted system. The full list of possible
prompts **must** be specified in the test job definition.

Each prompt needs to be unique across the entire boot sequence, so typically
includes `:` and needs to be quoted. If the hostname of the device is included
in the prompt, this can be included in the prompt string.

```yaml
- boot:
    prompts:
    - 'root@debian:'
```

When the hostname varies, use a regex pattern:

```yaml
- boot:
    prompts:
    - 'root@(.*):'
```

When using a ramdisk, the prompt may contain brackets which need to be escaped:

```yaml
- boot:
    prompts:
    # escape the brackets to ensure that the prompt does not match
    # kernel debug lines which may mention initramfs
    - '\(initramfs\)'
```

When using `login_commands` that change the user (such as `sudo su`), include
prompts for both the initial user and the final user in the prompts list:

```yaml
- boot:
    auto_login:
      login_prompt: "login:"
      username: pi
      password_prompt: 'Password:'
      password: raspberry
      login_commands:
      - sudo su
    prompts:
    - "pi@raspberrypi:"
    - "root@raspberrypi:"
```

!!! warning "Take care with the specified prompts:"

    - Prompt strings which do not include enough characters can match early,
      resulting in a failed login
    - Prompt strings which include extraneous characters may fail to match
    - Avoid user-specific prompt elements like `$` (unprivileged user) or `#`
      (superuser) or `~` (home directory)
    - The prompt string should **include and usually end with** a colon `:` or
      a colon and space

## transfer_overlay

A LAVA test overlay is a tarball of scripts which run the LAVA Test Shell for
the test job. It also includes the git clones or the downloads of repositories
specified in the test job submission and the LAVA helper scripts. Normally,
applying the overlay is integrated into the test job automatically. When the
rootfs is not deployed directly by LAVA, for example booting from persistent
storage or a pre-installed system, it is necessary to transfer the overlay from
the LAVA worker to the DUT using commands within the booted system prior to
starting to run the test shell.

The `transfer_overlay` option allows LAVA to transfer the LAVA test overlay to
the DUT after boot.

```yaml
- boot:
    method: minimal
    transfer_overlay:
      download_command: wget
      unpack_command: tar -C / -xzf
    prompts:
    - 'root@debian:~#'
```

!!!note
    The overlay is transferred before any test shell operations run. Therefore,
    the commands required for the selected `transfer_method` must be available
    and functional after boot and before running the test shell. For `http` and
    `nfs` transfers this means the network, the download command and the
    unpack command **must** work. For the `zmodem` transfer method only the
    unpack command is required locally.

The `download_command` and `unpack_command` can include one or more shell
commands. Avoid using redirects (`>` or `>>`) or other complex shell syntax.
This example below changes to `/tmp` to ensure there is enough writeable space
for the download. This feature can also be used to install the utilities or
wait for the network needed for the transfer.


```yaml
- boot:
    transfer_overlay:
      download_command: cd /tmp ; wget
      unpack_command: tar -C / -xzf
```

### transfer_method

Optional. Defaults to `http`. Can be set to `nfs` for NFS-based transfer or to
`zmodem` for ZMODEM-based transfer.

#### http

This will transfer overlay through the worker's Apache service.

```yaml
- boot:
    transfer_overlay:
      transfer_method: http
      download_command: wget --progress=dot:giga
      unpack_command: tar -C / -xzf
```

The `--progress=dot:giga` options to wget in the example above optimize the
output for serial console logging to avoid wasting line upon line of progress
percentage dots. If the system uses `busybox`, these options may not be
supported by the version of `wget` on the device.

#### nfs

This will transfer overlay through the worker's NFS server service.

```yaml
- boot:
    transfer_overlay:
      transfer_method: nfs
      download_command: mount -t nfs -o nolock
      unpack_command: cp -rf
```

Since the `mount` command requires the NFS mount helper program to mount NFS
shares, the target device **must** have NFS client utilities installed. This is
typically provided by:

- `nfs-common` package on Debian-based systems
- `nfs-utils` package on Fedora-based systems

Example for installing the package for Debian at job runtime:

```yaml
- boot:
    transfer_overlay:
      transfer_method: nfs
      download_command: apt update && apt-get install -y nfs-common && mount -t nfs -o nolock
      unpack_command: cp -rf
```

When needed, you can append `-o Acquire::Check-Valid-Until=false` to the
`apt update` command for skipping APT's repository time validity check.

#### zmodem

This will transfer overlay through the ZMODEM inline file transfer protocol
from the worker to the target device.

```yaml
- boot:
    transfer_overlay:
      transfer_method: zmodem
      unpack_command: tar -C / -xzf
```

The worker and target device **must** have respectively the `sz` and `rz`
utilities installed. This is typically provided by:

- `lrzsz` package on Debian-based or Fedora-based systems

The `zmodem` transfer method is interesting for target device that does not
have an Ethernet connection. As a consequence, the `rz` utility should be
available by default in the flashed image.

The worker and the target device communicate over a `UART`. This `UART` usually
appears on the worker as `/dev/ttyUSB<N>` or `/dev/ttyACM<N>`. This value
**must** be defined in the device dictionary using the `device_info` variable
and the `uart` field. This is an example taken from a device dictionary.

```jinja
{% set device_info = [{'uart': '/dev/ttyUSB0'}] %}
```


### download_command

The command used to download the overlay file from the LAVA worker. This will
be called with the URL to the overlay file appended. For example:

```shell
wget http://192.168.18.116/tmp/427/compress-overlay-5jg6nqov/overlay-1.1.5.tar.gz
```

### unpack_command

The command used to extract the overlay archive. The overlay filename will be
appended to this command. For example: `tar -C / -xzf overlay-1.1.5.tar.gz`

!!! note
    The `-C /` command to tar is **essential** or the test shell will not be
    able to start. The overlay will use `gzip` compression, so pass the `z`
    option to `tar`.

Some systems do not store the current time between boots. The `--warning
no-timestamp` option is a useful addition for `tar` for those systems but note
that `busybox tar` does not support this option.

## parameters

The optional `parameters` block in the job definition boot action allows you to
override the following device constants.

### bootloader-final-message

The string that the bootloader prints when it has finished. After sending the
last bootloader command, LAVA waits for this message before continuing.

See the boot method in your device type for the default value. Adjust the value
in the device type or in the boot action parameters block:

```yaml
- boot:
    method: u-boot
    commands: nfs
    parameters:
      bootloader-final-message: "Booting kernel"
    prompts:
    - 'root@device:~#'
```

### kernel-start-message

The string that indicates the kernel has started booting. LAVA waits for this
message and then starts parsing the kernel boot logs to detect common kernel
boot errors.

The default is `Linux version [0-9]`. Adjust it in your device type or in the
boot action parameters block:

```yaml
- boot:
    method: minimal
    parameters:
      kernel-start-message: 'Starting kernel'
    prompts:
    - 'root@device:~#'
```

!!!note
    Only after the start message is matched, LAVA starts waiting for the boot
    prompts or login prompt to appear. When needed, set the string to `""` to
    skip the matching.

### shutdown-message

The message indicates the system is shutting down or rebooting. It is used when
performing a [soft reboot](#soft_reboot). LAVA waits for this string to confirm
that the device has started shutting down or rebooting.

The default is `The system is going down for reboot NOW`. You can override it
in your device configuration or in the boot action parameters.

```yaml
- boot:
    method: u-boot
    commands: ramdisk
    parameters:
      shutdown-message: "reboot: Restarting system"
    prompts:
    - 'root@device:~#'
```

## soft_reboot

When LAVA needs to reset the device and the `hard_reset_command` is not defined
in the device configuration, it sends a soft reboot command.

By default, LAVA sends the command in the default list
`["reboot", "reboot -n", "reboot -nf"]` one by one until the
[shutdown-message](#shutdown-message) is matched.

You can override the default in your device configure using the
`soft_reboot_command` variable or in the boot action parameters using the
`soft_reboot` option.

```yaml
- boot:
    method: u-boot
    commands: ramdisk
    soft_reboot: reboot -nf
    prompts:
    - 'root@device:~#'
```

## ignore_kernel_messages

Some test scenarios deliberately force a kernel panic. To prevent LAVA from
stopping the job when this happens, set `ignore_kernel_messages` to `true`:

```yaml
- boot:
    method: u-boot
    ignore_kernel_messages: true
    prompts:
    - 'root@device:~#'
```

!!! warning
    When `ignore_kernel_messages` is `true`, LAVA won't be able to detect any
    "legitimate" kernel crashes either.

This option also disables detection of unexpected board resets. The pattern
`U-Boot SPL 20[0-9][0-9]` is used to detect board reset. Disabling kernel
message parsing can be useful when a board reset is expected.

Default value: `false`
