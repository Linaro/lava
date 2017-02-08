.. index:: developer testing, running unit tests

.. _testing_pipeline_code:

Testing the new design
######################

To test the new design after making changes, use the :ref:`unit_tests`. During
development, it is useful to only run selected tests, although remember that
**all** tests must pass before proposing the change as a review.

In each case, ensure that your local packages are up to date and rebase your
local development branch against master if ``git pull`` fetches new commits. If
your branch needed to be updated, always build and install your local packages.

.. seealso:: :ref:`developer_build_version`

lava-server
***********

::

 $ ./lava_server/manage test

``lava-server`` has several components, see the contents of ``ci-run`` for the
full list. Each component can be tested separately::

 $ ./lava_server/manage test lava_scheduler_app

To run particular tests in a specific file, add e.g. ``test_device.py`` to the
command::

 $ ./lava_server/manage test lava_scheduler_app.tests.test_device

.. note:: the ``tests`` directory needs to be specified (instead of the test
   process discovering all tests) and the filename lacks the ``.py`` suffix.

Add the class name to run all tests within that class within the specified
file.::

 $ ./lava_server/manage test lava_scheduler_app.tests.test_device.TestTemplates

Add a specific test function to run only that one unit test::

 $ ./lava_server/manage test lava_scheduler_app.tests.test_device.TestTemplates.test_x86_template

The same path can also be passed to ``./ci-run``::

 $ ./ci-run lava_scheduler_app.tests.test_device.TestTemplates.test_x86_template

This adds the ``pep8`` check before running the test(s).

Jinja2 templates
================

#. All jinja2 templates in ``lava_scheduler_app/tests/device-types/`` will be
   tested using a basic check in
   ``lava_scheduler_app.tests.test_device.DeviceTypeTest.test_device_type_templates``
   for YAML syntax. This renders the template without a device dictionary and
   checks that the output is valid YAML. This test will fail with syntax errors
   in variables, jinja2 blocks, inheritance and whitespace indent errors.

#. Add a new unit test to the ``TestTemplates`` class in the same unit test
   file when any jinja2 template fails to parse. Change the ``DEBUG`` setting
   to ``True`` to see the rendered output and use the `Online YAML Parser
   <http://yaml-online-parser.appspot.com/?yaml=&type=json>`_ to identify the
   problems with the YAML output. Once the basic validation passes, add an
   initial device dictionary, following the examples and identify specific
   values in the output which can be asserted

#. Compare the output of the template with a realistic device dictionary, using
   the unit test, with the test YAML used when developing the underlying
   support. If this is a fix for an existing template, you can generate the
   relevant output on the master branch and verify against the changes in the
   local branch.

#. Completed templates need to be installed into
   ``/etc/lava-server/dispatcher-config/device-types/`` before testjobs can be
   submitted through XML-RPC. The ``lava-master`` daemon does **not** need to
   be restarted, the next submitted testjob will use the modified template(s).

.. seealso:: :ref:`adding_known_device`.

lava-dispatcher
***************

::

 $ python -m unittest discover lava_dispatcher/pipeline/

To run a single test, use the test class name as output by a failing test,
without the call to ``discover``::

 $ python -m unittest lava_dispatcher.pipeline.test.test_basic.TestPipelineInit.test_pipeline_init

 $ python -m unittest -v -c -f lava_dispatcher.pipeline.test.test_basic.TestPipelineInit.test_pipeline_init

The call references the path to the python module, the class and then the test
function within that class. To run all tests in a class, omit the function. To
run all tests in a file, omit the class and the function.

Sets of tests can also be executed from the :file:`./ci-run` script
of ``lava-dispatcher`` as well::

 $ ./ci-run --test-suite lava_dispatcher.pipeline.test.test_basic.TestPipelineInit.test_pipeline_init

Also, install the updated ``lava-dispatcher`` package and use it to inspect the
output of the pipeline using the ``--validate`` switch to ``lava-dispatch``::

 $ sudo lava-dispatch --validate --target ./devices/kvm01.yaml ./sample_jobs/kvm.yaml --output-dir=/tmp/test

.. note:: The refactoring has changed the behaviour of ``target`` - the value
   **must** be a path to a YAML file, not a hostname. This is because the
   refactored dispatcher has no local configuration, so the master sends the
   entire device configuration to the dispatcher as a single YAML file.

