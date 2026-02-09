# ISO Installer

Provides QEMU operations using an operating system installer into a new image
and then boot into the installed image to run the specified test definitions.

!!! note
    Currently only tested with Debian installer and the `qemu-iso` boot method.

```yaml
- deploy:
    to: iso-installer
    os: debian_installer
    images:
      iso:
        url: https://cdimage.debian.org/debian-cd/13.3.0/amd64/iso-cd/debian-13.3.0-amd64-netinst.iso
        image_arg: -drive file={iso},index=2,media=cdrom,readonly=on
      preseed:
        url: https://storage.lavacloud.io/health-checks/qemu/iso/preseed.cfg
    iso:
      kernel: /install.amd/vmlinuz
      initrd: /install.amd/initrd.gz
      installation_size: 3G
    timeout:
      minutes: 30
```

## images

The ISO and the preseed file can be tightly coupled but point releases of a
stable release will typically continue to work with existing preseed files.
LAVA tests of the installer tend to only install the base system in order to
test kernel functionality rather than the operating system itself.

### iso

The operating system installer ISO image. This ISO should contain the installer
that will be used to install the operating system onto a new disk image.

#### image_arg

QEMU requires `,media=cdrom,readonly=on` to handle the ISO correctly.

### preseed

Debian Installer can retrieve settings from a `preseed` file to allow the
installation to proceed without prompting for information.

## iso

### kernel

Absolute path to the kernel within the installer ISO. LAVA extracts the kernel
from the ISO so it can be booted directly by QEMU with custom kernel
command-line options required for automated installation.

### initrd

Absolute path to the initial ramdisk within the installer ISO. LAVA extracts
the initrd from the ISO so it can be passed directly to QEMU, enabling
custom boot configuration for the installer.

!!! note
    Both `kernel` and `initrd` paths must:

    - Start with `/` (absolute path from the ISO root)
    - Be unique within the ISO

### installation_size

Size of the empty image to be provided to the installer. Typically, a maximum of
6G. Use megabytes for a smaller image, although ~3G is likely to be the
smallest practical size for a recent Debian installer.
