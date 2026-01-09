# avh

Creates and boots Arm Virtual Hardware models.

```yaml
- boot:
    method: avh
    bootargs:
      normal: earlycon=uart8250,mmio32,0xfe215040 console=ttyS0,115200n8 rw rootwait root=/dev/mmcblk0p2 coherent_pool=1M 8250.nr_uarts=1 cma=64M
      restore: earlycon=uart8250,mmio32,0xfe215040 console=ttyS0,115200n8 console=tty0 rw rootwait root=/dev/mmcblk0p2 coherent_pool=1M 8250.nr_uarts=1 cma=64M init=/usr/lib/raspi-config/init_resize.sh
    docker:
      image: ghcr.io/vi/websocat:v1.14.1
      local: true
```

## bootargs

(optional) The `bootargs` dictionary allows you to override the default Kernel
bootargs provided by the AVH model.

The `normal` key is used for every regular boot.

The `restore` key, if present, is used for a first boot prior to the device
being declared ready. It is expected that the device will reboot itself to
indicate that this phase is complete. It is used, for example, on the Raspberry
Pi 4 to expand the root FS.

## docker

(optional) `avh` boot method uses [websocat](https://github.com/vi/websocat) for
connecting to AVH device serial console.

[ghcr.io/vi/websocat:v1.14.1](https://github.com/vi/websocat/pkgs/container/websocat/623664453?tag=v1.14.1)
docker image is used by default. The docker image specified in the job definition
overrides the default one.

!!! note
    An `avh` deploy action before this boot action is required. The boot method
    uses the image path from the deploy action to create the AVH instance.
