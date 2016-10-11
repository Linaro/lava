.. index:: replacing vmgroups, secondary connections - vmgroups

.. _replacing_vmgroups:

Replacing VMGroups using Secondary Connections
##############################################

One of the primary use cases for secondary connections is the abilty to *watch* a job from
multiple perspectives. This includes being able to start a task in one job and interact
with that task from another job. For example, if one job runs QEMU to start a VM on the host
machine, another connection can test that the VM responds on the relevant ports, depending
on what is installed inside the image downloaded onto the host machine. More complex jobs
could start a daemon in a debugger and connect to the output of the daemon itself in one
job and to the output of the debugger in another job. This does not necessarily require the
watching job to do anything, the job could just record the output.

The role of a Virtual Machine Group is to arrange a test job such that a host device, which
**must** have virtualisation support, boots into a base image and installs a daemon to allow
other test jobs to connect - typically this will be :ref:`secure_secondary_shells`.

.. seealso:: :ref:`host_role`

Once the secondary connections are logged in, any program accessible in the base image can be
used by the secondary connection. :ref:`As highlighted <host_role>` in the link above, tasks involving
package installation or other system-wide operations are best done in the test job managing the host
device and preferably **before** the secondary connection jobs start. So the ``install: deps:`` of all
jobs in the group should all be collated into the test definition(s) of the host role.

The secondary connection support performs all the synchronisation steps that are required prior to
the test shell starting in each of the secondary test jobs. The :ref:`multinode_api` remains available
for any synchronisation requirements during the test shell operation. **Importantly** the test shell
running on the host device should wait for a :ref:`lava_sync` before completing the test shell definition.
Otherwise the secondary connection jobs may find that the underlying system suddenly goes away unexpectedly.

With all of that in place, the actual operation of a test involving multiple virtual machines is little
different to a test involving a daemon or long running task. Something in the secondary job test shell
needs to start the process and something needs to end the process so that the final ``sync`` can occur.
If the task is not capable of terminating itself, it will be necessary for one test shell (often the host
role on the host device) to be able to terminate it or the test shell will not complete. The choice of how
to do this is left to the test writer.

The command line to use to start the VM(s) on the host device is controlled entirely by the test
specification. This is different to the old deprecated `vmgroups` support. Image files and other
components can be present in the image deployed to the host device or downloaded by the host device or
after the secondary connection is logged in. The delayed start requirements are already covered by the
secondary connections, so the test shell can start the VM immediately, if desired, or do any preliminary
tests first.

Structure of an example job for a mustang
=========================================

This job uses an nfsrootfs for the host device on a mustang (using the U-Boot pipeline support
for the mustang) as the host role. The NFS is a base Debian Jessie arm64, so the initial
lava test shell operation on the host is to install ``openssh-server`` and then use the ``lava-echo-ipv4``
helper to declare the IPv4 address of the host machine.

The secondary connection support picks up the IP address in the pipeline actions, so the id of the
message needs to be declared to the relevant action. The test shell sends::

 lava-send ipv4 ipaddr=$(lava-echo-ipv4 eth0)

Then it tells the secondary connections to start::

 lava-send lava-start

This tells the dispatcher for the ``guest`` role to start the deployment. The test definition files for
secondary connection jobs are copied onto the host device immediately before the connection is made,
then the contents are unpacked to be able to run the test shell. The tarball will exist on the
host device as ``/<job_id>-overlay-<level>.tar.gz``. For job ID ``74585`` and level ``1.1.5``, this would result
in ``/74585-overlay-1.1.5.tar.gz``.

In this example job, the host test shell does nothing except wait for the clients to complete
their own tests before proceeding to run a final test shell of smoke tests.

The receiving action is declared as:

.. code-block:: yaml

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

.. note:: the messageID specified to ``lava-send`` (*ipv4*), is also the messageID specified to the
   ``prepare-scp-overlay`` action within the pipeline. In addition, the content of the sent message is
   declared. ``lava-send`` uses the syntax ``key=value``, the YAML uses the equivalent syntax of
   ``key: value``. As the value will be substituted with the real IP address, the value in the YAML
   is marked as replaceable using the ``$`` prefix.

The message parameters are passed to the ``boot`` action of the ``guest`` role so that the
details can be retrieved:

Finally, the jobs with the ``guest`` role are *booted* - this establishes the connection between the dispatcher
and the host device using ssh. Once logged in, each job completes the boot stage and starts the test shell
for that job.

.. code-block:: yaml

    - boot:
        method: ssh
        role: [guest]
        prompts: ['root@linaro-nano:']
        parameters:
          hostID: ipv4  # messageID
          host_key: ipaddr  # message key

Notes
-----

* **Starting the VM(s)** is for the test writer to implement, depending on the support required and
  the objectives of the test. In the example below, the host device simply runs the smoke tests
  definition in the position where images could be downloaded and QEMU started.
* **Use inlines** - this example keeps all of the :ref:`multinode_api` calls to the inline
  definitions. This is a recommended practice and future developments will make it easier to match up
  the synchronisation calls from inline definitions. So, to adapt this job to do other tasks while the
  secondary connections jobs are running those test shells, move the final ``lava-sync clients`` to another
  inline definition and do the other calls in between.

  .. seealso:: :ref:`running_inside_vm`

