# Bootloader Testing

## Interactive bootloader tests

LAVA supports testing bootloaders such as U-Boot by interacting directly with
the bootloader prompt over the device serial console.

This example job boots a Raspberry Pi 4B to the U-Boot prompt and runs
[interactive](../../technical-references/job-definition/actions/test.md#interactive)
U-Boot tests directly.

```yaml
job_name: Interactive U-Boot test
device_type: bcm2711-rpi-4-b

priority: medium
visibility: public

timeouts:
  job:
    minutes: 20
  action:
    minutes: 5
  connection:
    minutes: 2

context:
  extra_kernel_args: console_msg_format=syslog earlycon
  console_device: ttyS1

secrets:
  GITLAB_TOKEN: gitlab-private-code

actions:
- deploy:
    to: downloads
    failure_retry: 3
    images:
      gitlab_files:
        url: https://gitlab.com/api/v4/projects/58465263/jobs/9656175138/artifacts/files_from_gl.tar.xz
        compression: xz
        archive: tar
        headers:
          PRIVATE-TOKEN: gitlab-private
    timeout:
      minutes: 5

- deploy:
    to: usbg-ms
    image:
      url: https://gitlab.com/api/v4/projects/58465263/jobs/9656175138/artifacts/disk.img.gz
      compression: gz
      headers:
        PRIVATE-TOKEN: gitlab-private
    timeout:
      minutes: 5

- boot:
    method: bootloader
    bootloader: u-boot
    commands: []
    prompts:
    - 'U-Boot> '
    timeout:
      minutes: 5

- test:
    timeout:
      minutes: 5
    interactive:
    - name: basic-cmds
      prompts: ["U-Boot> ", "=> ", "/ # "]
      script:
      - command: echo "u-boot echo test"
        name: echo
        successes:
        - message: "u-boot echo test"
      - command: version
        name: version
        successes:
        - message: "U-Boot "
      - command: help test
        name: help
        successes:
        - message: "test - minimal test like /bin/sh"
      - command: setenv test_var test123printenv
      - command: printenv
        name: setenv-and-printenv
        successes:
        - message: "test_var=test123"
    - name: memory-test
      prompts: ["U-Boot> ", "=> ", "/ # "]
      script:
      - command: base
        name: print-default-base-address-offset
        successes:
        - message: "Base Address: 0x"
      - command: base 40000000
        name: set-address-offset-0x40000000
        successes:
        - message: "Base Address: 0x40000000"
      - command: base
        name: check-address-offset-0x40000000
        successes:
        - message: "Base Address: 0x40000000"
      - command: mw.b 40000000 aa 400
      - command: crc 40000000 400
        name: compute-CRC32-checksum
        successes:
        - message: "CRC32 for 40000000 ... 400003ff ==> efb5af2e"
      - command: mw 100000 aabbccdd 10
      - command: md 100000 10
        name: mw-md-100000
        successes:
        - message: "aabbccdd"
      - command: cp 100000 200000 10
      - command: md 200000 10
        name: cp-md-200000
        successes:
        - message: "aabbccdd"
      - command: cmp 100000 200000 10
        name: cmp-100000-200000-10
        successes:
        - message: 'Total of 16 word\(s\) were the same'
    - name: network
      prompts: ["U-Boot> ", "=> ", "/ # "]
      script:
      - command: dhcp
        name: dhcp
        successes:
        - message: "DHCP client bound to address"
        failures:
        - message: "TIMEOUT"
          exception: InfrastructureError
          error: "dhcp failed"
    - name: tftp-cmds
      prompts: ["U-Boot> ", "=> ", "/ # "]
      script:
      - command: setenv serverip {SERVER_IP} ; tftp 0x1000000 {JOB_ID}/downloads/common/gitlab_files/helloworld.efi
        name: tftp
        successes:
        - message: "Bytes transferred ="
```

## Running bootloader test suite

LAVA allows test scripts running from a
[docker test shell](../../user/advanced-tutorials/running-arbitrary-code-with-docker.md)
to connect to and control the DUT. This enables running existing bootloader test
suites unmodified inside an isolated container.

The following example job deploys firmware images and then runs the U-Boot test
suite inside a Docker container. LAVA exposes the DUT’s power control and serial
connection commands to the container, enabling the test framework to power-cycle
the board and interact directly with the bootloader.

```yaml
job_name: Running U-Boot test suite
device_type: kv260

visibility: public
priority: high

timeouts:
  job:
    minutes: 60
  connection:
    minutes: 2
  actions:
    finalize:
      seconds: 60

context:
  lava_test_results_dir: /var/lib/lava-%s

actions:
- deploy:
    to: downloads
    images:
      firmware:
        url: https://linaro.gitlab.io/trustedsubstrate/meta-ts//ImageA.bin.xz
        compression: xz
      os:
        url: https://gitlab.com/Linaro/trustedsubstrate/ts-testing/-/jobs/artifacts/main/raw/image/efiboot.wic.xz?job=build
        compression: xz
      tested_os:
        url: https://linaro.gitlab.io/trustedsubstrate/gpit/gpit-genericarm64.img.xz
        compression: xz
      capsule:
        url: https://linaro.gitlab.io/trustedsubstrate/meta-ts//zynqmp-kria-starter_fw.capsule
      invalid_sig:
        url: https://linaro.gitlab.io/trustedsubstrate/meta-ts//zynqmp-kria-starter_fw_invalid_sig.capsule
    postprocess:
      docker:
        image: registry.gitlab.com/linaro/trustedsubstrate/dockerfiles/lava-postprocess:arm64-38fee7c
        steps:
        - mkdir -p EFI/BOOT/
        - mcopy -i efiboot.wic@@1048576 ::/EFI/BOOT/startup.nsh EFI/BOOT/
        - mcopy -o -i efiboot.wic@@1048576 zynqmp-kria-starter_fw.capsule ::/EFI/BOOT/valid.capsule
        - mcopy -o -i efiboot.wic@@1048576 zynqmp-kria-starter_fw_invalid_sig.capsule ::/EFI/BOOT/invalid.capsule
        - sed -i "s#ledge.efi -f.*#ledge.efi -f -u ${LAVA_DISPATCHER_IP}/tmp/${LAVA_JOB_ID}/downloads/common/gpit-genericarm64.img#g" EFI/BOOT/startup.nsh
        - cat EFI/BOOT/startup.nsh
        - mcopy -o -i efiboot.wic@@1048576 EFI/BOOT/startup.nsh ::/EFI/BOOT/
        - fdisk -l efiboot.wic
        - fdisk -l ImageA.bin
    timeout:
      minutes: 20

- deploy:
    to: flasher
    images:
      ImageA:
        url: downloads://ImageA.bin
      ImageB:
        url: downloads://ImageA.bin
      sd:
        url: downloads://efiboot.wic
    timeout:
      minutes: 60

- boot:
    method: minimal
    prompts:
    - (.*)login:(.*)
    timeout:
      minutes: 5

- test:
    docker:
      image: registry.gitlab.com/linaro/trustedsubstrate/dockerfiles/u-boot-ci:arm64-77bfe23
    timeout:
      minutes: 30
    definitions:
    - from: inline
      path: inline-docker-test
      name: u-boot-ci
      repository:
        metadata:
          format: Lava-Test Test Definition 1.0
          name: inline-repo
          description: "Inline repository test for U-Boot"
        run:
          steps:
          - |
            mkdir src && cd src
            retry --delay=30 --times=3 -- git clone https://source.denx.de/u-boot/u-boot.git
            retry --delay=30 --times=3 -- git clone --depth 1 https://source.denx.de/u-boot/u-boot-test-hooks.git
            cd u-boot
            git checkout "127a42c7257a6ffbbd1575ed1cbaa8f5408a44b3"
            git describe
          - |
            python -m virtualenv /lava-${LAVA_JOB_ID}/0/uboot-venv
            . /lava-${LAVA_JOB_ID}/0/uboot-venv/local/bin/activate
            python -m pip install --root-user-action=ignore --upgrade pip
            python -m pip install --root-user-action=ignore -r ./test/py/requirements.txt
            python -m pip install --root-user-action=ignore -r ./tools/buildman/requirements.txt
          - |
            export KBUILD_OUTPUT=/lava-${LAVA_JOB_ID}/0/build/xilinx_zynqmp_kria
            mkdir -p ${KBUILD_OUTPUT}
            tools/buildman/buildman \
              -o ${KBUILD_OUTPUT} \
              -w -E -W -e -V \
              --boards xilinx_zynqmp_kria || { echo "==== Buildman failed ===="; exit 1; }
          - |
            mkdir ../u-boot-test-hooks/bin/${HOSTNAME}
            mkdir ../u-boot-test-hooks/py/${HOSTNAME}

            echo 'bash -c "${LAVA_POWER_ON_COMMAND}"' > ../u-boot-test-hooks/bin/poweron.laa
            echo 'bash -c "${LAVA_POWER_OFF_COMMAND}"' > ../u-boot-test-hooks/bin/poweroff.laa
            echo 'bash -c "${LAVA_HARD_RESET_COMMAND}"' > ../u-boot-test-hooks/bin/reset.laa

            echo 'exec telnet 172.17.0.1 2001' > ../u-boot-test-hooks/bin/console.laa

            cat > ../u-boot-test-hooks/bin/${HOSTNAME}/conf.xilinx_zynqmp_kria_laa-xilinx_zynqmp_kria << _EOF
            flash_impl=none
            power_impl=laa
            console_impl=laa
            reset_impl=laa
            _EOF

            cat > ../u-boot-test-hooks/py/${HOSTNAME}/u_boot_boardenv_xilinx_zynqmp_kria.py << __EOF
            env__net_dhcp_server = True
            env__spl_skipped = True
            env__dhcp_abort_test_skip = False
            env_spl_banner_times = 0
            env__net_static_env_vars = [
              ("ipaddr", "198.18.0.2"),
              ("netmask", "255.255.255.0"),
              ("serverip", "198.18.0.1"),
              ("tftpserverip", "198.18.0.1"),
            ]
            __EOF
          - |
            U_BOOT_TEST_HOOKS_PATH=/var/lib/lava-${LAVA_JOB_ID}/0/tests/0_u-boot-ci/src/u-boot-test-hooks
            export PATH=${U_BOOT_TEST_HOOKS_PATH}/bin:./tools/buildman:${PATH}
            export PYTHONPATH=${U_BOOT_TEST_HOOKS_PATH}/py/${HOSTNAME}/:${PYTHONPATH}

            ./test/py/test.py --tb=long \
              -s -v -ra \
              --bd xilinx_zynqmp_kria \
              --id laa-xilinx_zynqmp_kria \
              --build-dir ${KBUILD_OUTPUT} \
              --junitxml=results.xml --color=no || { echo "==== U-Boot CI failed ==="; exit 1; }

            xmllint --format results.xml --output formatted_results.xml
            cat formatted_results.xml
```

!!! note
    The inline test definition demonstrates how the `LAVA_*` environment variables
    are used to control and connect to the DUT from LAVA Docker test shell. When
    needed, you can convert these steps into a custom shell script with a result
    parser to store test results in LAVA.
