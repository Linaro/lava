.. _protocols:

Protocol Reference
##################

Protocols are similar to a Connection but operate over a known API instead of a
shell connection. The protocol defines which API calls are available through
the LAVA interface and the Pipeline determines when the API call is made.

Not all protocols can be called from all actions. Not all protocols are able to
share data between actions.

A Protocol operates separately from any Connection, generally over a
predetermined layer, e.g. TCP/IP sockets. Some protocols can access data
passing over a Connection.

.. contents::
   :backlinks: top

.. _multinode_protocol:

MultiNode Protocol
******************

This protocol allows actions within the Pipeline to make calls using the
:ref:`MultiNode_api` outside of a test definition by wrapping the call inside
the protocol. Wrapped calls do not necessarily have all of the functionality of
the same call available in the test definition.

The MultiNode Protocol allows data to be shared between actions, including data
generated in one test shell definition being made available over the protocol
to a deploy or boot action of jobs with a different ``role``. It does this by
adding handlers to the current Connection to intercept API calls.

The MultiNode Protocol can underpin the use of other tools without necessarily
needing a dedicated Protocol class to be written for those tools. Using the
MultiNode Protocol is an extension of using the existing :ref:`multinode_api`
calls within a test definition. The use of the protocol is an advanced use of
LAVA and relies on the test writer carefully planning how the job will work.

.. code-block:: yaml

        protocols:
          lava-multinode:
            action: umount-retry
            request: lava-sync
            messageID: test

This snippet would add a :ref:`lava_sync` call at the start of the UmountRetry
action:

* Actions which are too complex and would need data mid-operation need to be
  split up.

* When a particular action is repeatedly used with the protocol, a dedicated
  action needs to be created. Any Strategy which explicitly uses protocol
  support **must** create a dedicated action for each protocol call.

* To update the value available to the action, ensure that the key exists in
  the matching :ref:`lava_send` and that the value in the job submission YAML
  starts with **$** ::

          protocols:
          lava-multinode:
            action: execute-qemu
            request: lava-wait
            messageID: test
            message:
              ipv4: $IPV4

  This results in this data being available to the action::

   {'message': {'ipv4': '192.168.0.3'}, 'messageID': 'test'}

* Actions check for protocol calls at the start of the run step before even the
  internal pipeline actions are run.

* Only the named Action instance inside the Pipeline will make the call

* The :ref:`multinode_api` asserts that repeated calls to :ref:`lava_sync` with
  the same messageID will return immediately, so this protocol call in a Retry
  action will only synchronise the first attempt at the action.

* Some actions may make the protocol call at the end of the run step.

The MultiNode Protocol also exposes calls which are not part of the test shell
API, which were formerly hidden inside the job setup phase.

.. _lava_start:

lava-start API call
===================

``lava-start`` determines when MultiNode jobs start, according to the state of
other jobs in the same MultiNode group. This allows jobs with one ``role`` to
determine when jobs of a different ``role`` start, so that the delayed jobs can
be sure that particular services required for those jobs are available. For
example, if the ``server`` role is actually providing a virtualisation platform
and the ``client`` is a VM to be started on the ``server``, then a delayed
start is necessary as the first action of the ``client`` role will be to
attempt to connect to the server in order to boot the VM, before the ``server``
has even been deployed. The ``lava-start`` API call allows the test writer to
control when the ``client`` is started, allowing the ``server`` test image to
setup the virtualisation support in a way that allows attaching of debuggers or
other interventions, before the VM starts.

The client enables a delayed start by declaring which ``role`` the client can
``expect`` to send the signal to start the client.

.. code-block:: yaml

        protocols:
          lava-multinode:
            request: lava-start
            expect_role: server
            timeout:
              minutes: 10

The timeout specified for ``lava_start`` is the amount of time the job will
wait for permission to start from the other jobs in the group.

Internally, ``lava-start`` is implemented as a :ref:`lava_send` and a
:ref:`lava_wait_all` for the role of the action which will make the
``lava_start`` API call using the message ID ``lava_start``.

It is an error to specify the same ``role`` and ``expect_role`` to
``lava-start``.

.. note:: Avoid confusing :ref:`host_role <host_role>` with ``expect_role``.
   ``host_role`` is used by the scheduler to ensure that the job assignment
   operates correctly and does not affect the dispatcher or delayed start
   support. The two values may often have the same value but do not mean the
   same thing.

It is an error to specify ``lava-start`` on all roles within a job or on any
action without a ``role`` specified.

