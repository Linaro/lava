# Secondary media (USB / SATA / SD)

The `usb / sata / sd` deployment methods can be used to deploy an image to a
secondary media device on the DUT. The three methods use the same deployment
strategy. The only difference is which media is configured in the
[device dictionary](../../../configuration/device-dictionary.md#secondary-media)
and referenced in the job definition.

The DUT is first booted into a primary OS from a primary media device that contains
a pre-installed OS, or via netboot (for example, U-Boot ramdisk or NFS). Once the
primary OS is running, LAVA invokes `download` and `writer` tools on the DUT to
fetch the image that already downloaded to the LAVA worker and write it to the
secondary media device.

This guide describes how to write an image to a secondary media device using the
default `dd` tool and the custom `bmaptool` tool. Other download and writer tools
can be used similarly.

## dd

```yaml
- deploy:
    to: sd
    image:
      url: http://example.com/rootfs.img.gz
      compression: gz
      root_partition: 1
    device: sdcard
    download:
      tool: /usr/bin/wget
      options: --no-check-certificate --no-proxy --connect-timeout=30 -S --progress=dot:giga -O - {DOWNLOAD_URL}
      prompt: HTTP request sent, awaiting response
    timeout:
      minutes: 15
```

See also [SD device configuration](../../../configuration/device-dictionary.md#sd).

### image

A single disk image. Mutually exclusive with [`images`](#images).

#### url

See [url](./index.md#url).

#### compression

See [compression](./index.md#compression).

If the image is compressed and the writing tool doesn't support using a compressed
file, the compression method must be specified.

#### root_partition

When tests defined in the job definition, the `root_partition` index (0-based) of
the image must be specified for applying the LAVA overlay that contains the tests
and LAVA helpers.

### device

Required. The name of the secondary media device configured using the
[`<media>_label`](../../../configuration/device-dictionary.md#secondary-media) in
the device dictionary.

### download

Specifies how to download and pipe the image to the writing tool for flashing the
secondary device.

#### tool

Required. Absolute path to the download tool on the primary OS.

The tool must be pre-installed:

```shell title="Debian"
sudo apt install wget
```

#### options

Required. Options for the download tool.

LAVA substitutes the placeholder `{DOWNLOAD_URL}` with the HTTP URL served by
the LAVA worker for the downloaded (and decompressed if specified) image file.
For example:

```plain
http://198.18.0.1/tmp/529/storage-deploy-23634l0i/image/ubuntu-24.04.4-preinstalled-server-arm64+raspi.img
```

#### prompt

Required. A string that appears in the tool's output when the download starts. LAVA
waits for this string first before waiting for write completion prompts.

### writer

If not defined, `dd` is used for the flashing by default. The full pipeline sent
to the primary OS shell is:

```shell
/usr/bin/wget <options> | dd of='/dev/disk/by-id/<media>_uuid' bs=4M
```

For example:

```shell
/usr/bin/wget --no-check-certificate --no-proxy --connect-timeout=30 \
  -S --progress=dot:giga \
  -O - http://198.18.0.1/tmp/529/storage-deploy-23634l0i/image/ubuntu-24.04.4-preinstalled-server-arm64+raspi.img \
  | dd of='/dev/disk/by-id/mmc-SE16G_0x5005f804' bs=4M
```

### tool

Optional. Overrides the prompts LAVA uses to detect write completion.

#### prompts

If omitted, LAVA uses the default `DD_PROMPTS`:

```yaml
- "[0-9]+\+[0-9]+ records out"
- "[0-9]+ bytes \(.*\) copied"
```

## bmaptool

```yaml
- deploy:
    to: usb
    images:
      image:
        url: https://example.com/raspberrypi4-64/oniro-image-base-tests-raspberrypi4-64.rootfs.wic.gz
      bmap:
        url: https://example.com/raspberrypi4-64/oniro-image-base-tests-raspberrypi4-64.rootfs.wic.bmap
    uniquify: false
    device: SanDiskCruzerBlade
    writer:
      tool: /usr/bin/bmaptool
      options: copy {DOWNLOAD_URL} {DEVICE}
      prompt: 'bmaptool: info'
    tool:
      prompts: ['bmaptool: info: copying time: [0-9hms\.\ ]+, copying speed [0-9\.]+ [MKiBbytes]+\/sec']
    timeout:
      minutes: 30
```

See also [USB device configuration](../../../configuration/device-dictionary.md#usb).

### images

A dictionary of named files. Mutually exclusive with [`image`](#image). Must
contain the `image` key. Any additional keys (e.g. `bmap`) are downloaded as
companion files.

### uniquify

Optional boolean. By default, LAVA stores each downloaded image in a separate
subdirectory named after the image key to avoid filename collisions.

For this case, it must be set to `false` so that `bmaptool` can locate the
corresponding `bmap` file to accelerate the flashing. The `bmap` file must
share the same base name and reside in the same directory as the `image`.

### device

See [device](#device).

### writer

Specifies the image writing tool.

#### tool

Required. Absolute path to the writer tool on the primary OS.

The tools must be pre-installed:

```shell title="Debian"
sudo apt install bmap-tools
```

#### options

Required. Options for the writer tool.

Placeholders:

- `{DOWNLOAD_URL}` — See [options](#options). Additionally, the `bmaptool` fetches
  the `image` and the corresponding `bmap` files directly from the LAVA worker
  over HTTP. This means download tool is not needed in this case.
- `{DEVICE}` — LAVA substitutes the placeholder with the resolved block device
  path on the primary OS, e.g.
  `/dev/disk/by-id/usb-SanDisk_Cruzer_Blade_20060266531DA442AD42-0:0`. The
  `usb-SanDisk_Cruzer_Blade_20060266531DA442AD42-0:0` is configured using
  `usb_uuid` parameter in the device dictionary.

#### prompt

Required. The string that appears in the tool's output when the write operation
start. LAVA waits for this string before waiting for write completion prompts.

### tool

Optional. Overrides the prompts LAVA uses to detect write completion.

#### prompts

Overwrites the default [`DD_PROMPTS`](#prompts)

#### LAVA overlay

When using `bmaptool` to flash an image with a corresponding `bmap` file, the
LAVA overlay should be transferred after the secondary device flashing and boot
since the image shouldn't be modified before flashing.

```yaml
- boot:
    method: minimal
    auto_login:
      login_prompt: 'login:'
      username: root
    prompts:
      - 'root@device:~#'
    transfer_overlay:
      download_command: wget
      unpack_command: tar -C / -xzf
    timeout:
      minutes: 5
```

See also [transfer overlay](../boot/common.md#transfer_overlay).

## Sample job

```yaml
job_name: RPi4b secondary media deployment sample job
device_type: bcm2711-rpi-4-b

visibility: public
priority: medium

timeouts:
  job:
    minutes: 15
  connection:
    minutes: 2

actions:
# Attach USB mass storage gadget.
- deploy:
    to: usbg-ms
    image:
      url: https://raspi.debian.net/tested/20231109_raspi_4_bookworm.img.xz
      compression: xz
    timeout:
      minutes: 5

# Boot primary OS - Debian.
- boot:
    method: minimal
    auto_login:
      login_prompt: 'login:'
      username: root
    prompts:
    - 'root@rpi4-20231108:'
    timeout:
      minutes: 5

# 'wget | dd' Ubuntu image to secondary media SD Card
- deploy:
    timeout:
      minutes: 15
    to: sd
    image:
      url: https://cdimage.ubuntu.com/releases/24.04.4/release/ubuntu-24.04.4-preinstalled-server-arm64+raspi.img.xz
      compression: xz
      root_partition: 1
    device: sdcard
    download:
      tool: /usr/bin/wget
      options: --no-check-certificate --no-proxy --connect-timeout=30 -S --progress=dot:giga -O - {DOWNLOAD_URL}
      prompt: HTTP request sent, awaiting response

# Detach USB mass storage gadget.
- command:
    name: usbg_ms_commands_disable

# Boot Ubuntu from SD Card.
- boot:
    method: minimal
    auto_login:
      login_prompt: 'login:'
      username: 'ubuntu'
      password_prompt: 'Password:'
      password: 'ubuntu'
      login_commands:
      - ubuntu
      - linaro123
      - linaro123
      - sudo su
    prompts:
    - 'Current password:'
    - 'New password:'
    - 'Retype new password:'
    - 'ubuntu@ubuntu:'
    - 'root@ubuntu:'
    timeout:
      minutes: 5

# Run tests to check kernel version and OS ID.
- test:
    definitions:
    - from: inline
      repository:
        metadata:
          format: Lava-Test Test Definition 1.0
          name: test-definition-example
        run:
          steps:
          - lava-test-case run-uname-a --shell uname -a
          - lava-test-case check-os-id --shell 'cat /etc/os-release | grep "ID=ubuntu"'
      path: inline/test-definition-example.yaml
      name: test-suite-example
    timeout:
      minutes: 5
```

This job example utilizes the
[USB mass storage gadget](https://docs.lavacloud.io/hardware/peripherals.html#laa-usb)
feature of the LAA as the primary boot media to launch Debian. Once Debian is running,
it is used to flash the Ubuntu image onto the SD card. The pipeline can be useful
for testing if a disk image boots correctly from the SD card.

See also:

- [Prioritize RPi USB boot over SD](https://docs.lavacloud.io/devices/rpi-3-and-4.html#setup-a-simple-recovery-mechanism)
- [usbg-ms deployment method](./to-usg-ms.md)

--8<-- "refs.txt"