.. seealso:: :ref:`unit_tests` for information on running the full set of
   unit tests on ``lava-server`` and ``lava-dispatcher``.

The structure of any one job will be the same each time it is run (subject to
changes in the developing codebase). Each different job will have a different
pipeline structure. Do not rely on any of the pipeline levels have any specific
labels. When writing unit tests, only use checks based on ``isinstance`` or
``self.name``. (The description and summary fields are subject to change to
make the validation output easier to understand whereas ``self.name`` is a
strict class-based label.)

Sample pipeline description output
==================================

(Actual output is subject to frequent change.)

.. code-block:: yaml

 !!python/object/apply:collections.OrderedDict
 - - - device
    - parameters:
        actions:
          boot:
            prompts: ['linaro-test', 'root@debian:~#']
            command:
              amd64: {qemu_binary: qemu-system-x86_64}
            methods: [qemu]
            overrides: [boot_cmds, qemu_options]
            parameters:
              boot_cmds:
              - {root: /dev/sda1}
              - {console: 'ttyS0,115200'}
              machine: accel=kvm:tcg
              net: ['nic,model=virtio', user]
              qemu_options: [-nographic]
          deploy:
            methods: [image]
        architecture: amd64
        device_type: kvm
        hostname: kvm01
        memory: 512
        root_part: 1
  - - job
    - parameters: {action_timeout: 5m, device_type: kvm, job_name: kvm-pipeline, job_timeout: 15m,
        output_dir: /tmp/codehelp, priority: medium, target: kvm01, yaml_line: 3}
  - - '1'
    - content:
        description: deploy image using loopback mounts
        level: '1'
        name: deployimage
        parameters:
          deployment_data: &id001 {TESTER_PS1: 'linaro-test [rc=$(echo \$?)]# ', TESTER_PS1_INCLUDES_RC: true,
            TESTER_PS1_PATTERN: 'linaro-test \[rc=(\d+)\]# ', boot_cmds: boot_cmds,
            distro: debian, lava_test_dir: /lava-%s, lava_test_results_dir: /lava-%s,
            lava_test_results_part_attr: root_part, lava_test_sh_cmd: /bin/bash}
        summary: deploy image
        valid: true
        yaml_line: 12
      description: deploy image using loopback mounts
      summary: deploy image
  - - '1.1'
    - content:
        description: download with retry
        level: '1.1'
        max_retries: 5
        name: download_action
        parameters:
          deployment_data: *id001
        sleep: 1
        summary: download-retry
        valid: true
      description: download with retry
      summary: download-retry
  - - '1.2'
    - content:
        description: md5sum and sha256sum
        level: '1.2'
        name: checksum_action
        parameters:
          deployment_data: *id001
        summary: checksum
        valid: true
      description: md5sum and sha256sum
      summary: checksum
  - - '1.3'
    - content:
        description: mount with offset
        level: '1.3'
        name: mount_action
        parameters:
          deployment_data: *id001
        summary: mount loop
        valid: true
      description: mount with offset
      summary: mount loop
  - - 1.3.1
    - content:
        description: calculate offset of the image
        level: 1.3.1
        name: offset_action
        parameters:
          deployment_data: *id001
        summary: offset calculation
        valid: true
      description: calculate offset of the image
      summary: offset calculation
  - - 1.3.2
    - content:
        description: ensure a loop back mount operation is possible
        level: 1.3.2
        name: loop_check
        parameters:
          deployment_data: *id001
        summary: check available loop back support
        valid: true
      description: ensure a loop back mount operation is possible
      summary: check available loop back support
  - - 1.3.3
    - content:
        description: Mount using a loopback device and offset
        level: 1.3.3
        max_retries: 5
        name: loop_mount
        parameters:
          deployment_data: *id001
        retries: 10
        sleep: 10
        summary: loopback mount
        valid: true
      description: Mount using a loopback device and offset
      summary: loopback mount
  - - '1.4'
    - content:
        description: customise image during deployment
        level: '1.4'
        name: customise
        parameters:
          deployment_data: *id001
        summary: customise image
        valid: true
      description: customise image during deployment
      summary: customise image
  - - '1.5'
    - content:
        description: load test definitions into image
        level: '1.5'
        name: test-definition
        parameters:
          deployment_data: *id001
        summary: loading test definitions
        valid: true
      description: load test definitions into image
      summary: loading test definitions
  - - 1.5.1
    - content:
        description: apply git repository of tests to the test image
        level: 1.5.1
        max_retries: 5
        name: git-repo-action
        parameters:
          deployment_data: *id001
        sleep: 1
        summary: clone git test repo
        uuid: b32dd5ff-fb80-44df-90fb-5fbd5ab35fe5
        valid: true
        vcs_binary: /usr/bin/git
      description: apply git repository of tests to the test image
      summary: clone git test repo
  - - 1.5.2
    - content:
        description: apply git repository of tests to the test image
        level: 1.5.2
        max_retries: 5
        name: git-repo-action
        parameters:
          deployment_data: *id001
        sleep: 1
        summary: clone git test repo
        uuid: 200e83ef-bb74-429e-89c1-05a64a609213
        valid: true
        vcs_binary: /usr/bin/git
      description: apply git repository of tests to the test image
      summary: clone git test repo
  - - 1.5.3
    - content:
        description: overlay test support files onto image
        level: 1.5.3
        name: test-overlay
        parameters:
          deployment_data: *id001
        summary: applying LAVA test overlay
        valid: true
      description: overlay test support files onto image
      summary: applying LAVA test overlay
  - - '1.6'
    - content:
        default_fixupdict: {FAIL: fail, PASS: pass, SKIP: skip, UNKNOWN: unknown}
        default_pattern: (?P<test_case_id>.*-*)\s+:\s+(?P<result>(PASS|pass|FAIL|fail|SKIP|skip|UNKNOWN|unknown))
        description: add lava scripts during deployment for test shell use
        lava_test_dir: /usr/lib/python2.7/dist-packages/lava_dispatcher/lava_test_shell
        level: '1.6'
        name: lava-overlay
        parameters:
          deployment_data: *id001
        runner_dirs: [bin, tests, results]
        summary: overlay the lava support scripts
        valid: true
        xmod: 493
      description: add lava scripts during deployment for test shell use
      summary: overlay the lava support scripts
  - - '1.7'
    - content:
        description: unmount the test image at end of deployment
        level: '1.7'
        max_retries: 5
        name: umount
        parameters:
          deployment_data: *id001
        sleep: 1
        summary: unmount image
        valid: true
      description: unmount the test image at end of deployment
      summary: unmount image
  - - '2'
    - content:
        description: boot image using QEMU command line
        level: '2'
        name: boot_qemu_image
        parameters:
          parameters: {failure_retry: 2, media: tmpfs, method: kvm, yaml_line: 22}
        summary: boot QEMU image
        timeout: {duration: 30, name: boot_qemu_image}
        valid: true
        yaml_line: 22
      description: boot image using QEMU command line
      summary: boot QEMU image
  - - '2.1'
    - content:
        description: Wait for a shell
        level: '2.1'
        name: expect-shell-connection
        parameters:
          parameters: {failure_retry: 2, media: tmpfs, method: kvm, yaml_line: 22}
        summary: Expect a shell prompt
        valid: true
      description: Wait for a shell
      summary: Expect a shell prompt
  - - '3'
    - content:
        level: '3'
        name: test
        parameters:
          parameters:
            definitions:
            - {from: git, name: smoke-tests, path: ubuntu/smoke-tests-basic.yaml,
              repository: 'git://git.linaro.org/qa/test-definitions.git', yaml_line: 31}
            - {from: git, name: singlenode-basic, path: singlenode01.yaml, repository: 'git://git.linaro.org/people/neilwilliams/multinode-yaml.git',
              yaml_line: 39}
            failure_retry: 3
            name: kvm-basic-singlenode
            yaml_line: 27
        summary: test
        valid: true
      description: null
      summary: test
  - - '4'
    - content:
        level: '4'
        description: finish the process and cleanup
        name: finalize
        parameters:
          parameters: {}
        summary: finalize the job
        valid: true
      description: finish the process and cleanup
      summary: finalize the job

