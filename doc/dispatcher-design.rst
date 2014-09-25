.. _dispatcher_design:

Lava Dispatcher Design
**********************

The new dispatcher design is intended to make it easier to adapt the
dispatcher flow to new boards, new mechanisms and new deployments.

.. note:: The new code is still developing, some areas are absent,
          some areas will change substantially before it will work.
          All details here need to be seen only as examples and the
          specific code may well change independently.

Start with a Job which is broken up into a Deployment, a Boot, a Test
and a Submit class:

+-------------+--------------------+------------------+-------------------+
|     Job     |                    |                  |                   |
+=============+====================+==================+===================+
|             |     Deployment     |                  |                   |
+-------------+--------------------+------------------+-------------------+
|             |                    |   DeployAction   |                   |
+-------------+--------------------+------------------+-------------------+
|             |                    |                  |  DownloadAction   |
+-------------+--------------------+------------------+-------------------+
|             |                    |                  |  ChecksumAction   |
+-------------+--------------------+------------------+-------------------+
|             |                    |                  |  MountAction      |
+-------------+--------------------+------------------+-------------------+
|             |                    |                  |  CustomiseAction  |
+-------------+--------------------+------------------+-------------------+
|             |                    |                  |  TestDefAction    |
+-------------+--------------------+------------------+-------------------+
|             |                    |                  |  UnmountAction    |
+-------------+--------------------+------------------+-------------------+
|             |                    |   BootAction     |                   |
+-------------+--------------------+------------------+-------------------+
|             |                    |   TestAction     |                   |
+-------------+--------------------+------------------+-------------------+
|             |                    |   SubmitAction   |                   |
+-------------+--------------------+------------------+-------------------+

The Job manages the Actions using a Pipeline structure. Actions
can specialise actions by using internal pipelines and an Action
can include support for retries and other logical functions:

+------------------------+----------------------------+
|     DownloadAction     |                            |
+========================+============================+
|                        |    HttpDownloadAction      |
+------------------------+----------------------------+
|                        |    FileDownloadAction      |
+------------------------+----------------------------+

If a Job includes one or more Test definitions, the Deployment can then
extend the Deployment to overlay the LAVA test scripts without needing
to mount the image twice:

+----------------------+------------------+---------------------------+
|     DeployAction     |                  |                           |
+======================+==================+===========================+
|                      |   OverlayAction  |                           |
+----------------------+------------------+---------------------------+
|                      |                  |   MultinodeOverlayAction  |
+----------------------+------------------+---------------------------+
|                      |                  |   LMPOverlayAction        |
+----------------------+------------------+---------------------------+

The TestDefinitionAction has a similar structure with specialist tasks
being handed off to cope with particular tools:

+--------------------------------+-----------------+-------------------+
|     TestDefinitionAction       |                 |                   |
+================================+=================+===================+
|                                |    RepoAction   |                   |
+--------------------------------+-----------------+-------------------+
|                                |                 |   GitRepoAction   |
+--------------------------------+-----------------+-------------------+
|                                |                 |   BzrRepoAction   |
+--------------------------------+-----------------+-------------------+
|                                |                 |   TarRepoAction   |
+--------------------------------+-----------------+-------------------+
|                                |                 |   UrlRepoAction   |
+--------------------------------+-----------------+-------------------+

Following the code flow
=======================

+-------------------------------------+---------------------------------------------+
|           Filename                  |   Role                                      |
+=====================================+=============================================+
| lava/dispatcher/commands.py         | Command line arguments, call to YAML parser |
+-------------------------------------+---------------------------------------------+
| lava_dispatcher/pipeline/parser.py  | YAML Parser to create the Job               |
+-------------------------------------+---------------------------------------------+
| ....pipeline/job_actions/deploy/    | Handlers for different deployment stages    |
+-------------------------------------+---------------------------------------------+

The deployment is determined from the device_type specified in the Job
(or the device_type of the specified target) by reading the list of
support methods from the device_types YAML configuration.

.. code-block:: yaml

 actions:
   deploy:
     allow:
       - image
   boot:
     allow:
       - image

This then matches the python class structure::

 actions/
    deploy/
        image.py

The class defines the list of Action classes needed to implement this
deployment.

Testing the new design
======================

To test the new design, use the increasing number of unit tests::

 $ python -m unittest discover lava_dispatcher/pipeline/

Also, install the updated ``lava-dispatcher`` package and use it to
inspect the output of the pipeline using the ``--validate`` switch to
``lava-dispatch``::

 $ sudo lava-dispatch --validate --target kvm01 lava_dispatcher/pipeline/test/sample_jobs/kvm.yaml --output-dir=/tmp/test

