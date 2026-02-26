# Fastboot

The `fastboot` boot method boots a device that has been deployed using the
[Fastboot](https://en.wikipedia.org/wiki/Fastboot) protocol.

```yaml
- boot:
    method: fastboot
    docker:
      image: linaro/noble-adb-fastboot
      local: true
    prompts:
    - 'root@linaro-developer:~#'
```

For boot sequence,see [fastboot_sequence](../../../../technical-references/configuration/device-dictionary.md#fastboot_sequence)

## docker

See [docker](../deploy/to-fastboot.md#docker)

## commands

Some test jobs need to send additional `fastboot` commands before rebooting the
device. For example, when images are deployed to A/B partition slots, a command
is needed to activate the correct slot before boot.

If the deployment action used `boot_a` as the partition label instead of `boot`,
then the following command ensures the device boots from `boot_a` instead of
`boot_b` (which may contain a stale deployment or be empty):

```yaml
- boot:
    method: fastboot
    commands:
    - --set-active=a
```

Each entry in `commands` is passed as an argument to the `fastboot` binary and
issued by LAVA sequentially.

## prompts

See [prompts](./common.md#prompts)