All jobs without a ``lava-start`` API call specified for the ``role`` of that
job will start immediately. Other jobs will write to the log files that the
start has been delayed, pending a call to ``lava-start`` by actions with the
specified role(s).

Subsequent calls to ``lava-start`` for a role which has already started will
still be sent but will have no effect.

If ``lava-start`` is specified for a ``test`` action, the test definition is
responsible for making the ``lava-start`` call.

.. code-block:: yaml

 run:
   steps:
     - lava-send lava_start

.. _passing_data_at_startup:

Passing data at startup
=======================

The pipeline exposes the names of all actions and these names are used for a
variety of functions, from timeouts to protocol usage.

To see the actions within a specific pipeline job, see the job definition (not
the MultiNode definition) where you will find a Pipeline Description.

Various delayed start jobs will need dynamic data from the "server" job in
order to be able to start, like an IP address. This is achieved by adding the
``lava-start`` call to a specified ``test`` action of the server role where the
test definition initiates a :ref:`lava_send` message. When this specific
``test`` action completes, the protocol will send the ``lava-start``. The first
thing the delayed start job does is a ``lava-wait`` which would be added to the
``deploy`` action of that job.

+-----------------------------------+-------------------------+
| ``Server`` role                   | Delayed ``client`` role |
+===================================+=========================+
| ``deploy``                        |                         |
+-----------------------------------+-------------------------+
| ``boot``                          |                         |
+-----------------------------------+-------------------------+
| ``test``                          |                         |
+-----------------------------------+-------------------------+
| ``- lava-send ipv4 ipaddr=$(IP)`` |                         |
+-----------------------------------+-------------------------+
| ``- lava-start``                  |  ``deploy``             |
+-----------------------------------+-------------------------+
|                                   |  ``- lava-wait ipv4``   |
+-----------------------------------+-------------------------+
| ``- lava-test-case``              |  ``boot``               |
+-----------------------------------+-------------------------+

.. code-block:: yaml

      deploy:
        role: client
        protocols:
          lava-multinode:
          - action: prepare-scp-overlay
            request: lava-wait
            message:
                ipaddr: $ipaddr
            messageID: ipv4
            timeout:
              minutes: 5

.. note:: Some calls can only be made against specific actions. Specifically,
   the ``prepare-scp-overlay`` action needs the IP address of the host device
   to be able to copy the LAVA overlay (containing the test definitions) onto
   the device before connecting using ``ssh`` to start the test. This is a
   **complex** configuration to write.

.. seealso:: :ref:`writing_secondary_connection_jobs`

Depending on the implementation of the ``deploy`` action, determined by the
Strategy class, the ``lava-wait`` call will be made at a suitable opportunity
within the deployment. In the above example, the ``lava-send`` call is made
before ``lava-start`` - this allows the data to be stored in the lava
coordinator and the ``lava-wait`` will receive the data immediately.

The specified ``messageID`` **must** exactly match the message ID used for the
:ref:`lava_send` call in the test definition. (So an **inline** test definition
could be useful for the test action of the job definition for the ``server``
role. See :ref:`inline_test_definition_example`)

.. code-block:: yaml

 - lava-send ipv4 ipaddr=$(lava-echo-ipv4 eth0)

``lava-send`` takes a messageID as the first argument.

.. code-block:: yaml

      test:
        role: server
        protocols:
          lava-multinode:
          - action: multinode-test
            request: lava-start
            roles:
              - client

See also :ref:`writing_secondary_connection_jobs`.

.. _managing_flow_using_inline:

Managing flow using inline definitions
======================================

The pipeline exposes the names of all actions and these names are used for a
variety of functions, from timeouts to protocol usage.

To see the actions within a specific pipeline job, see the job definition (not
the MultiNode definition) where you will find a Pipeline Description.

Creating MultiNode jobs has always been complex. The consistent use of inline
definitions can significantly improve the experience and once the support is
complete, it may be used to invalidate submissions which fail to match the
synchronisation primitives.

The principle is to separate the synchronisation from the test operation. By
only using synchronisation primitives inside an inline definition, the flow of
the complete MultiNode group can be displayed. This becomes impractical as soon
as the requirement involves downloading a test definition repository and
possibly fishing inside custom scripts for the synchronisation primitives.

Inline blocks using synchronisation calls can still do other checks and tasks
as well but keeping the synchronisation at the level of the submitted YAML
allows much easier checking of the job before the job starts to run.

