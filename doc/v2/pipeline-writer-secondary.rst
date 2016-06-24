.. _writing_secondary_connection_jobs:

Writing jobs using Secondary Connections
########################################

Secondary connections involve Multinode submissions and some of the
setup can require some thought. As with other Multinode test writing
tasks, it is helpful to draw out the flow of each role, matching the
synchronisation points, to make it clear which role is waiting at each
point of the test.

Even if the test definitions will eventually reside in external
repositories, it is helpful to do the planning stage using inline
definitions. See :ref:`inline_test_definition_example`.

.. _secure_secondary_shells:

Secure Shell connections (ssh)
******************************

:file:`ssh` involves deploying and booting a test device to host the
server daemon and delaying the start of the secondary connection(s)
until this daemon is ready. As the deployment of the test device acting
as the host is specified by the test writer, the IP address of the
host device and therefore the ssh server is unknown at submission. So
there are two problems to resolve:

#. The secondary connections must wait for the host to be ready
#. The secondary connections must know the IP address of the host
   once the host is ready and before attempting to connect.

The flow for the job will be:

#. The job will use :ref:`lava_start` to resolve the first problem.
#. The job will also use :ref:`passing_data_at_startup` to resolve the second problem.


+------------------------------+---------------------------+
|   **host role**              |    **guest role(s)**      |
+==============================+===========================+
| Multinode group start        | Multinode group start     |
+------------------------------+---------------------------+
| Deploy to test device        | Wait for lava-start       |
+------------------------------+---------------------------+
| Boot test device             |                           |
+------------------------------+---------------------------+
| Login                        |                           |
+------------------------------+---------------------------+
| Start test definition        |                           |
+------------------------------+---------------------------+
| install openssh-server       |                           |
+------------------------------+---------------------------+
| obtain IP address            |                           |
+------------------------------+---------------------------+
| ``lava-send`` ipv4           |                           |
+------------------------------+---------------------------+
| ``lava-send`` lava_start     |                           |
+------------------------------+---------------------------+
| ``lava-sync`` clients        |  Deployment starts        |
+------------------------------+---------------------------+
|                              | Action retrieves ipv4     |
+------------------------------+---------------------------+
|                              | Boot starts               |
+------------------------------+---------------------------+
|                              | host_address set to ipv4  |
+------------------------------+---------------------------+
|                              | scp overlay to host       |
+------------------------------+---------------------------+
|                              | Start test definition     |
+------------------------------+---------------------------+
|                              | ``lava-sync`` clients     |
+------------------------------+---------------------------+
| further test actions         | further test actions      |
+------------------------------+---------------------------+
| ``lava-sync`` finish         | ``lava-sync`` finish      |
+------------------------------+---------------------------+
| further test actions         | Finalise action & logout  |
+------------------------------+---------------------------+
| Finalize action & power off  |                           |
+------------------------------+---------------------------+

.. note:: Secondary connections rely on the host device remaining powered
   on and the server daemon continuing to operate. The guest roles **must**
   always finish before (or at the same time) as the host or the guest
   job will fail with a broken connection. To ensure this, the jobs
   need to use a final file:`lava-sync` operation - the host can continue
   to do test actions after that sync has completed.

Delaying the start of a job using Multinode
===========================================

The real device in this example has the role label **host**. The
guest secondary connections over SSH are testjobs with the role
**guest**.

The ``lava-start`` request implements the delayed start of the
guest connections by expecting a message from the device with the
**host** role, allowing 15 minutes from the time the Multinode group
jobs start for the device to boot and for the server to be installed
and ready for connections.

.. code-block:: yaml

 protocols:
   lava-multinode:
   # expect_role is used by the dispatcher and is part of delay_start
   # host_role is used by the scheduler, unrelated to delay_start.
     roles:
       host:
         device_type: beaglebone-black
         count: 1
         timeout:
           minutes: 10
       guest:
         # protocol API call to make during protocol setup
         request: lava-start
         # set the role for which this role will wait
         expect_role: host
         timeout:
           minutes: 15
         # no device_type, just a connection
         connection: ssh
         count: 3
         # each ssh connection will attempt to connect to the device of role 'host'
         host_role: host

