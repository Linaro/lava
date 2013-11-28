.. _deploy_bootloader:

Deploying a Bootloader Device
=============================

Adding a Bootloader device allows the LAVA user to directly control the 
bootloader on the target, and provide the desired boot sequence. This page 
outlines the steps required to add a new Bootloader device to your LAVA 
deployment and make it able to accept job requests.

Overview
--------

The Bootloader device extends master image type devices to allow backwards 
compatiblity. In the example below, an Arndale target will be used as an 
example to show how you can tftp boot a target.

Installing a tftp server on each dispatcher
-------------------------------------------

Any tftp server will work, if configured correctly. Use this as a guideline.

Install tftpd-hpa package on the dispatcher(s)::

    # apt-get install tftpd-hpa

Install openbsd-inetd package on the dispatcher(s)::

    # apt-get install openbsd-inetd

Configuring the tftp server on each dispatcher
----------------------------------------------

Configure each TFTP server to serve from the dispatcher's download directory::

    # /etc/default/tftpd-hpa

    TFTP_USERNAME="tftp"
    TFTP_DIRECTORY="/srv/lava/instances/<LAVA_INSTANCE>/var/www/lava-server/"
    TFTP_ADDRESS="0.0.0.0:69"
    TFTP_OPTIONS="--secure"

Reload the TFTP server::

    # stop tftpd-hpa
    # start tftpd-hpa

Configure the dispatcher for tftp booting
-----------------------------------------

Deployment schema:

This schema describes the options for deploy_linaro_kernel. It is important 
to notice that only manditory property is "kernel."::

    parameters_schema = {
        'type': 'object',
        'properties': {
            'kernel': {'type': 'string', 'optional': False},
            'ramdisk': {'type': 'string', 'optional': True},
            'dtb': {'type': 'string', 'optional': True},
            'rootfs': {'type': 'string', 'optional': True},
            'rootfstype': {'type': 'string', 'optional': True},
            'bootloader': {'type': 'string', 'optional': True, 'default': 'u_boot'},
            },
        'additionalProperties': False,
        }

Device configuration example::

    # /srv/lava/instances/<LAVA_INSTANCE>/etc/lava-dispatcher/devices/arndale01.conf

    device_type = arndale
    hostname = arndale01
    hard_reset_command = /usr/local/lab-scripts/pdu1.sh 192.168.1.11 3
    power_off_cmd = /usr/local/lab-scripts/pdu1.sh 192.168.1.11 3 0
    power_on_cmd = /usr/local/lab-scripts/pdu1.sh 192.168.1.11 3 1
    soft_boot_cmd = reboot
    bootloader_prompt = ARNDALE5250
    interrupt_boot_command = autoboot
    interrupt_boot_prompt = autoboot
    connection_command = telnet localhost 2000

    boot_cmds_tftp =
        setenv autoload no,
        setenv usbethaddr 00:40:5c:26:0a:5b,
        setenv pxefile_addr_r "'0x50000000'",
        setenv kernel_addr_r "'0x40007000'",
        setenv initrd_addr_r "'0x42000000'",
        setenv fdt_addr_r "'0x41f00000'",
        setenv loadkernel "'tftp ${kernel_addr_r} ${lava_kernel}'",
        setenv loadinitrd "'tftp ${initrd_addr_r} ${lava_ramdisk}; setenv initrd_size ${filesize}'",
        setenv loadfdt "'tftp ${fdt_addr_r} ${lava_dtb}'",
        setenv bootargs "'root=/dev/ram0 console=ttySAC2,115200n8 init --no-log ip=:::::eth0:dhcp'",
        setenv bootcmd "'usb start; dhcp; setenv serverip ${lava_server_ip}; run loadkernel; run loadinitrd; run loadfdt; bootm ${kernel_addr_r} ${initrd_addr_r} ${fdt_addr_r}'",
        boot

    boot_cmds = mmc rescan,
        mmc part 0,
        setenv bootcmd "'fatload mmc 0:5 0x40007000 uImage; fatload mmc 0:5 0x42000000 uInitrd; fatload mmc 0:5 0x41f00000 board.dtb; bootm 0x40007000 0x42000000 0x41f00000'",
        setenv bootargs "'console=ttySAC2,115200n8  root=LABEL=testrootfs rootwait ro'",
        boot

    boot_options =
        boot_cmds

    [boot_cmds] 
    default = boot_cmds

Required configuration parameters::

    # boot_cmds_tftp - These are the boot commands to TFTP boot the device.
    # connection_command - This is the serial connection command.
    # bootloader_prompt - This is the bootloader prompt string.
    # hard_reset_command - This command will power cycle the device.
    # power_off_cmd - This command will turn off power to the device.

Job example:

Below shows how to netboot an Arndale device, by supplying a kernel, ramdisk, 
and dtb to the LAVA server::

    # /tmp/boot-cmds-tftp-kernel.json

    {
      "device_type": "arndale",
      "actions": [
        {
          "command": "deploy_linaro_kernel",
          "parameters": {
            "kernel": "file:///path/to/my/zImage",
            "ramdisk": "file:///path/to/my/uInitrd",
            "dtb": "file:///path/to/my/exynos5250-arndale.dtb"
          }
        },
        {
          "command": "boot_linaro_image"
        }
      ],
      "timeout": 18000,
      "job_name": "boot-cmds-tftp-kernel"
    }

When this job runs, the LAVA dispatcher will download the kernel, ramdisk, dtb 
to it's download directory. It will then set the bootloader enviroment 
variables on the user's behalf so that they can be referenced in 
boot_cmds_tftp and served to the target over TFTP.

    ARNDALE5250 # lava_server_ip=192.168.1.7
    ARNDALE5250 # lava_kernel=images/tmpZXJ0J1/.uImage
    ARNDALE5250 # lava_ramdisk=images/tmpZXJ0J1/.uInitrd
    ARNDALE5250 # lava_dtb=images/tmpZXJ0J1/exynos5250-arndale.dtb

To test, you can execute the dispatcher directly with the following
commands as ``root``:

::

    . /srv/lava/instances/<INST>/bin/activate
    lava-dispatch /tmp/boot-cmds-tftp-kernel.json.json

Submitting a Bootloader Job
---------------------------

The scheduler documentation includes instructions for :ref:`job_submission` to
LAVA. You can use the job file shown above as the basis for your new job.
