.. _migrating_known_device_example:

Worked example of migrating a known device
##########################################

This guide makes the following assumptions:

#. You have access to a working LAVA instance with pipeline support.
#. You have at least one working device of a known device type
#. You have at least one working JSON job submission for that device.
#. You are migrating to a deployment type and boot type which is
   already supported by the pipeline code.
#. You have read access to the current configuration of that device,
   including PDU port numbers and serial port access.

Things will go more easily if you also have:

#. admin access to the django configuration of the LAVA instance
#. root command line access to the dispatcher currently using the device.
#. a browser tab open at the `Online YAML parser <http://yaml-online-parser.appspot.com/?yaml=>`_

.. note:: some parts of the refactoring are still in development, so
   not all of the support may be available. However, as YAML supports
   comments, this data is not lost.

The objective is to migrate the configuration of the existing device
such that exactly the same commands are sent to the device as in the
current dispatcher jobs, with the benefit of pipeline validation, results
and metadata.

.. _writing_device_config_yaml:

Writing a device configuration in YAML
**************************************

The current dispatcher configuration is in two parts and these will
typically be respected in the migration.

The :term:`device type` configuration will become a device type template.

The device configuration will become a device dictionary.

However, initially, we need a single YAML file which contains the data
that the pipeline will send to the dispatcher - a combination of the
device type and device information. You can see examples of such content
when validating pipeline jobs. (This example has been edited slightly to
take out some of the noise.)::

 $ sudo lava-dispatch --target devices/bbb-01.yaml bbb-uboot-ramdisk.yaml --validate --output-dir=/tmp/test/

.. code-block:: yaml

 device: !!python/object/new:lava_dispatcher.pipeline.device.NewDevice
  dictitems:
    actions:
      boot:
        prompts:
          - 'linaro-test'
          - 'root@debian:~#'
        connections: {serial: null, ssh: null}
        methods:
          u-boot:
            parameters: {boot_message: Booting Linux, bootloader_prompt: U-Boot, send_char: false}
            ramdisk:
              commands: [setenv autoload no, setenv initrd_high '0xffffffff', setenv
                  fdt_high '0xffffffff', 'setenv kernel_addr_r ''{KERNEL_ADDR}''',
                'setenv initrd_addr_r ''{RAMDISK_ADDR}''', 'setenv fdt_addr_r ''{DTB_ADDR}''',
                'setenv loadkernel ''tftp ${kernel_addr_r} {KERNEL}''', 'setenv loadinitrd
                  ''tftp ${initrd_addr_r} {RAMDISK}; setenv initrd_size ${filesize}''',
                'setenv loadfdt ''tftp ${fdt_addr_r} {DTB}''', 'setenv bootargs ''console=ttyO0,115200n8
                  root=/dev/ram0 ip=dhcp''', 'setenv bootcmd ''dhcp; setenv serverip
                  {SERVER_IP}; run loadkernel; run loadinitrd; run loadfdt; {BOOTX}''',
                boot]
      deploy:
        methods:
          tftp: null
          usb: null
    commands: {connect: telnet localhost 6000}
    device_type: beaglebone-black
    hostname: bbb-01
    parameters:
      bootm: {dtb: '0x815f0000', kernel: '0x80200000', ramdisk: '0x81600000'}
      bootz: {dtb: '0x81f00000', kernel: '0x81000000', ramdisk: '0x82000000'}
    power_state: 'off'
    timeouts:
      apply-overlay-image: {seconds: 120}
      lava-test-shell: {seconds: 30}
      power_off: {seconds: 5}
      umount-retry: {seconds: 45}
  state: {target: bbb-01}

This snippet includes the connection command (``telnet localhost 6000``)
from the device configuration and the ramdisk uboot parameters from the
device type configuration - note that as this is the validation output,
no job files have been downloaded, so the substitution placeholders remain,
``{DTB}``, ``{SERVER_IP}``, ``{KERNEL}`` etc. - this is correct and will
help with the next steps. What isn't so helpful at the moment is the
layout of this YAML dump.

.. _migrating_mustang:

Migrating a mustang
===================