Ignoring the deploy or boot sections for now, the test action for
the **host** role then needs to arrange for the server to be installed,
start it and identify the IP address at which the server can be
contacted. Then the **host** role can tell the **guest** role to
start by using the Multinode API.

.. note:: The IP address is gathered using a LAVA helper and sent to the
   guests before the start is requested. The guest has a ``lava-wait`` call
   but sending early means that the guest does not need to wait. This new
   helper (:file:`lava-echo-ipv4` uses the same parsing as :file:`lava-network`
   but does not need the guest to collect data and wait for the entire
   group to broadcast. It can be used in any test definitions using the
   :term:`pipeline` or the current dispatcher.

Picking up the data in the guest role
=====================================

The LAVA :ref:`multinode_protocol` has support for Multinode API calls
outside of the test definition by making a request based on a named
action within the pipeline for the job.

.. code-block:: yaml

  - deploy:
      timeout:  # timeout for the connection attempt
        seconds: 30
      to: ssh
      connection: ssh
      os: debian
      protocols:
        lava-multinode:
          - action: prepare-scp-overlay
            request: lava-wait
            message:
                ipaddr: $ipaddr
            messageID: ipv4
        timeout:  # delay_start timeout
          minutes: 5
      role:
      - guest

This data also needs to be available to the boot action which will
actually make the ``ssh`` login, so the boot action needs to know
exactly which value to retrieve from the Multinode data:

.. code-block:: yaml

  - boot:
      timeout:
        minutes: 3
      method: ssh
      connection: ssh
      parameters:
        hostID: ipv4
        host_key: ipaddr
      role:
      - guest

The ``hostID`` needs to match the ``messageID``, the ``host_key`` needs
to match the key of the ``message``. The value of the message can then
be retrieved.

Test definition for the host role
=================================

This definition needs to install the server daemon, obtain the local IP
address and send that to the group, allow the guests to start and wait
for the guests to complete their own actions.

.. code-block:: yaml

  - test:
     name: install-ssh-server
     timeout:
       minutes: 30
     definitions:
         - repository:
                metadata:
                    format: Lava-Test Test Definition 1.0
                    name: install-ssh
                    description: "install step"
                    os:
                        - debian
                    scope:
                        - functional
                install:
                    deps:
                        - openssh-server
                        - ntpdate
                run:
                    steps:
                        - ntpdate-debian
                        - lava-send ipv4 ipaddr=$(lava-echo-ipv4 eth0)
                        - lava-send lava_start
                        - lava-sync clients
           from: inline
           name: ssh-inline
           path: inline/ssh-install.yaml
         - repository: git://git.linaro.org/qa/test-definitions.git
           from: git
           path: ubuntu/smoke-tests-basic.yaml
           name: smoke-tests
     role:
     - host

Test definition for the guest role
==================================

In this example, the guest runs other tasks before calling the sync as
the final operation.

.. code-block:: yaml

  - test:
     name: guest-secondary
     timeout:
       minutes: 5
     definitions:
         - repository: git://git.linaro.org/qa/test-definitions.git
           from: git
           path: ubuntu/smoke-tests-basic.yaml
           name: smoke-tests
           # run the inline last as the host is waiting for this final sync.
         - repository:
                metadata:
                    format: Lava-Test Test Definition 1.0
                    name: client-ssh
                    description: "client complete"
                    os:
                        - debian
                    scope:
                        - functional
                run:
                    steps:
                        - df -h
                        - free
                        - lava-sync clients
           from: inline
           name: ssh-client
           path: inline/ssh-client.yaml
     role:
     - guest

Complete Multinode test definition
==================================

https://git.linaro.org/lava-team/refactoring.git/blob_plain/HEAD:/bbb-ssh-guest.yaml

.. code-block:: yaml

    # submission YAML prototype for connecting to a BBB over ssh
    # as secondary connection.
    # whichever role is operating as the "host" must specify how to
    # authorize connections from other roles using the authorize: key
    # in the deployment. This allows the relevant Action to deploy the
    # necessary support. e.g. /root/.ssh/authorized_keys

    job_name: bbb-guest-ssh
    timeouts:
      job:
        minutes: 30
      action:
        minutes: 3
      connection:
        minutes: 5
    visibility: public

    protocols:
      lava-multinode:
      # expect_role is used by the dispatcher and is part of delay_start
      # host_role is used by the scheduler, unrelated to delay_start.
        roles:
          host:
            device_type: beaglebone-black
            count: 1
            timeout:
              minutes: 10
          guest:
            # protocol API call to make during protocol setup
            request: lava-start
            # set the role for which this role will wait
            expect_role: host
            timeout:
              minutes: 15
            # no device_type, just a connection
            connection: ssh
            count: 3
            # each ssh connection will attempt to connect to the device of role 'host'
            host_role: host

    priority: medium

    actions:
      - deploy:
          timeout:
            minutes: 4
          to: tftp
          # authorize for ssh adds the ssh public key to authorized_keys
          authorize: ssh
          kernel:
            url: https://images.validation.linaro.org/functional-test-images/bbb/zImage
          # nfsrootfs: file:///home/linaro/lava/nfsrootfs/jessie-rootfs2.tar.gz
          nfsrootfs:
            url: https://images.validation.linaro.org/debian-jessie-rootfs.tar.gz
            compression: gz
          os: debian
          dtb:
            url: https://images.validation.linaro.org/functional-test-images/bbb/am335x-bone.dtb
          role:
          - host

      - deploy:
          timeout:  # timeout for the connection attempt
            seconds: 30
          to: ssh
          connection: ssh
          os: debian
          protocols:
            lava-multinode:
            - action: prepare-scp-overlay
              request: lava-wait
              # messageID matches hostID
              messageID: ipv4
              message:
                # the key of the message matches value of the host_key
                # the value of the message gets substituted
                ipaddr: $ipaddr
              timeout:  # delay_start timeout
                minutes: 5
          role:
          - guest

      - boot:
          timeout:
            minutes: 15
          method: u-boot
          commands: nfs
          type: bootz
          prompts: ['root@linaro:', 'root@debian:']
          # auto_login:
          # login_prompt: "login:"
          # username: root
          parameters:
            shutdown-message: "reboot: Restarting system"
          role:
          - host

      - boot:
          timeout:
            minutes: 3
          prompts: ['root@linaro:', 'root@debian:']
          parameters:
            hostID: ipv4  # messageID
            host_key: ipaddr  # message key
          method: ssh
          role:
          - guest

      - test:
         name: install-ssh-server
         timeout:
           minutes: 30
         definitions:
             - repository:
                    metadata:
                        format: Lava-Test Test Definition 1.0
                        name: install-ssh
                        description: "install step"
                        os:
                            - debian
                        scope:
                            - functional
                    install:
                        deps:
                            - openssh-server
                            - ntpdate
                    run:
                        steps:
                            - ntpdate-debian
                            - lava-network broadcast eth0
                            # messageID matches, message_key as the key.
                            - lava-send ipv4 ipaddr=$(lava-echo-ipv4 eth0)
                            - lava-send lava_start
                            - lava-sync clients
               from: inline
               name: ssh-inline
               path: inline/ssh-install.yaml
             - repository: git://git.linaro.org/qa/test-definitions.git
               from: git
               path: ubuntu/smoke-tests-basic.yaml
               name: smoke-tests
         role:
         - host

      - test:
         name: kvm-basic-singlenode
         timeout:
           minutes: 5
         definitions:
             - repository: git://git.linaro.org/qa/test-definitions.git
               from: git
               path: ubuntu/smoke-tests-basic.yaml
               name: smoke-tests
               # run the inline last as the host is waiting for this final sync.
             - repository:
                    metadata:
                        format: Lava-Test Test Definition 1.0
                        name: client-ssh
                        description: "client complete"
                        os:
                            - debian
                        scope:
                            - functional
                    run:
                        steps:
                            - df -h
                            - free
                            - lava-sync clients
               from: inline
               name: ssh-client
               path: inline/ssh-client.yaml
         role:
         - guest