* **Completion** - It is useful for the host device test shell to do **something** after completing the final
  ``lava-sync`` or the host device may complete the test shell before the secondary connections can logout
  correctly, resulting in the secondary connection jobs being incomplete. A final test definition of smoke
  tests or other quick checks could be useful.

https://git.linaro.org/lava-team/refactoring.git/blob/HEAD:/mustang-ssh-guest.yaml

.. code-block:: yaml

    actions:
    - deploy:
        role: [host]
        authorize: ssh
        dtb:
          url: http://images-internal/mustang/mustang.dtb_1.11
        kernel:
          url: http://images-internal/mustang/uImage_1.11
        nfsrootfs:
          url: https://people.linaro.org/~neil.williams/arm64/debian-jessie-arm64-rootfs.tar.gz
          compression: gz
        os: debian
        timeout: {minutes: 5}
        to: tftp
    - deploy:
        role: [guest]
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
        timeout: {seconds: 30}
        to: ssh
    - boot:
        role: [host]
        auto_login: {login_prompt: 'login:', username: root}
        commands: nfs
        prompts: ['root@linaro-nano:']
        method: u-boot
        timeout: {minutes: 5}
        type: bootm
    - boot:
        role: [guest]
        method: ssh
        prompts: ['root@linaro-nano:']
        parameters:
          hostID: ipv4  # messageID
          host_key: ipaddr  # message key
        timeout: {minutes: 3}
    - test:
        role: [host]
        definitions:
        - from: inline
          name: ssh-inline
          path: inline/ssh-install.yaml
          repository:
            install:
              deps: [openssh-server, ntpdate]
            metadata:
              description: install step
              format: Lava-Test Test Definition 1.0
              name: install-ssh
              os: [debian]
              scope: [functional]
            run:
              steps: [ntpdate-debian, lava-send ipv4 ipaddr=$(lava-echo-ipv4 eth0), lava-send lava_start]
        # insert a test definition here which starts the VM(s)
        - {from: git, name: smoke-tests, path: ubuntu/smoke-tests-basic.yaml, repository: 'git://git.linaro.org/qa/test-definitions.git'}
        - from: inline
          name: completion
          path: inline/client-completion.yaml
          repository:
            metadata:
              description: synchronisation once clients are complete
              format: Lava-Test Test Definition 1.0
              name: client-completion
              os: [debian]
            run:
              steps: [lava-sync clients]
        name: client-completion
        timeout: {minutes: 30}
    - test:
        role: [guest]
        definitions:
        - {from: git, name: smoke-tests, path: ubuntu/smoke-tests-basic.yaml, repository: 'git://git.linaro.org/qa/test-definitions.git'}
        - from: inline
          name: ssh-client
          path: inline/ssh-client.yaml
          repository:
            metadata:
              description: client complete
              format: Lava-Test Test Definition 1.0
              name: client-ssh
              os: [debian]
              scope: [functional]
            run:
              steps: [df -h, free, lava-sync clients]
        name: kvm-basic-singlenode
        timeout: {minutes: 5}
    job_name: mustang-guest-ssh
    priority: medium
    visibility: public
    protocols:
      lava-multinode:
        roles:
          guest:
            connection: ssh
            count: 3
            expect_role: host
            host_role: host
            request: lava-start
            timeout: {minutes: 15}
          host:
            count: 1
            device_type: mustang
            timeout: {minutes: 10}
    timeouts:
      action: {minutes: 3}
      job: {minutes: 30}
      connection:
        minutes: 3

.. _running_inside_vm:

Running operations inside the guest VM
======================================

A guest VM started by running QEMU on the command line is not a LAVA environment (unless the test writer
deliberately copies files into it from another job), so it will not run a lava test shell by default. Tasks can
be executed within the VM from any of the other jobs running on the host device, dependent on support provided
by the test writer.

Remember, although LAVA tries to stay out of the way of how the test runs once the secondary connection has logged
in, there are some things test writers need to consider to be able to automate tests like these.

#. If you start QEMU with the ``-nographics`` option rather than as a daemon, the secondary connection gets connected
   to the console of that VM at the point within the test shell where the call to QEMU is made.
#. Make sure you know if the image being used has a serial console configured.
#. If the image being launched stops at a ``login:`` prompt, the test definition will need to handle that prompt
   or log in to the VM in some other way. e.g. by having one of the other secondary connections set up a configuration
   to use ``ssh`` to log in to the VM - the keys needed for this login will need to be handled by the test writer.
#. The test shell will **pause**, waiting for QEMU to return, unless QEMU is configured to do otherwise or a
   wrapper like ``pexpect`` is used. (The LAVA QEMU devices run a QEMU command using ``pexpect.spawn`` but this
   is not necessarily suitable for test jobs.)
#. If the VM is started as a daemon, then the test shell will need to have a way of monitoring when the VM is ready
   and then connect to the VM, as appropriate.

.. note:: The :ref:`lava_start` **only acts once** - i.e. the host role starts, then the other jobs wait until
   ``lava-start`` is sent - at which point these jobs will download any test shell definitions and try to connect
   to the IP address declared. It is better to have a synchronisation which the test writer controls, after all the
   jobs have connected to the host device.