Existing configuration::

 device_type = mustang
 hostname = staging-mustang01
 hard_reset_command = /usr/bin/pduclient --daemon services --hostname pdu15 --command reboot --port 05
 power_off_cmd = /usr/bin/pduclient --daemon services --hostname pdu15 --command off --port 05
 connection_command = telnet serial4 7012
 reset_port_command = flock /var/lock/serial1.lock /usr/local/lab-scripts/reset-serial5000 serial4 12
 image_boot_msg_timeout = 240

Start with a new file:

.. code-block:: yaml

 device_type: mustang
 # hostname is irrelevant in the refactoring, the dispatcher uses what it is given.
 commands:
   connect: telnet serial4 7012
   hard_reset: /usr/bin/pduclient --daemon services --hostname pdu15 --command reboot --port 05
   power_off: /usr/bin/pduclient --daemon services --hostname pdu15 --command off --port 05
   power_on: /usr/bin/pduclient --daemon services --hostname pdu15 --command on --port 05
   # power_on is new in the refactoring.
   # reset_port_command not yet ported:
   # reset_port: flock /var/lock/serial1.lock /usr/local/lab-scripts/reset-serial5000 serial4 12
   # timeouts are handled later in the file.

So far, so good. Now add the device type configuration blocks. This is the
existing configuration::

 client_type = bootloader

 bootloader_prompt = Mustang
 send_char = False
 uimage_only = True
 boot_cmd_timeout = 60
 text_offset = 0x80000

 u_load_addrs =
    0x4002000000
    0x4004000000
    0x4003000000

 z_load_addrs =
    0x4002000000
    0x4004000000
    0x4003000000

 boot_cmds_nfs =
    setenv autoload no,
    setenv kernel_addr_r "'{KERNEL_ADDR}'",
    setenv initrd_addr_r "'{RAMDISK_ADDR}'",
    setenv fdt_addr_r "'{DTB_ADDR}'",
    setenv loadkernel "'tftp ${kernel_addr_r} {KERNEL}'",
    setenv loadinitrd "'tftp ${initrd_addr_r} {RAMDISK}'",
    setenv loadfdt "'tftp ${fdt_addr_r} {DTB}'",
    setenv nfsargs "'setenv bootargs root=/dev/nfs rw nfsroot={SERVER_IP}:{NFSROOTFS},tcp,hard,intr panic=1 console=ttyS0,115200 earlyprintk=uart8250-32bit,0x1c020000 debug ip=dhcp'",
    setenv bootcmd "'dhcp; setenv serverip {SERVER_IP}; run loadkernel; run loadinitrd; run loadfdt; run nfsargs; {BOOTX}'",
    boot

 boot_cmds_ramdisk =
    setenv autoload no,
    setenv kernel_addr_r "'{KERNEL_ADDR}'",
    setenv initrd_addr_r "'{RAMDISK_ADDR}'",
    setenv fdt_addr_r "'{DTB_ADDR}'",
    setenv loadkernel "'tftp ${kernel_addr_r} {KERNEL}'",
    setenv loadinitrd "'tftp ${initrd_addr_r} {RAMDISK}'",
    setenv loadfdt "'tftp ${fdt_addr_r} {DTB}'",
    setenv bootargs "'root=/dev/ram0 rw panic=1 console=ttyS0,115200 earlyprintk=uart8250-32bit,0x1c020000 debug ip=dhcp'",
    setenv bootcmd "'dhcp; setenv serverip {SERVER_IP}; run loadkernel; run loadinitrd; run loadfdt; {BOOTX}'",
    boot

 boot_cmds =
    boot

 boot_options =
    boot_cmds

 [boot_cmds]
 default = boot_cmds

Extend the existing YAML file, to add:

#. parameters
#. actions
#. deploy and boot methods
#. method parameters
#. method commands

Parameters
----------

Note how the existing config just lists the addresses without identifying
which is the kernel load addr. Although these blocks are the same in this
example, the addresses can differ between z_load and u_load.::

 u_load_addrs =
    0x4002000000
    0x4004000000
    0x4003000000
 z_load_addrs =
    0x4002000000
    0x4004000000
    0x4003000000

