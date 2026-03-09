# NBD (Network Block Device)

The `nbd` deployment method is used to support NBD root deployments.  Files are
downloaded to a temporary directory on the worker. The rootfs is shared through
`xnbd-server` and the filenames are substituted into the
[bootloader commands](../boot/common.md#commands) specified in the device
configuration or overridden in the job definition.

```yaml
- deploy:
    to: nbd
    kernel:
      url: http://example.com/vmlinuz
      type: zimage
    initrd:
      url: http://example.com/initramfs.ext4.gz.u-boot
    nbdroot:
      url: http://example.com/rootfs.ext4.xz
      compression: xz
    dtb:
      url: http://example.com/dtb.dtb
```

## kernel

Required. The kernel to boot on the device.

### type

Specifies the type of kernel being downloaded. Supported types:

- `image`
- `uimage`
- `zimage`

## initrd

The initrd contains all necessary files, daemons and scripts to bring-up the
`nbd-client` and `pivot_root` to the final rootfs.

!!!note
    The nbdroot filesystem will not be modified prior to the boot. Since the
    filesystems are using security labels and the modification would alternate
    the FS. So the [LAVA overlay](./index.md#lava-overlay) needs to be transferred
    after the boot with [`transfer_overlay`](../boot/common.md#transfer_overlay).

## nbdroot

The root filesystem image shared over xnbd-server.

### url

See [url](./index.md#url)

### compression

The NBD filesystem image is unpacked into a temporary directory on the LAVA
worker in a location supported by the NBD server.

The compression method **must** be specified if the file is compressed. See
[compression](./index.md#compression).

## dtb

Optional Device Tree Blob.

## modules

Modules are not supported in the NBD deployment method. Modules must be part of
the filesystem already.

## Example job

```yaml
# NBD root deployment
job_name: standard Debian ARMMP nbd test on bbb
device_type: beaglebone-black

priority: medium
visibility: public

timeouts:
  job:
    minutes: 10
  action:
    minutes: 5
  connection:
    minutes: 2

actions:
# NBD_DEPLOY_BLOCK
- deploy:
    timeout:
      minutes: 5
    to: nbd
    kernel:
      url: http://example.com/vmlinuz
      type: zimage
    initrd:
      url: http://example.com/initramfs.ext4.gz.u-boot
    nbdroot:
      url: http://example.com/rootfs.ext4.xz
      compression: xz
    dtb:
      url: http://example.com/dtb.dtb

# NBD_BOOT_BLOCK
- boot:
    method: u-boot
    commands: nbd
    auto_login:
      login_prompt: 'login:'
      username: root
    prompts:
    - 'root@jessie:'
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