Provisos with the current codebase
----------------------------------

The code can be executed::

 $ sudo lava-dispatch --target kvm01 lava_dispatcher/pipeline/test/sample_jobs/kvm.yaml --output-dir=/tmp/test

* During development, there may be images left mounted at the end of the run.
  Always check the output of ``mount``.

* Files in ``/tmp/test`` are not removed at the start or end of a job as these
  would eventually form part of the result bundle and would also be in a
  per-job temporary directory (created by the scheduler). To be certain of what
  logs were created by each run, clear the directory each time.

Compatibility with the old dispatcher LavaTestShell
***************************************************

The hacks and workarounds in the old LavaTestShell classes may need to be
marked and retained until such time as either the new model replaces the old or
the bug can be fixed in both models. Whereas the submission schema, log file
structure and result bundle schema have thrown away any backwards
compatibility, LavaTestShell will need to at least attempt to retain
compatibility while improving the overall design and integrating the test shell
operations into the new classes.

Current possible issues include:

* ``testdef.yaml`` is hardcoded into ``lava-test-runner`` when this could be a
  parameter fed into the overlay from the VCS handlers.

* Dependent test definitions had special handling because certain YAML files
  had to be retained when the overlay was taken from the dispatcher and
  installed onto the device. This approach leads to long delays and the need to
  use wget on the device to apply the test definition overlay as a separate
  operation during LavaTestShell. The new classes should be capable of creating
  a complete overlay prior to the device being booted which allows for the
  entire VCS repo to be retained. This may change behaviour.

