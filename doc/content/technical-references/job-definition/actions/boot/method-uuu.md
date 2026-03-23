# UUU

The `uuu` boot method flashes and boots NXP i.MX devices using the
[UUU (Universal Update Utility)](https://github.com/NXPmicro/mfgtools). See the
[wiki](https://github.com/NXPmicro/mfgtools/wiki) for the complete documentation
of the tool.

```yaml
- boot:
    method: uuu
    commands:
    - uuu: -b sd {boot}
    timeout:
      minutes: 5
```

## Installation

LAVA supports running `uuu` directly on the worker or inside a Docker container.
See [docker](#docker) for running with docker. When running directly, `uuu`
must be installed manually on the LAVA worker since it is not provided as a
dependency by LAVA.

The latest release is available at
<https://github.com/NXPmicro/mfgtools/releases/latest>. A specific version can
be installed using the following commands:

```shell
wget https://github.com/NXPmicro/mfgtools/releases/download/<UUU_VERSION>/uuu
chmod a+x uuu
mv uuu /usr/bin/uuu
```

The `uuu` boot method supports to run [`bcu`](https://github.com/NXPmicro/bcu)
commands, see [using BCU commands](#using-bcu-commands). When needed, the tool
can be installed in the same way.

## Device configuration

Follow the instructions in [UUU](../../../configuration/device-dictionary.md#uuu)
and [BCU](../../../configuration/device-dictionary.md#bcu) to configure your
UUU device.

## commands

Required. The `commands` field is a list of commands to execute. Each entry is
a dictionary with a single `key:value` pair where the key is the protocol and the
value is the command string. Image placeholders like `{boot}` or `{system}` are
replaced with paths to images downloaded during the
[`uuu`](../deploy/to-uuu.md) deployment action.

### Using built-in scripts

UUU provides built-in scripts invoked via the `uuu` protocol with the `-b`
flag:

```yaml
- boot:
    method: uuu
    commands:
    - uuu: -b sd {boot}
```

Non-exhaustive list of available built-in scripts:

```yaml
- uuu: -b emmc {boot}              # Write bootloader to eMMC
- uuu: -b emmc_all {boot} {system} # Write bootloader & rootfs to eMMC
- uuu: -b sd {boot}                # Write bootloader to SD card
- uuu: -b sd_all {boot} {system}   # Write bootloader & rootfs to SD card
```

### Using commands

```yaml
- boot:
    method: uuu
    commands:
    - SDPS: boot -f {boot}
    - FB: continue
    - FB: done
```

Each entry is passed to the `uuu` binary as a `<Protocol>: <Command>` pair.

### Using BCU commands

Devices that support [BCU (Board Control Utility)](https://github.com/NXPmicro/bcu)
can use `bcu` commands using the commands list:

```yaml
- boot:
    method: uuu
    commands:
    - bcu: reset usb
    - uuu: -b emmc {boot}
    - bcu: set_boot_mode emmc
```

Non-exhaustive list of available bcu commands :

```yaml
- reset BOOTMODE_NAME # Reset the board and then boots from mentioned BOOTMODE_NAME.
                      # Replace BOOTMODE_NAME with different options like emmc,sd,
                      # usb which can be obtained from command bcu lsbootmode.
                      # Replace the BOOTMODE_NAME with anyone of the mentioned.
- lsftdi              # List all the boards connected by ftdi device
- lsboard             # List all supported board models
- get_boot_mode       # Displays the boot mode set by BCU
```

!!! note
    The serial availability check and bootloader corruption actions are skipped
    when the first command is `bcu: reset usb`, or when the `commands` block
    contains `bcu` commands only. This behavior is useful to recover bricked
    devices or to use `bcu` as a standalone action.

## docker

UUU can run inside a Docker container. The `docker` block specifies the
container image, which must contain the `uuu` binary.

```yaml
- boot:
    method: uuu
    docker:
      image: atline/uuu:1.5.239
    commands:
    - uuu: -b sd {boot}
```

!!! note
    A docker image specified in the job definition overrides the
    `uuu_docker_image` value from the device configuration.

### image

The Docker image name.

### local

Optional. If `true`, LAVA will use the image if it already exists locally on
the worker without pulling from a registry.

## skip_uuu_if_bootloader_valid

When set to `true`, LAVA checks whether the device already has a valid
bootloader by attempting to boot to U-Boot. If the bootloader is valid, the
entire UUU flash sequence is skipped. This is useful for jobs that only need to
flash when the bootloader is missing or corrupted.

```yaml
- boot:
    method: uuu
    skip_uuu_if_bootloader_valid: true
    commands:
    - bcu: set_boot_mode emmc_s
    timeout:
      minutes: 2
```