The structure of any one job will be the same each time it is run (subject
to changes in the developing codebase). Each different job will have a
different pipeline structure. Do not rely on any of the pipeline levels
have any specific labels. When writing unit tests, only use checks based
on ``isinstance`` or ``self.name``. (The description and summary fields
are subject to change to make the validation output easier to understand
whereas ``self.name`` is a strict class-based label.)

Sample pipeline description output
----------------------------------

(Actual output is subject to frequent change.)

.. code-block:: yaml

 !!python/object/apply:collections.OrderedDict
 - - - device
    - parameters:
        actions:
          boot:
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
        test_image_prompts: [\(initramfs\), linaro-test, '/ #', root@android, root@linaro,
          root@master, root@debian, 'root@linaro-nano:~#', 'root@linaro-developer:~#',
          'root@linaro-server:~#', 'root@genericarmv7a:~#', 'root@genericarmv8:~#']
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
        name: submit_results
        parameters:
          parameters: {stream: /anonymous/codehelp/, yaml_line: 44}
        summary: submit_results
        valid: true
      description: null
      summary: submit_results
  - - '5'
    - content:
        description: finish the process and cleanup
        level: '5'
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

* There is a developer shortcut which uses ``/tmp/`` to store the downloaded
  image instead of a fresh ``mkdtemp`` each time. This saves re-downloading
  the same image but as the image is modified in place, a second run using
  the image will fail.
  * Either change the YAML locally to refer to a ``file://``
    URL and comment out the developer shortcut or copy a decompressed image
    over the modified one in ``tmp`` before each run.
* During development, there may also be images left mounted at the end of
  the run. Always check the output of ``mount``.
* Files in ``/tmp/test`` are not removed at the start or end of a job as
  these would eventually form part of the result bundle and would also be
  in a per-job temporary directory (created by the scheduler). To be certain
  of what logs were created by each run, clear the directory each time.

Compatibility with the old dispatcher LavaTestShell
===================================================

The hacks and workarounds in the old LavaTestShell classes may need to
be marked and retained until such time as either the new model replaces
the old or the bug can be fixed in both models. Whereas the submission
schema, log file structure and result bundle schema have thrown away any
backwards compatibility, LavaTestShell will need to at least attempt to
retain compatibility whilst improving the overall design and integrating
the test shell operations into the new classes.

Current possible issues include:

* ``testdef.yaml`` is hardcoded into ``lava-test-runner`` when this could
  be a parameter fed into the overlay from the VCS handlers.
* Dependent test definitions had special handling because certain YAML
  files had to be retained when the overlay was taken from the dispatcher
  and installed onto the device. This approach leads to long delays and
  the need to use wget on the device to apply the test definition overlay
  as a separate operation during LavaTestShell. The new classes should
  be capable of creating a complete overlay prior to the device being
  booted which allows for the entire VCS repo to be retained. This may
  change behaviour.
  * If dependent test definitions use custom signal handlers, this may
    not work - it would depend on how the job parameters are handled
    by the new classes.

Connections, Actions and the SignalDirector
===========================================

Most deployment Action classes run without needing a Connection. Once a
Connection is established, the Action may need to run commands over that
Connection. At this point, the Action delegates the maintenance of
the run function to the Connection pexpect. i.e. the Action.run() is
blocked, waiting for Connection.run_command() (or similar) to return
and the Connection needs to handle timeouts, signals and other interaction
over the connection. This role is taken on by the internal SignalDirector
within each Connection. Unlike the old model, Connections have their
own directors which takes the multinode and LMP workload out of the
singlenode operations.

Adding new classes
==================

The expectation is that new tasks for the dispatcher will be created
by adding more specialist Actions and organising the existing Action
classes into a new pipeline for the new task.

Always add unit tests for new classes
-------------------------------------

Wherever a new class is added, that new class can be tested - if only
to be sure that it is correctly initialised and added to the pipeline
at the correct level.

Online YAML checker
-------------------

http://yaml-online-parser.appspot.com/

Use syntax checkers during the refactoring
------------------------------------------

::

 $ sudo apt install pylint
 $ pylint -d line-too-long -d missing-docstring lava_dispatcher/pipeline/

Use class analysis tools
------------------------

::

 $ sudo apt install graphviz
 $ pyreverse lava_dispatcher/pipeline/
 $ dot -Tpng classes_No_Name.dot > classes.png

(Actual images can be very large.)

Pre-boot deployment manipulation
================================

There are several situations where an environment needs to be setup in
a contained and tested manner and then used for one or multiple LAVA
test operations.

One solution is to use MultiNode and this works well when the device
under test supports a secondary connection, e.g. ethernet.

MultiNode has requirements on a POSIX-type command line shell to be
able to pass messages, e.g. busybox.

QEMU tests involve downloading a pre-built chroot based on a stable
distribution release of a foreign architecture and running tests inside
that chroot.

Android tests may involve setting up a VM or a configured chroot to
expose USB devices whilst retaining the ability to use different
versions of tools for different tests.