* If dependent test definitions use custom signal handlers, this may not work
  - it would depend on how the job parameters are handled by the new classes.

.. _retry_diagnostic:

Logical actions
***************

RetryAction subclassing
=======================

For a RetryAction to validate, the RetryAction subclass must be a wrapper class
around a new internal_pipeline to allow the RetryAction.run() function to
handle all of the retry functionality in one place.

An Action which needs to support ``failure_retry`` or which wants to use
RetryAction support internally, needs a new class added which derives from
RetryAction, sets a useful name, summary and description and defines a
populate() function which creates the internal_pipeline. The Action with the
customised run() function then gets added to the internal_pipeline of the
RetryAction subclass - without changing the inheritance of the original Action.

.. _diagnostic_actions:

Diagnostic subclasses
=====================

To add Diagnostics, add subclasses of DiagnosticAction to the list of supported
Diagnostic classes in the Job class. Each subclass must define a trigger
classmethod which is unique across all Diagnostic subclasses. (The trigger
string is used as an index in a generator hash of classes.) Trigger strings are
only used inside the Diagnostic class. If an Action catches a JobError or
InfrastructureError exception and wants to allow a specific Diagnostic class to
run, import the relevant Diagnostic subclass and add the trigger to the current
job inside the exception handling of the Action:

.. code-block:: python

 try:
   self._run_command(cmd_list)
 except JobError as exc:
   self.job.triggers.append(DiagnoseNetwork.trigger())
   raise JobError(exc)
 return connection

Actions should only append triggers which are relevant to the JobError or
InfrastructureError exception about to be raised inside an Action.run()
function. Multiple triggers can be appended to a single exception. The
exception itself is still raised (so that a RetryAction container will still
operate).

.. hint:: A DownloadAction which fails to download a file could
          append a DiagnosticAction class which runs ``ifconfig`` or
          ``route`` just before raising a JobError containing the
          404 message.

If the error to be diagnosed does not raise an exception, append the trigger in
a conditional block and emit a JobError or InfrastructureError exception with a
useful message.

Do not clear failed results of previous attempts when running a Diagnostic
class - the fact that a Diagnostic was required is an indication that the job
had some kind of problem.

Avoid overloading common Action classes with Diagnostics, add a new Action
subclass and change specific Strategy classes (Deployment, Boot, Test) to use
the new Action.

Avoid chaining Diagnostic classes - if a Diagnostic requires a command to
exist, it must check that the command does exist. Raise a RuntimeError if a
Strategy class leads to a Diagnostic failing to execute.

It is an error to add a Diagnostic class to any Pipeline. Pipeline Actions
should be restricted to classes which have an effect on the Test itself, not
simply reporting information.

.. _adjuvants:

Adjuvants - skipping actions and using helper actions
=====================================================

Sometimes, a particular test image will support the expected command but a
subsequent image would need an alternative. Generally, the expectation is that
the initial command should work, therefore the fallback or helper action should
not be needed. The refactoring offers support for this situation using
Adjuvants.

An Adjuvant is a helper action which exists in the normal pipeline but which is
normally skipped, unless the preceding Action sets a key in the PipelineContext
that the adjuvant is required. A successful operation of the adjuvant clears
the key in the context.

