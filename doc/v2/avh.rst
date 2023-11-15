.. index:: avh, Arm Virtual Hardware

AVH
###

The AVH device type in LAVA refers to `Arm Virtual Hardware <https://www.arm.com/products/development-tools/simulation/virtual-hardware>`_.

AVH for third-party boards provides cloud-based functionally accurate virtual
models of popular IoT development kits, simulating CPU, peripherals, sensors
and board components. It allows developers to execute the same binaries as on
the real hardware and so leverage the board SDKs and software code examples.

AVH integration in LAVA enables efficient CI workflow for modern agile software
development.

LAVA AVH Dispatcher Setup
*************************

LAVA uses `avh-api <https://pypi.org/project/avh-api/>`_ Python library to
communicate with AVH's REST API for managing virtual devices. If you are a LAVA
docker worker user, the library is already pre-installed in lava dispatcher
docker image. If your LAVA dispatcher is installed via APT, you will need to
install the avh-api library manually using the following commands. This is
mainly because the library isn't available via APT installation yet.

.. code-block:: bash

  apt-get install --no-install-recommends --yes python3-pip
  python3 -m pip install avh-api==1.0.5

API Authentication
******************

The following steps are required to authorize LAVA for API access to AVH.

1. Generate AVH API token.

   Log in to AVH with your Arm account at https://app.avh.arm.com. Navigate to
   your profile by clicking on your name at the top right corner. Change to API
   tab. Then click GENERATE button to generate your AVH API Token.

2. Add LAVA remote artifact tokens.

   Log in to LAVA server. Click on your name at the top right corner, and then
   click Profile. On the profile page, click the Remote artifact tokens Create
   button and input ``avh_api_token`` for Token name and the above AVH API
   token for Token string. Save the token.

3. Define secrets block in LAVA job definition.

   .. code-block:: yaml

      secrets:
        avh_api_token: avh_api_token

   The secrets block should include the ``avh_api_token`` key. LAVA dispatcher
   needs it for AVH API authentication. The key value should be the **name** of
   the above LAVA remote artifact token name. At run time, the token name will
   be replaced with the token string by LAVA server. This is mainly for hiding
   the real token in a public LAVA job.

Job Example
***********

.. code-block:: yaml

   device_type: avh
   job_name: avh-rpi4b-health-check

   timeouts:
     job:
       minutes: 60

   priority: medium
   visibility: public

   secrets:
     avh_api_token: avh_api_token

   actions:
   - deploy:
       to: avh
       avh:
         model: rpi4b
       timeout:
         minutes: 30
       images:
         rootfs:
           url: https://example.com/rpi4b/nand
           format: ext4
           root_partition: 1
         kernel:
           url: https://example.com/rpi4b/kernel
         dtb:
           url: https://example.com/rpi4b/devicetree

   - boot:
       method: avh
       timeout:
         minutes: 20
       prompts:
       - "pi@raspberrypi:"
       - "root@raspberrypi:"
       auto_login:
         login_prompt: "login:"
         username: pi
         password_prompt: 'Password:'
         password: raspberry
         login_commands:
         - sudo su

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