Use a working job log file to identify which is where::

  <LAVA_DISPATCHER>2015-06-19 08:32:29 AM DEBUG: boot_cmds(after preprocessing):
  ['setenv autoload no', u"setenv kernel_addr_r '0x4002000000'",
  u"setenv initrd_addr_r '0x4004000000'",
  u"setenv fdt_addr_r '0x4003000000'",
  u"setenv loadkernel 'tftp ${kernel_addr_r} tmplv_wQe/uImage_1.11'",
  "setenv loadinitrd 'tftp ${initrd_addr_r} {RAMDISK}'",
  u"setenv loadfdt 'tftp ${fdt_addr_r} tmplv_wQe/mustang.dtb_1.11'",
  u"setenv nfsargs 'setenv bootargs root=/dev/nfs rw
  nfsroot=10.3.2.1:/var/lib/lava/dispatcher/tmp/tmplv_wQe/tmprhrAXO,tcp,hard,intr
  panic=1 console=ttyS0,115200 earlyprintk=uart8250-32bit,0x1c020000 debug ip=dhcp'",
  u"setenv bootcmd 'dhcp; setenv serverip 10.3.2.1; run loadkernel;
  run loadinitrd; run loadfdt; run nfsargs; bootm ${kernel_addr_r} - ${fdt_addr_r}'", 'boot']

Note here that the action job uses ``bootm``, so it is ``bootm`` parameters
we need to specify.

.. code-block:: yaml

 parameters:
   bootm:
     kernel: '0x4002000000'
     ramdisk: '0x4004000000'
     dtb: '0x4003000000'

Only add ``bootz`` support if you know that the UBoot ``bootz`` command
is present in the UBoot version on the board and that it works with zImage
kernels. The eventual templates will exist on the server and can be used
to declare the detailed device support so that test writers know in advance
what kind of images the device can use.

.. index:: trailing comma

.. _v1_trailing_commas:

Actions
-------

For this example, the deployment method is relatively simple - you can
see from the working job that it is using ``tftp`` to deploy.

.. code-block:: yaml

 actions:
   deploy:
     methods:
     - tftp

**Always** check your YAML syntax. The YAML parser can provide links to
small snippets of YAML,
`like the one above <http://yaml-online-parser.appspot.com/?yaml=actions%3A%0A++deploy%3A%0A++++methods%3A%0A++++-+tftp%0A&type=json>`_

The boot support is where things become more detailed.

.. code-block:: yaml

    boot:
     prompts:
       - 'linaro-test'
       - 'root@debian:~#'
     methods:
       u-boot:
         parameters:
           bootloader_prompt: Mustang
           boot_message: Starting kernel

The bootloader prompt (at this stage) comes from the device type
configuration. The boot message will later be supportable as image-specific.
For now, you need whatever values work with the current state of the
device. The ``boot_message`` is a string emitted during the boot which
denotes a successful attempt to boot. There is no need to quote the string
unless it contains an illegal character in YAML like a colon.

Next are the commands for the deployment method itself:

.. code-block:: yaml

 nfs:
   commands:
   - setenv autoload no
   - setenv kernel_addr_r '{KERNEL_ADDR}'
   - setenv initrd_addr_r '{RAMDISK_ADDR}'
   - setenv fdt_addr_r '{DTB_ADDR}'
   - setenv loadkernel 'tftp ${kernel_addr_r} {KERNEL}'
   - setenv loadinitrd 'tftp ${initrd_addr_r} {RAMDISK}'
   - setenv loadfdt 'tftp ${fdt_addr_r} {DTB}'
   - "setenv nfsargs 'setenv bootargs root=/dev/nfs rw nfsroot={SERVER_IP}:{NFSROOTFS},tcp,hard,intr panic=1 console=ttyS0,115200 earlyprintk=uart8250-32bit,0x1c020000 debug ip=dhcp'"
   - setenv bootcmd 'dhcp; setenv serverip {SERVER_IP}; run loadkernel; run loadinitrd; run loadfdt; run nfsargs; {BOOTX}'
   - boot

These are retained with only formatting changes - after all, these are
what the device needs to be able to boot.

#. Remove **trailing commas** (remnants of the old config)
#. Remove one level of quote marks **unless** the command embeds a colon
   (e.g. NFS), in which case the **whole line** is quoted.
#. Make each line part of a list by prefixing with a hyphen and a space.

.. note:: Trailing commas are known to cause problems on devices - check
   the config carefully and be particularly watchful for failures where
   the device reports ``cannot find device 'net0,'`` when working V1 jobs
   would report using ``device 'net0'``. Commas are required in V1 but
   YAML processing for V2 will include trailing commas as part of the
   string, not part of the formatting.

Timeouts
--------

A process of trial and error will illuminate which timeouts are
appropriate to set at this level.

.. code-block:: yaml

 timeouts:
   power_off:
     seconds: 5

Complete device YAML
====================

Untested at this point, but this is the start of the integration.

.. code-block:: yaml

 device_type: mustang
 # hostname is irrelevant in the refactoring, the dispatcher uses what it is given.
 commands:
   connect: telnet serial4 7012
   hard_reset: /usr/bin/pduclient --daemon services --hostname pdu15 --command reboot --port 05
   power_off: /usr/bin/pduclient --daemon services --hostname pdu15 --command off --port 05
   power_on: /usr/bin/pduclient --daemon services --hostname pdu15 --command on --port 05
   # power_on is new in the refactoring.
   # reset_port_command not yet ported:
   # reset_port: flock /var/lock/serial1.lock /usr/local/lab-scripts/reset-serial5000 serial4 12
   # timeouts are handled later in the file.
 parameters:
   bootm:
     kernel: '0x4002000000'
     ramdisk: '0x4004000000'
     dtb: '0x4003000000'
 actions:
   deploy:
     methods:
     - tftp
   boot:
     prompts:
       - 'linaro-test'
       - 'root@debian:~#'
     methods:
       u-boot:
         parameters:
           bootloader_prompt: Mustang
           boot_message: Starting kernel
         nfs:
           commands:
           - setenv autoload no
           - setenv kernel_addr_r '{KERNEL_ADDR}'
           - setenv initrd_addr_r '{RAMDISK_ADDR}'
           - setenv fdt_addr_r '{DTB_ADDR}'
           - setenv loadkernel 'tftp ${kernel_addr_r} {KERNEL}'
           - setenv loadinitrd 'tftp ${initrd_addr_r} {RAMDISK}'
           - setenv loadfdt 'tftp ${fdt_addr_r} {DTB}'
           - "setenv nfsargs 'setenv bootargs root=/dev/nfs rw nfsroot={SERVER_IP}:{NFSROOTFS},tcp,hard,intr panic=1 console=ttyS0,115200 earlyprintk=uart8250-32bit,0x1c020000 debug ip=dhcp'"
           - setenv bootcmd 'dhcp; setenv serverip {SERVER_IP}; run loadkernel; run loadinitrd; run loadfdt; run nfsargs; {BOOTX}'
           - boot

 timeouts:
   power_off:
     seconds: 5

.. _writing_job_submission_yaml:

Writing a job submission in YAML
********************************

.. warning:: Do **not** be tempted into writing a script to convert
   the JSON to YAML. You need to understand what the job is doing and
   why. e.g. the original job gives no clue that ``u-boot`` is involved
   nor that the required ``u-boot`` parameters for this job are ``bootm``
   and not ``bootz``. Any such attempts would re-introduce assumptions
   that the refactoring is deliberately removing. Just because a file
   has a particular name or suffix does not mean that the job can make
   any safe assumptions about the content of that file.

Migrating a job for the mustang
===============================

Existing JSON::

 {
    "actions": [
        {
            "command": "deploy_linaro_kernel",
            "metadata": {
                "distribution": "debian"
            },
            "parameters": {
                "dtb": "http://images-internal/mustang/mustang.dtb_1.11",
                "kernel": "http://images-internal/mustang/uImage_1.11",
                "login_prompt": "login:",
                "nfsrootfs": "http://people.linaro.org/~neil.williams/arm64/debian-jessie-arm64-rootfs.tar.gz",
                "target_type": "ubuntu",
                "username": "root"
            }
        },
        {
            "command": "boot_linaro_image"
        },
        {
            "command": "lava_test_shell",
            "parameters": {
                "testdef_repos": [
                    {
                        "git-repo": "http://git.linaro.org/people/neil.williams/temp-functional-tests.git",
                        "testdef": "singlenode/singlenode03.yaml"
                    }
                ],
                "timeout": 900
            }
        },
        {
            "command": "submit_results",
            "parameters": {
                "server": "https://staging.validation.linaro.org/RPC2",
                "stream": "/anonymous/lava-functional-tests/"
            }
        }
    ],
    "device_type": "mustang",
    "job_name": "mustang-singlenode-jessie",
    "timeout": 900
 }

Identifying the elements of the job
-----------------------------------

Forget the ``deploy_linaro_kernel``, this is a deployment of a kernel,
a DTB and an NFS root filesystem.

Start with the top level structures:

.. code-block:: yaml

 device_type: mustang
 job_name: mustang-singlenode-jessie
 timeouts:
   job:
     minutes: 15

``device_type`` isn't stricly necessary at this point but it will become
necessary once this job is able to be submitted via the server rather than
directly to the dispatcher.

Now identify the actions - a single deploy, a single boot and a single test.

Deploy
^^^^^^

.. code-block:: yaml

 actions:
   - deploy:
       to: tftp
       kernel: http://images-internal/mustang/uImage_1.11
       nfsrootfs: http://people.linaro.org/~neil.williams/arm64/debian-jessie-arm64-rootfs.tar.gz
       dtb: http://images-internal/mustang/mustang.dtb_1.11
       os: debian

Boot
^^^^

Note that ``boot`` has the details of the autologin which will occur
at the end of the boot action.

.. code-block:: yaml

   - boot:
     prompts:
       - 'linaro-test'
       - 'root@debian:~#'
     method: u-boot
     commands: nfs
     type: bootm
     auto_login:
       login_prompt: "login:"
       username: root

Test
^^^^

Note how the test action can have a name and the test definition can also
have  a name, separate from the content of the YAML file.

.. code-block:: yaml

   - test:
     timeout:
       minutes: 5
     name: singlenode-mustang-demo
     definitions:
       - repository: http://git.linaro.org/people/neil.williams/temp-functional-tests.git
         from: git
         path: singlenode/singlenode03.yaml
         name: singlenode-advanced

Complete YAML submission
========================

.. code-block:: yaml

 device_type: mustang
 job_name: mustang-singlenode-jessie
 timeouts:
   job:
     minutes: 15
 actions:
   - deploy:
       to: tftp
       kernel: http://images-internal/mustang/uImage_1.11
       nfsrootfs: http://people.linaro.org/~neil.williams/arm64/debian-jessie-arm64-rootfs.tar.gz
       dtb: http://images-internal/mustang/mustang.dtb_1.11
       os: debian
   - boot:
     prompts:
       - 'linaro-test'
       - 'root@debian:~#'
     method: u-boot
     commands: nfs
     type: bootm
     auto_login:
       login_prompt: "login:"
       username: root
   - test:
     timeout:
       minutes: 5
     name: singlenode-mustang-demo
     definitions:
       - repository: http://git.linaro.org/people/neil.williams/temp-functional-tests.git
         from: git
         path: singlenode/singlenode03.yaml
         name: singlenode-advanced

Writing a device type template
******************************

The purpose of a template is to move as much common data out of each
individual template and into the base template for sharing of code.
Where parameters differ (e.g. the console port), these are supplied
as variables. The device dictionary then only needs to supply information
which is specific to that one device - usually including the serial
connection command and the power commands.

The first point of reference with a new template is the ``lava-server``
`base.jinja2 <https://git.linaro.org/lava/lava-server.git/blob/HEAD:/lava_scheduler_app/tests/device-types/base.jinja2>`_
template and existing examples (e.g. `beaglebone-black
<https://git.linaro.org/lava/lava-server.git/blob/HEAD:/lava_scheduler_app/tests/device-types/beaglebone-black.jinja2>`_)
- templates live on the server, are populated with data from
the database and the resulting YAML is sent to the dispatcher.

Starting a new device type template
===================================

For example, a new mustang template starts as::

 {% extends 'base.jinja2' %}
 {% block body %}

 device_type: mustang

 {% endblock %}

The content is a jinja2 template based directly on the working device jinja2
template above. Where there are values, these are provided with defaults
matching the currently working values. Where there are common blocks of
code in ``base.jinja2``, these are pulled in using Jinja2 templates. The
``commands`` block itself is left to the device dictionary (and picked
up by ``base.jinja2``).

``ramdisk`` and ``nfs`` are particularly common deployment methods, so
the majority of the commands are already available in ``base.jinja2``.
These commands use ``{{ console_device }}`` and ``{{ baud_rate }}``,
which need to be defined with defaults:

.. code-block:: jinja

 {% set console_device = console_device | default('ttyS0') %}
 {% set baud_rate = baud_rate | default(115200) %}

  parameters:
    bootm:
     kernel: '{{ bootm_kernel_addr|default('0x4002000000') }}'
     ramdisk: '{{ bootm_ramdisk_addr|default('0x4004000000') }}'
     dtb: '{{ bootm_dtb_addr|default('0x4003000000') }}'

The actions are determined by the available support for this device,
initially, templates can simply support the initial working configuration,
more support can be added later.

.. code-block:: jinja

  actions:
    deploy:
      methods:
        tftp

  boot:
    prompts:
      - 'linaro-test'
      - 'root@debian:~#'
    methods:
      u-boot:
        parameters:
          bootloader_prompt: {{ bootloader_prompt|default('Mustang') }}
          boot_message: {{ boot_message|default('Starting kernel') }}
        nfs:
          commands:
 {{ base_uboot_commands }}
 {{ base_uboot_addr_commands }}
 {{ base_tftp_commands }}
          # Always quote the entire string if the command includes a colon to support correct YAML.
          - "setenv nfsargs 'setenv bootargs console={{ console_device }},{{ baud_rate }}n8 root=/dev/nfs rw {{ base_nfsroot_args }} panic=1 earlyprintk=uart8250-32bit,0x1c020000 debug ip=dhcp'"
 {{ base_nfs_uboot_bootcmd }}

Completed mustang template
--------------------------

.. code-block:: jinja

 {% extends 'base.jinja2' %}
 {% block body %}

 device_type: mustang
 {% set console_device = console_device | default('ttyS0') %}
 {% set baud_rate = baud_rate | default(115200) %}

  parameters:
    bootm:
     kernel: '{{ bootm_kernel_addr|default('0x4002000000') }}'
     ramdisk: '{{ bootm_ramdisk_addr|default('0x4004000000') }}'
     dtb: '{{ bootm_dtb_addr|default('0x4003000000') }}'

  actions:
    deploy:
      methods:
      - tftp

    boot:
      prompts:
        - 'linaro-test'
        - 'root@debian:~#'
      methods:
        u-boot:
          parameters:
            bootloader_prompt: {{ bootloader_prompt|default('Mustang') }}
            boot_message: {{ boot_message|default('Starting kernel') }}
          nfs:
            commands:
            - setenv autoload no
 {{ base_uboot_addr_commands }}
 {{ base_tftp_commands }}
            # Always quote the entire string if the command includes a colon to support correct YAML.
            - "setenv nfsargs 'setenv bootargs console={{ console_device }},{{ baud_rate }}n8 root=/dev/nfs rw {{ base_nfsroot_args }} panic=1 earlyprintk=uart8250-32bit,0x1c020000 debug ip=dhcp'"
 {{ base_nfs_uboot_bootcmd }}

 {% endblock %}


Creating a device dictionary for the device
===========================================

Examples of exported device dictionaries exist in the ``lava-server``
`codebase <https://git.linaro.org/lava/lava-server.git/blob/HEAD:/lava_scheduler_app/tests/bbb-01.yaml>`_
for unit test support. The dictionary extends the new template and
provides the device-specific values.

.. code-block:: jinja

 {% extends 'mustang.jinja2' %}
 {% set connection_command = "telnet serial4 7012" %}
 {% set hard_reset_command = "/usr/bin/pduclient --daemon services --hostname pdu15 --command reboot --port 05" %}
 {% set power_off_command = "/usr/bin/pduclient --daemon services --hostname pdu15 --command off --port 05" %}
 {% set power_on_command = "/usr/bin/pduclient --daemon services --hostname pdu15 --command on --port 05" %}

Testing the template and dictionary
===================================

``lava-tool`` has support for comparing the templates with working
YAML files and this can be done using files already deployed or local
changes prior to submission. To test the local files, create a new
directory, add the YAML file used when calling ``lava-dispatch``
directly and add two sub-directories::

 mkdir ./device-types
 mkdir ./devices

Copy ``base.jinja2`` into the ``device-types`` directory, along with your
new local template. Copy the device dictionary file to ``devices``. If
your locally working jinja2 file is called ``working.jinja2``, the comparison
would be::

 $ lava-tool compare-device-conf --wdiff --dispatcher-config-dir . devices/mustang01.yaml working.jinja2
 $ lava-tool compare-device-conf --dispatcher-config-dir . devices/mustang01.yaml working.jinja2

Iterate through the changes, testing any changes to the ``working.jinja2``
at each stage, until you have no differences between the generated YAML
and the working jinja2.

Pay particular attention to whitespace and indentation which have a
direct impact on the structure of the object represented by the file.
``wdiff`` output is very useful for identifying content changes and
it is often necessary to change the order of fields within a single
command to get an appropriate match, even if that order has no actual
effect. By ensuring that the content does match, it allows the comparison
to show other changes like indents. Be prepared to change both the
``working.jinja2`` and the template so that the indenting is the same in
each even after commands have been substituted.

.. note:: The snippets here are just examples. In particular, formatting
   these examples for the documentation has changed some of the indents,
   so take particular care to compare and fix the indents of your files
   and ensure that your working YAML file continues to work as well as
   to match the output of the template.

Adapting the base commands to the device type
---------------------------------------------

``base.jinja2`` for most devices uses the command
``base_uboot_commands`` which expands to::

          - setenv autoload no
          - setenv initrd_high '0xffffffff'
          - setenv fdt_high '0xffffffff'

This command works well on 32-bit systems, on the mustang, it causes:

.. code-block:: yaml

 - {target: ERROR: Failed to allocate 0xa38c bytes below 0xffffffff.}
 - {target: Failed using fdt_high value for Device TreeFDT creation failed! hanging...### ERROR ### Please RESET the board ###}

So the mustang template simply omits ``base_uboot_commands``, using:

.. code-block:: yaml

          - setenv autoload no

Completing the migration
************************

The device dictionary and the template need to be introduced into the
``lava-server`` configuration and database entries created for the
device type and device. Helpers may be implemented for this in due course
but the process involves:

#. Add a device type to lava_scheduler_app in the admin interface
#. Populate fields (you can omit health check for now - pipeline health
   checks are not yet ready).
#. Add a device of the specified type to lava_scheduler_app in the
   admin interface. Set the device as a pipeline device by checking the
   "Pipeline Device" box.
#. Add the template to the ``lava-server`` configuration::

   $ sudo cp device-types/mustang.jinja2 /etc/lava-server/dispatcher-config/device-types/

#. Import the device dictionary to provide the device-specific configuration::

   $ sudo lava-server manage device-dictionary --hostname mustang1 --import mustang1.yaml

#. Review the generated YAML::

   $ sudo lava-server manage device-dictionary --hostname mustang1 --review

#. Submit a test job against ``localhost`` and ensure it runs to completion::

   $ lava-tool submit-job http://<user>@localhost/RPC2 mustang-nfs.yaml

#. Offer the new template as a :ref:`code review <contribute_upstream>`
   against ``lava-server``.