One example is the ``reboot`` command. Normal user expectation is that a
``reboot`` command as root will successfully reboot the device but LAVA needs
to be sure that a reboot actually does occur, so usually uses a hard reset PDU
command after a timeout. The refactoring allows LAVA to distinguish between a
job where the soft reboot worked and a job where the PDU command became
necessary, without causing the test itself to fail simply because the job
didn't use a hard reset.

If the ResetDevice Action determines that a reboot happened (by matching a
pexpect on the bootloader initialisation), then nothing happens and the
Adjuvant action (in this case, HardResetDevice) is marked in the results as
skipped. If the soft reboot fails, the ResetDevice Action marks this result as
failed but also sets a key in the PipelineContext so that the HardResetDevice
action then executes.

Unlike Diagnostics, Adjuvants are an integral part of the pipeline and show up
in the verification output and the results, whether executed or not. An
Adjuvant is not a simple retry, it is a different action, typically a more
aggressive or forced action. In an ideal world, the adjuvant would never be
required.

A similar situation exists with firmware upgrades. In this case, the adjuvant
is skipped if the firmware does not need upgrading. The preceding Action would
not be set as a failure in this situation but LAVA would still be able to
identify which jobs updated the firmware and which did not.

.. _connections_and_signals:

Connections, Actions and the SignalDirector
*******************************************

Most deployment Action classes run without needing a Connection. Once a
Connection is established, the Action may need to run commands over that
Connection. At this point, the Action delegates the maintenance of the run
function to the Connection pexpect. i.e. the Action.run() is blocked, waiting
for Connection.run_command() (or similar) to return and the Connection needs to
handle timeouts, signals and other interaction over the connection. This role
is taken on by the internal SignalDirector within each Connection. Unlike the
old model, Connections have their own directors which takes the multinode and
LMP workload out of the singlenode operations.

.. _detecting_power_state:

Detecting power state
=====================

Devices on your desk can behave differently to those in the lab under full
automation. Under automation, the ``hard_reset`` and ``power_off`` support
means that the device is likely to be powered off when the first connection
atttempt is made. On the desk, the device may spend more time powered on (even
if the device is not running a usable system, for example the NFS location will
be deleted when the previous job ends). So when writing connection classes and
actions which initiate connections, check the power state of the device first.

#. An Action initiating a connection needs to know if it should wait for a
   prompt. In the run function, add::

     if self.job.device.power_state not in ['on', 'off']:
         self.wait(connection)

#. The next Action should be a ResetDevice action which understands the power
   state and determines whether to call the ``hard_reset`` commands or to
   attempt a soft reboot. In the populate function, ensure the correct ordering
   is in place::

     self.internal_pipeline.add_action(MenuConnect())
     self.internal_pipeline.add_action(ResetDevice())

#. Warn if the device has no automation support in the validate function::

    if self.job.device.power_state in ['on', 'off']:
        # to enable power to a device, either power_on or hard_reset are needed.
        if self.job.device.power_command is '':
            self.errors = "Unable to power on or reset the device %s" % hostname
        if self.job.device.connect_command is '':
            self.errors = "Unable to connect to device %s" % hostname
    else:
        self.logger.warning("%s may need manual intervention to reboot" % hostname)

.. index:: power commands

.. _power_commands:

Power Commands
==============

Some devices need a sequence of commands to change power state, some may
require a ``sleep`` or similar delay. The power commands available in the
:term:`device dictionary` support two uses:

Simple string
-------------

This is the simplest form and is recommended for the majority of devices.

.. code-block:: jinja

 {% set hard_reset_command = '/usr/bin/pduclient --daemon tweetypie --hostname pdu --command reboot --port 08' %}

Simple list
-----------

It can be useful to have a short list of simple commands, e.g. during device
integration. In the final file used in the device dictionary, the entire list
must be on a single line.

.. code-block:: jinja

 {% set hard_reset_command = ['/usr/local/lab-scripts/snmp_pdu_control --hostname pdu14 --command reboot --port 5 --delay 20', '/usr/local/lab-scripts/eth008_control -a 10.0.9.2 -r 3 -s onoff'] %}

