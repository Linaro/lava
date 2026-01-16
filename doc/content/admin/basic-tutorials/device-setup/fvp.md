# FVP

The FVP device type in LAVA refers to running
[Fixed Virtual Platforms](https://developer.arm.com/tools-and-software/simulation-models/fixed-virtual-platforms).

## LAVA FVP worker setup

LAVA executes FVP devices inside Docker containers. Therefore, like any other
LAVA worker that can run `docker` device types, Docker needs to be
installed.

## Creating device type

[Create the device type](common.md#create-device-type) using the name **`fvp`**.

## Creating device

1. [Add the device](common.md#add-device) using the following settings:
    * **Device Type:** `fvp`
    * **Hostname:** A unique name (e.g., `fvp-01`)
2. [Add the device configuration](common.md#add-device-configuration).

    For a minimal configuration, simply extend the base template:

    ```jinja
    {% extends "fvp.jinja2" %}
    ```

## FVP Docker images

LAVA does not handle the download of FVP binaries. These are assumed to be in
the Docker image defined in the LAVA job.

You can use Docker images published by the
[shrinkwraptool](https://gitlab.arm.com/tooling/shrinkwrap) project. The image
`docker.io/shrinkwraptool/base-slim:2025.12.0` is known to work with LAVA.

## Building FVP Docker images

Here is a sample Dockerfile for building your own Docker images for running
FVPs in LAVA.

```shell
FROM ubuntu:22.04

# Install telnet package
RUN apt-get update && \
    apt-get install --no-install-recommends --yes bc libatomic1 telnet libdbus-1-3 && \
    rm -rf /var/cache/apt

# Add FVP Binaries
RUN mkdir /opt/fvp
ADD Foundation_Platform_11.30_27_Linux64.tgz /opt/fvp
```

This example is for the free Foundation model. Download this by going to
[FVP Downloads](https://developer.arm.com/Tools%20and%20Software/Fixed%20Virtual%20Platforms/Arm%20Architecture%20FVPs)
and downloading the `Foundation_Platform_*_Linux64.tgz` archive. Put the
Dockerfile and the archive in the same directory, then build the image from
there:

```shell
docker build -t fvp_foundation_platform:11.30 .
```

Run the following command to test the image. Adjust the versions and binary
paths as needed. You should see `Hello, 64-bit world!` printed.

```shell
docker run --rm \
  fvp_foundation_platform:11.30 \
  /opt/fvp/Foundation_Platformpkg/models/Linux64_GCC-9.3/Foundation_Platform \
  --image /opt/fvp/Foundation_Platformpkg/examples/hello.axf
```

## Networking inside models

Optionally, if you require networking in the model, here is a way to enable
this.

* Create the `network` file with the following contents:

    ```bash
    #!/bin/bash

    # If the change occurs to the "default" libvirt managed network
    if [ "${1}" = "default" ] ; then
      # If the network is started
      if [ "${2}" = "started" ] ; then
        ip tuntap add mode tap tap01
        ip link set tap01 promisc on
        ip link set tap01 up
        ip link set tap01 master virbr0
      fi
    fi
    ```

* Create the `entrypoint.sh` file with the following contents:

    ```bash
    #!/bin/bash

    set -ex

    /usr/sbin/libvirtd &
    sleep 3

    exec "$@"
    ```

    Use this `Dockerfile` instead for installing the additional packages and
    adding the scripts:

    ```dockerfile
    FROM ubuntu:22.04

    # Install packages
    RUN apt-get update && \
        apt-get install --no-install-recommends --yes bc libatomic1 telnet libdbus-1-3 \
        libvirt-daemon-system iproute2 dnsmasq&& \
        rm -rf /var/cache/apt

    # Add FVP Binaries
    RUN mkdir /opt/fvp
    ADD Foundation_Platform_11.30_27_Linux64.tgz /opt/fvp

    COPY network /etc/libvirt/hooks/network
    RUN chmod +x /etc/libvirt/hooks/network

    COPY entrypoint.sh /usr/local/bin/entrypoint.sh
    RUN chmod +x /usr/local/bin/entrypoint.sh

    ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
    ```

* Configure your FVP device type to run with privileged mode for creating the
  interfaces.

    ```jinja
    {% extends "fvp.jinja2" %}

    {% set fvp_docker_privileged = True %}
    ```

    !!! warning
        Access to devices running with privileged mode should be strictly
        controlled via user groups to mitigate security concerns.

* In your LAVA job, add the following arguments to your foundation model
(other models will differ):

    ```yaml
    arguments:
    - ...
    - "--network=bridged"
    - "--network-bridge=tap01"
    ```

This will be required if you require the use of `transfer_overlay`. This could
be useful in the event you want to pass binaries to the model that contains the
filesystem but stored in a way LAVA cannot currently put the overlay into.

```yaml
transfer_overlay:
  # It may be required to suppress some kernel messages
  download_command: echo 3 > /proc/sys/kernel/printk ; wget
  unpack_command: tar -C / -xzf
```

## Sample job definition

```yaml
device_type: fvp
job_name: sample fvp job

timeouts:
  job:
    minutes: 60

priority: medium
visibility: public

actions:
- deploy:
    to: fvp
    timeout:
      minutes: 15
    uniquify: false
    images:
      startup:
        # Create the 'startup.nsh' file with the below content, host it locally
        # or on a http file server, and then update the url below.
        # Image dtb=fvp-base-revc.dtb systemd.log_level=warning console=ttyAMA0 earlycon=pl011,0x1c090000 root=/dev/vda ip=dhcp
        url: file:///<path>/startup.nsh
      uefi:
        url: https://storage.tuxboot.com/buildroot/fvp-aemva/FVP_AARCH64_EFI.fd
      bl1:
        url: https://storage.tuxboot.com/buildroot/fvp-aemva/bl1.bin
      fip:
        url: https://storage.tuxboot.com/buildroot/fvp-aemva/fip.bin
      dtb:
        url: https://storage.tuxboot.com/buildroot/fvp-aemva/fvp-base-revc.dtb
      kernel:
        url: https://storage.tuxboot.com/buildroot/fvp-aemva/Image
      rootfs:
        url:
          https://storage.tuxboot.com/buildroot/fvp-aemva/rootfs.ext4.zst
        compression: zstd
        format: ext4
        overlays:
          lava: true

- boot:
    method: fvp
    docker:
      name: docker.io/shrinkwraptool/base-slim:2025.12.0
      local: true
    image: /tools/Base_RevC_AEMvA_pkg/models/Linux64_GCC-9.3/FVP_Base_RevC-2xAEMvA
    version_string: Fast Models [^\n]+
    timeout:
      minutes: 10
    console_string: 'terminal_0: Listening for serial connection on port (?P<PORT>\d+)'
    feedbacks:
    - '(?P<NAME>terminal_1): Listening for serial connection on port (?P<PORT>\d+)'
    - '(?P<NAME>terminal_2): Listening for serial connection on port (?P<PORT>\d+)'
    - '(?P<NAME>terminal_3): Listening for serial connection on port (?P<PORT>\d+)'
    arguments:
    - --stat
    - -C bp.dram_size=4
    - -C bp.flashloader0.fname='{FIP}'
    - -C bp.flashloader1.fname='{UEFI}'
    - -C bp.hostbridge.userNetPorts=8022=22
    - -C bp.hostbridge.userNetworking=1
    - -C bp.refcounter.non_arch_start_at_default=1
    - -C bp.secure_memory=1
    - -C bp.secureflashloader.fname='{BL1}'
    - -C bp.smsc_91c111.enabled=1
    - -C bp.terminal_0.mode=telnet
    - -C bp.terminal_0.start_telnet=0
    - -C bp.terminal_1.mode=raw
    - -C bp.terminal_1.start_telnet=0
    - -C bp.terminal_2.mode=raw
    - -C bp.terminal_2.start_telnet=0
    - -C bp.terminal_3.mode=raw
    - -C bp.terminal_3.start_telnet=0
    - -C bp.ve_sysregs.exit_on_shutdown=1
    - -C bp.virtio_rng.enabled=1
    - -C bp.virtioblockdevice.image_path='{ROOTFS}'
    - -C bp.virtiop9device.root_path=
    - -C bp.vis.disable_visualisation=1
    - -C cache_state_modelled=0
    - -C cluster0.NUM_CORES=4
    - -C cluster0.PA_SIZE=48
    - -C cluster0.check_memory_attributes=0
    - -C cluster0.clear_reg_top_eret=2
    - -C cluster0.cpu0.semihosting-cwd={ARTIFACT_DIR}
    - -C cluster0.ecv_support_level=2
    - -C cluster0.enhanced_pac2_level=3
    - -C cluster0.gicv3.cpuintf-mmap-access-level=2
    - -C cluster0.gicv3.without-DS-support=1
    - -C cluster0.gicv4.mask-virtual-interrupt=1
    - -C cluster0.has_16k_granule=1
    - -C cluster0.has_amu=1
    - -C cluster0.has_arm_v8-1=1
    - -C cluster0.has_arm_v8-2=1
    - -C cluster0.has_arm_v8-3=1
    - -C cluster0.has_arm_v8-4=1
    - -C cluster0.has_arm_v8-5=1
    - -C cluster0.has_arm_v8-6=1
    - -C cluster0.has_arm_v8-7=1
    - -C cluster0.has_arm_v8-8=1
    - -C cluster0.has_arm_v8-9=1
    - -C cluster0.has_arm_v9-0=1
    - -C cluster0.has_arm_v9-1=1
    - -C cluster0.has_arm_v9-2=1
    - -C cluster0.has_arm_v9-3=1
    - -C cluster0.has_arm_v9-4=1
    - -C cluster0.has_arm_v9-5=1
    - -C cluster0.has_branch_target_exception=1
    - -C cluster0.has_brbe=1
    - -C cluster0.has_brbe_v1p1=1
    - -C cluster0.has_const_pac=1
    - -C cluster0.has_gcs=1
    - -C cluster0.has_hpmn0=1
    - -C cluster0.has_large_system_ext=1
    - -C cluster0.has_large_va=1
    - -C cluster0.has_permission_indirection_s1=1
    - -C cluster0.has_permission_indirection_s2=1
    - -C cluster0.has_permission_overlay_s1=1
    - -C cluster0.has_permission_overlay_s2=1
    - -C cluster0.has_rndr=1
    - -C cluster0.has_sve=1
    - -C cluster0.max_32bit_el=0
    - -C cluster0.pmb_idr_external_abort=1
    - -C cluster0.stage12_tlb_size=1024
    - -C cluster0.sve.has_sme2=1
    - -C cluster0.sve.has_sme=1
    - -C cluster0.sve.has_sve2=1
    - -C cluster1.NUM_CORES=4
    - -C cluster1.PA_SIZE=48
    - -C cluster1.check_memory_attributes=0
    - -C cluster1.clear_reg_top_eret=2
    - -C cluster1.ecv_support_level=2
    - -C cluster1.enhanced_pac2_level=3
    - -C cluster1.gicv3.cpuintf-mmap-access-level=2
    - -C cluster1.gicv3.without-DS-support=1
    - -C cluster1.gicv4.mask-virtual-interrupt=1
    - -C cluster1.has_16k_granule=1
    - -C cluster1.has_amu=1
    - -C cluster1.has_arm_v8-1=1
    - -C cluster1.has_arm_v8-2=1
    - -C cluster1.has_arm_v8-3=1
    - -C cluster1.has_arm_v8-4=1
    - -C cluster1.has_arm_v8-5=1
    - -C cluster1.has_arm_v8-6=1
    - -C cluster1.has_arm_v8-7=1
    - -C cluster1.has_arm_v8-8=1
    - -C cluster1.has_arm_v8-9=1
    - -C cluster1.has_arm_v9-0=1
    - -C cluster1.has_arm_v9-1=1
    - -C cluster1.has_arm_v9-2=1
    - -C cluster1.has_arm_v9-3=1
    - -C cluster1.has_arm_v9-4=1
    - -C cluster1.has_arm_v9-5=1
    - -C cluster1.has_branch_target_exception=1
    - -C cluster1.has_brbe=1
    - -C cluster1.has_brbe_v1p1=1
    - -C cluster1.has_const_pac=1
    - -C cluster1.has_gcs=1
    - -C cluster1.has_hpmn0=1
    - -C cluster1.has_large_system_ext=1
    - -C cluster1.has_large_va=1
    - -C cluster1.has_permission_indirection_s1=1
    - -C cluster1.has_permission_indirection_s2=1
    - -C cluster1.has_permission_overlay_s1=1
    - -C cluster1.has_permission_overlay_s2=1
    - -C cluster1.has_rndr=1
    - -C cluster1.has_sve=1
    - -C cluster1.max_32bit_el=0
    - -C cluster1.pmb_idr_external_abort=1
    - -C cluster1.stage12_tlb_size=1024
    - -C cluster1.sve.has_sme2=1
    - -C cluster1.sve.has_sme=1
    - -C cluster1.sve.has_sve2=1
    - -C gic_distributor.has_nmi=1
    - -C pci.pci_smmuv3.mmu.SMMU_AIDR=2
    - -C pci.pci_smmuv3.mmu.SMMU_IDR0=135263935
    - -C pci.pci_smmuv3.mmu.SMMU_IDR1=216481056
    - -C pci.pci_smmuv3.mmu.SMMU_IDR3=5908
    - -C pci.pci_smmuv3.mmu.SMMU_IDR5=4294902901
    - -C pci.pci_smmuv3.mmu.SMMU_S_IDR1=2684354562
    - -C pci.pci_smmuv3.mmu.SMMU_S_IDR2=0
    - -C pci.pci_smmuv3.mmu.SMMU_S_IDR3=0
    - -C pctl.startup=0.0.0.0
    auto_login:
      login_prompt: 'login:'
      username: root
    prompts:
    - root@(.*):[/~]#

- test:
    timeout:
      minutes: 10
    definitions:
    - from: inline
      repository:
        metadata:
          format: Lava-Test Test Definition 1.0
          name: health checks
        run:
          steps:
          - lava-test-case kernel-info --shell uname -a
          - lava-test-case network-info --shell ip a
      name: health-checks
      path: inline/health-checks.yaml
```
