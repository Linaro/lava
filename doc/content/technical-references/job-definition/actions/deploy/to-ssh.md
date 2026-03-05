# SSH

The `ssh` deployment method is used to prepare the LAVA overlay needed by the
[ssh boot method](../boot/method-ssh.md).

```yaml
- deploy:
    to: ssh
    os: debian
```

## os

The operating system running on the device. LAVA uses this to select the
right options for applying the LAVA overlay.
