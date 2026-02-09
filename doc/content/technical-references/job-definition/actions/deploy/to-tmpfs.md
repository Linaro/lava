# TMPFS

Downloads files to a temporary directory on the LAVA worker, making them
available locally for boot methods that flash or run on the worker.

To date, this deployment method is used by the following boot methods:
`cmsis-dap`, `dfu`, `jlink`, `openocd`, `pyocd`, and `qemu`.

```yaml title="QEMU example" hl_lines="1-7"
- deploy:
    to: tmpfs
    images:
        rootfs:
          image_arg: -drive format=qcow2,file={rootfs}
          url: http://example.com/debian-buster.qcow2.zst
          compression: zstd
    timeout:
      minutes: 5

- boot:
    method: qemu
    media: tmpfs
    prompts:
    - "root@debian:"
    auto_login:
      login_prompt: "login:"
      username: root
    timeout:
      minutes: 5
```


```yaml title="pyOCD example" hl_lines="1-5"
- deploy:
    to: tmpfs
    images:
        zephyr:
          url: http://example.com/zephyr.bin
    timeout:
      minutes: 5

- boot:
    method: pyocd
    timeout:
      minutes: 5
```

## images

To deploy images using tmpfs, the job definition writer needs to specify a
unique **label** for each image. Depending on the boot method, an `image_arg`
may also be required to specify how the tool handles the image.

### label

The label is the key under `images:` that identifies each image. It is used to
identify the image by the following boot actions. It also can be used as a
placeholder `{label}` in the `image_arg` to reference the downloaded file path.

### image_arg

The `image_arg` determines how the boot method handles the image. When specified,
it should include a placeholder (referencing the label) which exactly matches
the key of the same block in the list of images. The actual location of the
downloaded file will then replace the placeholder.

In the QEMU example, the label is `rootfs` and the `image_arg` includes the
matching placeholder `{rootfs}`. If the final location of the downloaded image
is `/<DISPATCHER_DOWNLOAD_DIR>/tmp/442/deployimages-td1ofegd/rootfs/debian-buster.qcow2`,
then the final argument passed to QEMU would include
`-drive format=raw,file=/<DISPATCHER_DOWNLOAD_DIR>/tmp/442/deployimages-td1ofegd/rootfs/debian-buster.qcow2`.

!!! note
    Single brace before and after the label and **no whitespace**. This is test
    job definition syntax, not Jinja.

Multiple images can be supplied, but the test job definition writer is
responsible for ensuring that the `image_arg` values make sense to the target
tool.

!!! note
    For some boot methods like `pyocd`, `image_arg` is optional. The flashing
    tool will automatically use the downloaded file path with flashing arguments
    defined in the device type. For `qemu`, `image_arg` is required because QEMU
    needs to know how to use each image (e.g., as a disk drive via `-drive`, as
    a kernel via `-kernel`, or as an initrd via `-initrd`).

### url

See [url](./index.md#url)

### compression

See [compression](./index.md#compression)
