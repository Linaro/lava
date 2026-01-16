# FVP

Allows running of FVP (or Fixed Virtual Platforms) from a Docker container.
Generally speaking, FVP are launched in Docker and UART output is served over a
telnet connection locally. A pattern is given in the job definition to find the
port of the UART from the FVP output. LAVA will then connect via `telnet` to
view UART output.

```yaml
- deploy:
    to: fvp
    images:
      disk:
        url: http://fileserver/path/to/fvp/grub-busybox.img
        format: ext4
        overlays:
          lava: true
```

## images

See [images](./index.md#artifacts)

### overlays

See [overlays](./index.md#overlays)