.. code-block:: yaml

         - repository:
                metadata:
                    format: Lava-Test Test Definition 1.0
                    name: install-ssh
                    description: "install step"
                install:
                    deps:
                        - openssh-server
                        - ntpdate
                run:
                    steps:
                        - ntpdate-debian
                        - lava-echo-ipv4 eth0
                        - lava-send ipv4 ipaddr=$(lava-echo-ipv4 eth0)
                        - lava-send lava_start
                        - lava-sync clients
           from: inline
           name: ssh-inline
           path: inline/ssh-install.yaml

.. code-block:: yaml

         - repository: git://git.linaro.org/qa/test-definitions.git
           from: git
           path: ubuntu/smoke-tests-basic.yaml
           name: smoke-tests

This is a small deviation from how existing MultiNode jobs may be defined but
the potential benefits are substantial when combined with the other elements of
the MultiNode Protocol.

Marking some roles as essential
===============================

In many Multinode jobs, one or more roles is/are essential to completion of the
test. For example, a secondary connection job using SSH **must** rely on the
role providing the SSH server and cannot be expected to do anything useful if
that role does not become available.

In the MultiNode protocols section of the test job definition, roles may be
marked as **essential: True**. If **any** of the jobs for an essential role
fail with an :ref:`infrastructure_error_exception` or
:ref:`job_error_exception`, then the entire multinode group will end. (Pipeline
jobs always call the FinalizeAction when told to end by the master, so the
device will power-off or the connection can logout.)

.. code-block:: yaml

  protocols:
    lava-multinode:
    # expect_role is used by the dispatcher and is part of delay_start
    # host_role is used by the scheduler, unrelated to delay_start.
      roles:
        host:
          device_type: beaglebone-black
          essential: True
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

VLANd protocol
**************

See :ref:`VLANd protocol <vland_in_lava>` - which uses the MultiNode protocol
to interface with :term:`VLANd` to support virtual local area networks in LAVA.

.. index:: lxc protocol reference, lxc actions

.. _lxc_protocol_reference:

LXC protocol
************

The LXC protocol in LAVA implements a minimal set of APIs in order to define
the LXC container characteristics that will be shared by actions during the
life cycle of a job. The protocol also takes care of graceful tear down of the
LXC container at the end of the job.

Protocol elements
=================

.. code-block:: yaml

  protocols:
    lava-lxc:
      name: pipeline-lxc-test
      template: debian
      distribution: debian
      release: sid
      arch: amd64
      mirror: http://ftp.us.debian.org/debian/
      security_mirror: http://mirror.csclub.uwaterloo.ca/debian-security/
      verbose: true

The characteristics of the LXC container is defined by the following data
elements that are accepted by the LXC protocol:

* **name** *(mandatory)* - Name of the container that needs to be created. The
  LXC protocol appends the job id along with the name of the container provided
  by the user, by default. For example, if the name is given as
  'pipeline-lxc-test' and the submitted job id is 51, then the resulting
  transparent LXC container that will get created during the job execution
  would be 'pipeline-lxc-test-51'. This appending of job id is in place in
  order to ensure job repeatability, ie., when the same job is getting
  submitted more than once simultaneously, this check will ensure unique name
  for the container.

* **template** *(optional)* - Templates are per distribution based pre-defined
  scripts that are used to create LXC containers. Though there are many
  distribution specific templates that are available in LXC, LAVA supports a
  subset of the same. The following templates are supported, if no template is
  specified, by default `download` template is assumed:

  * download
  * debian

* **distribution** *(mandatory)* - The distribution of LXC container that
  should be created, which applies to 'download' template. Though there is no
  effect when this is specified for the 'debian' template, it is a mandatory
  data element.

* **release** *(mandatory)* - Specific release of the distribution specified
  above. When releases are other than codenames such as a version number, the
  value should be treated as a string, ie., when a number is specified, quote
  it, so that it will be taken as a string.

* **arch** *(mandatory)* - The architecture of the LXC container that should be
  created, this is limited to the processor architecture on which the LAVA
  dispatcher runs on.

* **mirror** *(optional)* - Specifies the Debian mirror to use during
  installation. This is specific to the 'debian' template. There is no effect
  when this is specified for the 'download' template.

* **security_mirror** *(optional)* - Specifies the Debian security mirror to use
  during installation. This is specific to the 'debian' template. There is no
  effect when this is specified for the 'download' template.

* **verbose** *(optional)* - Controls the output produced during LXC
  creation. By default the value is `False`. When `verbose` is set to `True`
  the LXC creation command produces detailed output.