.. note:: Extending the list support to more than a simple list of sequential
   commands is **not supported** and there is also **no support** for shell
   operators like ``&&`` or ``||``. Any device which needs something more
   complex **must** have custom scripts made available on the worker which
   can do all the conditionals and logic. A script will also make the device
   dictionary more readable.

Using connections
=================

Construct your pipeline to use Actions in the order:

* Prepare any overlays or commands or context data required later
* Start a new connection
* Issue the command which changes device state
* Wait for the specified prompt on the new connection
* Issue the commands desired over the new connection

.. note:: There may be several Retry actions necessary within these
          steps.

So, for a U-Boot operation, this results in a pipeline like:

* UBootCommandOverlay - substitutes dynamic and device-specific data into the
  U-Boot command list specified in the device configuration.

* ConnectDevice - establishes a serial connection to the device, as specified
  by the device configuration

* UBootRetry - wraps the subsequent actions in a retry

* UBootInterrupt - sets the ``Hit any key`` prompt in a new connection

* ResetDevice - sends the reboot command to the device

* ExpectShellSession - waits for the specified prompt to match

* UBootCommandsAction - issues the commands to U-Boot

.. _starting_connections:

Starting a connection
---------------------

Typically, a Connection is started by an Action within the Pipeline. The call
to start a Connection must not return until all operations on that Connection
are complete or the Pipeline determines that the Connection needs to be
terminated.

Using debug logs
****************

The refactored dispatcher has a different approach to logging:

#. **all** logs are structured using YAML
#. Actions log to discrete log files
#. Results are logged for each action separately
#. Log messages use appropriate YAML syntax.
#. Messages received from the device are prefixed with ``target``.
#. YAML wrapping handled by the dedicated logger. Always use
   ``self.logger.<LEVEL>`` in an action.

Examples
========

Actual representation of the logs in the UI will change - these examples are
the raw content of the output YAML.

.. code-block:: yaml

 - {debug: 'start: 1.4.2.3.7 test-install-overlay (max 300s)', ts: '2015-09-07T09:40:46.720450'}
 - {debug: 'test-install-overlay duration: 0.02', ts: '2015-09-07T09:40:46.746036'}
 - results:
     test-install-overlay: !!python/object/apply:collections.OrderedDict
     - - [success, a9b2300d-0864-4f9c-ba78-c2594b567fc5]
       - [skipped, a9b2300d-0864-4f9c-ba78-c2594b567fc5]
       - [duration, 0.024679899215698242]
       - [timeout, 300.0]
       - [level, 1.4.2.3.7]

