# NFS

The `nfs` deployment method is used to deploy a rootfs and optional kernel
modules to the NFS server that running on the LAVA worker.

## nfsrootfs

A compressed tarball containing the rootfs.

```yaml
deploy:
  to: nfs
  nfsrootfs:
    url: https://example.com/rootfs.tar.xz
    compression: xz
```

## modules

Optional. A compressed tarball containing kernel modules.

```yaml
deploy:
  to: nfs
  nfsrootfs:
    url: https://example.com/rootfs.tar.xz
    compression: xz
  modules:
    url: https://example.com/modules.tar.xz
    compression: xz
```

### overlays

The `nfsrootfs` action supports overlays with the `format` specified.

See [overlays](./index.md#overlays)

## images

Alternatively, you can specify a list of images to deploy. Here is an example
`nfs` deploy action for the `qemu-nfs` boot method.

```yaml
- deploy:
    to: nfs
    images:
      nfsrootfs:
        url: http://example.com/jessie-arm64-nfs.tar.gz
        image_arg: 'nfsroot={NFS_SERVER_IP}:{nfsrootfs},tcp,hard'
        compression: gz
      kernel:
        url: http://example.com/vmlinuz-4.9.0-2-arm64
        image_arg: -kernel {kernel}
      initrd:
        url: http://example.com/initrd.img-4.9.0-2-arm64
        image_arg: -initrd {initrd}
```

### image_arg

See [image_arg](./to-tmpfs.md#image_arg)
