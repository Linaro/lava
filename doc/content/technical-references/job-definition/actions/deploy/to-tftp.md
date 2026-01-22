# TFTP

The `tftp` deploy action is used to deploy files via
[TFTP](../../../../introduction/glossary.md#tftp) for network booting. This
is commonly used with bootloaders like U-Boot that can fetch kernel, device
tree, ramdisk, and other files over the network.

Files are downloaded to a temporary directory in the TFTP tree and the
file names are substituted into the bootloader commands specified in the device
configuration or overridden in the job definition.

```yaml
actions:
- deploy:
    to: tftp
    kernel:
      url: http://example.com/vmlinuz
      type: zimage
    dtb:
      url: http://example.com/device.dtb
    ramdisk:
      url: http://example.com/initrd.gz
      compression: gz
```

## url

See [url](./index.md#url)

## compression

See [compression](./index.md#compression)

## kernel

The kernel is a required artifact for TFTP deployments.

### type

Specifies the type of kernel being downloaded.

Supported types:

- `image` - used with `booti` command
- `zimage` - used with `bootz` command
- `uimage` - used with `bootm` command

Boot methods like `u-boot` use this information to determine the appropriate
load addresses and boot commands.

## dtb

See [DTB](../../../../introduction/glossary.md#dtb)

## dtbo

Device Tree Blob for Overlay (DTBO) - additional device tree files that can be
applied on top of the base DTB. Multiple overlays can be specified as a list.

See also: [U-Boot Device Tree Overlays](https://docs.u-boot.org/en/latest/usage/fdt_overlays.html)

```yaml
dtbo:
- url: https://example.com/overlay1.dtbo
- url: https://example.com/overlay2.dtbo
```

### Enabling DTBO

By default, dtb overlay is not enabled for uboot-based devices, you need to
enable it in your device type dictionary:

```jinja
{% set enable_dtbo_support = 'true' %}
```

Additionally, configure custom DTBO load addresses and `dtb_base_resize` if
your device configuration differs from the defaults:

```jinja
{% set bootm_dtbo_addr = '0x93c00000' %}
{% set bootz_dtbo_addr = bootm_dtbo_addr %}
{% set dtb_base_resize = dtb_base_resize | default(1048576) %}
```

The same DTBO load address can be used for every overlay, as they are loaded
and applied by LAVA sequentially in the following order.

1. Load the base DTB
2. Resize it to accommodate overlays
3. Load each overlay to the same address
4. Apply each overlay in sequence using `fdt apply`

```shell title="Example U-Boot commands:"
- fdt addr ${fdt_addr}
- fdt resize 1048576
- tftp 0x93c00000 577262/tftp-deploy-o40xvdqb/dtbo0/overlay1.dtbo
- fdt apply 0x93c00000
- tftp 0x93c00000 577262/tftp-deploy-o40xvdqb/dtbo1/overlay2.dtbo
- fdt apply 0x93c00000
```

## modules

```yaml
modules:
  url: http://example.com/modules.tar.gz
  compression: gz
```

A tarball of kernel modules for the supplied kernel. The file **must** be a tar
file and the compression method **must** be specified.

Modules are required when:

- The kernel needs modules to locate the rootfs (e.g., NFS or specific
  filesystem drivers)
- Tests within the ramdisk require certain kernel modules

When modules are provided, LAVA can unpack the ramdisk and add the modules
before repacking.

## ramdisk

An initial ramdisk (initrd/initramfs) that can be loaded alongside the kernel.
The ramdisk needs to be unpacked and modified in either of the following two
use cases:

- The LAVA test shell is expected to run inside the ramdisk
- Kernel modules need to be added (e.g., to load network drivers for NFS boot)

If the ramdisk is compressed, the compression method **must** be specified.

### header

If a header is already applied to the ramdisk, the `header` value **must**
specify the type of header. Currently only `u-boot` is supported.

```yaml
ramdisk:
  url: http://example.com/initrd.img.gz
  compression: gz
  header: u-boot
```

This header will be removed before unpacking so that LAVA can overlay files.
LAVA will add the header back if the device requires it. This is controlled by
the `add_header` parameter in the device type template.

### install_modules

The default is `true`. Set to `false` to skip installing kernel modules into the
ramdisk.

```yaml
ramdisk:
  url: http://example.com/initrd.gz
  compression: gz
  install_modules: false
```

### install_overlay

The default is `true`. The overlay is only applied when a test action is present
in the job. Set to `false` to skip installing the LAVA overlay into the ramdisk.

```yaml
ramdisk:
  url: http://example.com/initrd.gz
  compression: gz
  install_overlay: false
```

## nfsrootfs

A tarball containing the root filesystem to be exported via NFS. The device
boots with this filesystem mounted as the root.

```yaml
nfsrootfs:
  url: http://example.com/rootfs.tar.xz
  compression: xz
  format: tar
  overlays:
    kselftest:
      url: http://example.com/kselftest.tar.xz
      compression: xz
      format: tar
      path: /opt/kselftest
```

!!! note "Context options"
    Additional options can be specified via the job definition context:

    - **`extra_nfsroot_args`**: Append NFS mount options (e.g., protocol version)
    - **`extra_kernel_args`**: Append kernel command line arguments

    ```yaml
    context:
      extra_nfsroot_args: ",vers=3"
      extra_kernel_args: "loglevel=7 earlycon"
    ```

### prefix

Optional prefix path within the tarball to use as the root filesystem.

### install_modules

See [install_modules](#install_modules)

### install_overlay

See [install_overlay](#install_overlay)

### overlays

See [overlays](./index.md#overlays)

## persistent_nfs

A persistent NFS URL can be used instead of a compressed tarball. This allows
multiple jobs to share the same NFS export.

!!! warning "Known caveats"
    - Modules are not extracted into the persistent NFS mount
    - LAVA does not shut down the device or attempt to unmount the NFS
      filesystem when the job finishes. The device is simply powered off
    - The test writer needs to ensure that any background processes started
      by the test have been stopped before the test finishes

!!! note
    Only one of `nfsrootfs` or `persistent_nfs` can be specified in a single
    deploy action.

### address

Specifies the address to use for the persistent filesystem.

The `address` **must** include the IP address of the NFS server and the full
path to the directory which contains the root filesystem, separated by a single
colon. In YAML, all values containing a colon **must** be quoted:

```yaml
- deploy:
    to: tftp
    kernel:
      url: http://example.com/vmlinuz
      type: zimage
    persistent_nfs:
      address: "192.168.1.1:/var/lib/lava/dispatcher/tmp/nfsroot"
```

The address supports placeholders (see [URL placeholders](./index.md#url)):

### install_overlay

See [install_overlay](#install_overlay)

## tee

Trusted Execution Environment (TEE) image for devices that support secure
boot with TEE.

When booting with `u-boot`, LAVA can load tee over TFTP. User should provide a
resource called `tee` in the deploy action.

```yaml
- deploy:
    to: tftp
    tee:
      url: file:/local/lava-ref-binaries/fsl-imx6q-sabresd-linux/uTee-6qsdb
```

## preseed

Configuration file for automated OS installations.

When `os` is set to `debian_installer` or `centos_installer`, LAVA
automatically modifies the file to inject the LAVA overlay into the installed
system.

```yaml
- deploy:
    to: tftp
    os: debian_installer
    kernel:
      url: http://example.com/debian-installer/linux
    ramdisk:
      url: http://example.com/debian-installer/initrd.gz
      compression: gz
    preseed:
      url: http://example.com/preseed.cfg
```

Device boot commands can reference:

- `{PRESEED_CONFIG}` — TFTP path to the preseed file (e.g., `url=tftp://{SERVER_IP}/{PRESEED_CONFIG}`)
- `{PRESEED_LOCAL}` — file name embedded in the ramdisk root (e.g, `preseed.cfg`)


## Example jobs

* [Booting from ramdisk](../../../../admin/basic-tutorials/device-setup/u-boot.md#booting-from-ramdisk)
* [Booting from NFS](../../../../admin/basic-tutorials/device-setup/u-boot.md#booting-from-nfs)