.. code-block:: yaml

 - {debug: 'Received signal: <STARTTC> linux-linaro-ubuntu-pwd'}
 - {target: ''}
 - {target: ''}
 - {target: ''}
 - {target: ''}
 - {debug: 'test shell timeout: 300 seconds'}
 - {target: ''}
 - {target: /lava-None/tests/0_smoke-tests}
 - {target: <LAVA_SIGNAL_ENDTC linux-linaro-ubuntu-pwd>}
 - {target: <LAVA_SIGNAL_TESTCASE TEST_CASE_ID=linux-linaro-ubuntu-pwd RESULT=pass>}
 - {target: <LAVA_SIGNAL_STARTTC linux-linaro-ubuntu-uname>}
 - {target: ''}
 - {debug: 'Received signal: <ENDTC> linux-linaro-ubuntu-pwd'}
 - {target: ''}
 - {target: ''}
 - {target: ''}
 - {target: ''}
 - {debug: 'test shell timeout: 300 seconds'}
 - {debug: 'Received signal: <TESTCASE> TEST_CASE_ID=linux-linaro-ubuntu-pwd RESULT=pass'}
 - {debug: 'res: {''test_case_id'': ''linux-linaro-ubuntu-pwd'', ''result'': ''pass''}
     data: {''test_case_id'': ''linux-linaro-ubuntu-pwd'', ''result'': ''pass''}'}
 - results: {linux-linaro-ubuntu-pwd: pass, testsuite: smoke-tests-basic}

.. code-block:: yaml

 - {info: 'ok: lava_test_shell seems to have completed'}
 - debug: {curl-http: pass, direct-install: pass, direct-update: pass, linux-linaro-ubuntu-ifconfig: pass,
     linux-linaro-ubuntu-ifconfig-dump: pass, linux-linaro-ubuntu-lsb_release: fail,
     linux-linaro-ubuntu-lscpu: pass, linux-linaro-ubuntu-netstat: pass, linux-linaro-ubuntu-pwd: pass,
     linux-linaro-ubuntu-route-dump-a: pass, linux-linaro-ubuntu-route-dump-b: pass,
     linux-linaro-ubuntu-route-ifconfig-up: pass, linux-linaro-ubuntu-route-ifconfig-up-lo: pass,
     linux-linaro-ubuntu-uname: pass, linux-linaro-ubuntu-vmstat: pass, ping-test: pass,
     remove-tgz: pass, tar-tgz: pass}
 - {debug: 'lava-test-shell duration: 26.88', ts: '2015-09-07T09:43:14.065956'}

.. index:: developer debugging slaves

.. _debugging_slaves:

Debugging on the slave dispatcher
*********************************

Pipeline jobs are sent to the slave dispatcher over ZMQ as fully formatted YAML
files but are then deleted when the test job ends.

Equivalent files can be prepared using the ``lava-server manage
device-dictionary`` ``review`` option to output the device configuration YAML.
To re-run the job on the slave, pass this configuration as the ``--target``
option to ``lava-dispatch`` and specify a temporary ``--output-dir`` and the
test job definition.

.. note:: MultiNode test jobs produce a specific test job for each node in the
   group. The original MultiNode definition **cannot** be executed by
   ``lava-dispatch`` on the command line and the job definition for a single
   node within a MultiNode group will also need editing before it can be run
   without reference to the other nodes.

.. index:: developer: adding new classes

.. _adding_new_classes:

Adding new classes
******************

See also :ref:`mapping_yaml_to_code`:

The expectation is that new tasks for the dispatcher will be created by adding
more specialist Actions and organising the existing Action classes into a new
pipeline for the new task.

Adding new behaviour is a two step process:

- always add a new Action, usually with an internal pipeline, to implement the
  new behaviour

- add a new Strategy class which creates a suitable pipeline to use that
  Action.

A Strategy class may use conditionals to select between a number of top level
Strategy Action classes, for example ``DeployImageAction`` is a top level
Strategy Action class for the DeployImage strategy. If used, this conditional
**must only operate on job parameters and the device** as the selection
function is a ``classmethod``.

A test Job will consist of multiple strategies, one for each of the listed
*actions* in the YAML file. Typically, this may include a Deployment strategy,
a Boot strategy and a Test strategy. Jobs can have multiple deployment, boot,
or test actions. Strategies add top level Actions to the main pipeline in the
order specified by the parser. For the parser to select the new strategy, the
``strategies.py`` module for the relevant type of action needs to import the
new subclass. There should be no need to modify the parser itself.

A single top level Strategy Action implements a single strategy for the outer
Pipeline. The use of :ref:`retry_diagnostic` can provide sufficient complexity
without adding conditionals to a single top level Strategy Action class. Image
deployment actions will typically include a conditional to check if a Test
action is required later so that the test definitions can be added to the
overlay during deployment.

Re-use existing Action classes wherever these can be used without changes.

If two or more Action classes have very similar behaviour, re-factor to make a
new base class for the common behaviour and retain the specialised classes.

Strategy selection via select() must only ever rely on the device and the job
parameters. Add new parameters to the job to distinguish strategies, e.g. the
boot method or deployment method.

#. A Strategy class is simply a way to select which top level Action class is
   instantiated.

#. A top level Action class creates an internal pipeline in ``populate()``

   * Actions are added to the internal pipeline to do the rest of the work

#. a top level Action will generally have a basic ``run()`` function which
   calls ``run_actions`` on the internal pipeline.

#. Ensure that the ``accepts`` routine can uniquely identify this strategy
without interfering with other strategies. (:ref:`new_classes_unit_test`)

#. Respect the existing classes - reuse wherever possible and keep all classes
   as pure as possible. There should be one class for each type of operation
   and no more, so to download a file onto the dispatcher use the
   DownloaderAction whether that is an image or a dtb. If the existing class
   does not do everything required, inherit from it and add functionality.

#. Respect the directory structure - a strategies module should not need to
   import anything from outside that directory. Keep modules together with
   modules used in the same submission YAML stanza.

#. Expose all configuration in the YAML, not python. There are FIXMEs in the
   code to remedy situations where this is not yet happening but avoid adding
   code which makes this problem worse. Extend the device or submission YAML
   structure if new values are needed.

#. Take care with YAML structure. Always check your YAML changes in the online
   YAML parser as this often shows where a simple hyphen can dramatically
   change the complexity of the data.

#. Cherry-pick existing classes alongside new classes to create new pipelines
   and keep all Action classes to a single operation.

#. Code defensively:

   #. check that parameters exist in validation steps.
   #. call super() on the base class validate() in each Action.validate()
   #. handle missing data in the dynamic context
   #. use cleanup() and keep actions idempotent.

.. _new_classes_unit_test:

Always add unit tests for new classes
=====================================

Wherever a new class is added, that new class can be tested - if only to be
sure that it is correctly initialised and added to the pipeline at the correct
level. Always create a new file in the tests directory for new functionality.
All unit tests need to be in a file with the ``test_`` prefix and add a new
YAML file to the sample_jobs so that the strategies to select the new code can
be tested. See :ref:`yaml_job`.

Often the simplest way to understand the available parameters and how new
statements in the device configuration or job submission show up inside the
classes is to use a unit test. To run a single unit-test, for example
test_function in a class called TestExtra in a file called test_extra.py, use::

 $ python -m unittest -v -c -f lava_dispatcher.pipeline.test.test_extra.TestExtra.test_function

Example python code:

.. code-block:: python

 import os
 import unittest

 class TestExtra(unittest.TestCase):  # pylint: disable=too-many-public-methods

    def test_function(self):
        print "Hello world"

Group similar operations
========================

When using a connection to a device, group calls over that connection to calls
which are expected to return within a consistent timeout for that class. If the
final command from the class starts a longer running process, e.g. boot, set
the connection prompt to look for a message which will be seen on that
connection within a similar timeframe to all the other calls made by that
class. This allows test writers to correctly choose the timeout to extend.

Add documentation
=================

Add to the documentation when adding new classes which implement new dispatcher
actions, parameters or behaviour.

Online YAML checker
===================

http://yaml-online-parser.appspot.com/

Use syntax checkers during the refactoring
==========================================

::

 $ sudo apt install pylint
 $ pylint -d line-too-long -d missing-docstring lava_dispatcher/pipeline/

Use class analysis tools
========================

::

 $ sudo apt install graphviz
 $ pyreverse lava_dispatcher/pipeline/
 $ dot -Tpng classes_No_Name.dot > classes.png

(Actual images can be very large.)

Use memory analysis tools
=========================

* http://jam-bazaar.blogspot.co.uk/2009/11/memory-debugging-with-meliae.html
* http://jam-bazaar.blogspot.co.uk/2010/08/step-by-step-meliae.html

::

 $ sudo apt install python-meliae

Add this python snippet to a unit test or part of the code of interest:

.. code-block:: python

 from meliae import scanner
 scanner.dump_all_objects('filename.json')

Once the test has run, the specified filename will exist. To analyse
the results, start up a python interactive shell in the same directory::

 $ python

.. code-block:: python

 >>> from meliae import loader
 >>> om = loader.load('filename.json')
 loaded line 64869, 64870 objs,   8.7 /   8.7 MiB read in 0.9s
 checked    64869 /    64870 collapsed     5136
 set parents    59733 /    59734
 collapsed in 0.4s
 >>> s = om.summarize(); s

.. note:: The python interpreter, the ``setup.py`` configuration and other
   tools may allocate memory as part of the test, so the figures in the output
   may be larger than it would seem for a small test. A basic test may give a
   summary of 12Mb, total size. Figures above 100Mb should prompt a check on
   what is using the extra memory.

Pre-boot deployment manipulation
********************************

.. note:: These provisions are under development and are likely to change
   substantially. e.g. it may be possible to do a lot of these tasks using
   secondary media and secondary connections.

There are several situations where an environment needs to be setup in a
contained and tested manner and then used for one or multiple LAVA test
operations.

One solution is to use MultiNode and this works well when the device under test
supports a secondary connection, e.g. ethernet.

MultiNode has requirements on a POSIX-type command line shell to be able to
pass messages, e.g. busybox.

QEMU tests involve downloading a pre-built chroot based on a stable
distribution release of a foreign architecture and running tests inside that
chroot.

Android tests may involve setting up a VM or a configured chroot to expose USB
devices while retaining the ability to use different versions of tools for
different tests.
