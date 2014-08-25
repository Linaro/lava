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

Sample pipeline description output
----------------------------------

.. code-block:: yaml

 !!python/object/apply:collections.OrderedDict
 - - - '1'
    - content: {description: deploy kvm top level action, level: '1', name: deploykvm,
        parameters: '{"to": "tmpfs", "timeout": "20m", "yaml_line": 13, "image": "http://images.validation.linaro.org/kvm-debian-wheezy.img.gz",
          "os": "debian", "root_partition": 1}', summary: deploy kvm, valid: true,
        yaml_line: 13}
      description: deploy kvm top level action
      summary: deploy kvm
  - - '1.1'
    - content: {description: download with retry, level: '1.1', max_retries: 5, name: download_action,
        parameters: '{"image": "http://images.validation.linaro.org/kvm-debian-wheezy.img.gz",
          "to": "tmpfs", "timeout": "20m", "yaml_line": 13, "os": "debian", "root_partition":
          1}', sleep: 1, summary: download-retry, valid: true}
      description: download with retry
      summary: download-retry
  - - '1.2'
    - content: {description: md5sum and sha256sum, level: '1.2', name: checksum_action,
        parameters: '{"image": "http://images.validation.linaro.org/kvm-debian-wheezy.img.gz",
          "to": "tmpfs", "timeout": "20m", "yaml_line": 13, "os": "debian", "root_partition":
          1}', summary: checksum, valid: true}
      description: md5sum and sha256sum
      summary: checksum
  - - '1.3'
    - content: {description: mount with offset, level: '1.3', name: mount_action,
        parameters: '{"image": "http://images.validation.linaro.org/kvm-debian-wheezy.img.gz",
          "to": "tmpfs", "timeout": "20m", "yaml_line": 13, "os": "debian", "root_partition":
          1}', summary: mount loop, valid: true}
      description: mount with offset
      summary: mount loop
  - - 1.3.1
    - content: {description: calculate offset of the image, level: 1.3.1, name: offset_action,
        parameters: '{"image": "http://images.validation.linaro.org/kvm-debian-wheezy.img.gz",
          "to": "tmpfs", "timeout": "20m", "yaml_line": 13, "os": "debian", "root_partition":
          1}', summary: offset calculation, valid: true}
      description: calculate offset of the image
      summary: offset calculation
  - - 1.3.2
    - content: {description: ensure a loop back mount operation is possible, level: 1.3.2,
        name: loop_check, parameters: '{"image": "http://images.validation.linaro.org/kvm-debian-wheezy.img.gz",
          "to": "tmpfs", "timeout": "20m", "yaml_line": 13, "os": "debian", "root_partition":
          1}', summary: check available loop back support, valid: true}
      description: ensure a loop back mount operation is possible
      summary: check available loop back support
  - - 1.3.3
    - content: {description: Mount using a loopback device and offset, level: 1.3.3,
        max_retries: 5, name: loop_mount, parameters: '{"image": "http://images.validation.linaro.org/kvm-debian-wheezy.img.gz",
          "to": "tmpfs", "timeout": "20m", "yaml_line": 13, "os": "debian", "root_partition":
          1}', retries: 10, sleep: 10, summary: loopback mount, valid: true}
      description: Mount using a loopback device and offset
      summary: loopback mount
  - - '1.4'
    - content: {description: customise image during deployment, level: '1.4', name: customise,
        parameters: '{"image": "http://images.validation.linaro.org/kvm-debian-wheezy.img.gz",
          "to": "tmpfs", "timeout": "20m", "yaml_line": 13, "os": "debian", "root_partition":
          1}', summary: customise image, valid: true}
      description: customise image during deployment
      summary: customise image
  - - '1.5'
    - content: {description: load test definitions into image, level: '1.5', name: test-definition,
        parameters: '{"image": "http://images.validation.linaro.org/kvm-debian-wheezy.img.gz",
          "to": "tmpfs", "timeout": "20m", "yaml_line": 13, "test": {"failure_retry":
          3, "definitions": [{"path": "ubuntu/smoke-tests-basic.yaml", "from": "git",
          "name": "smoke-tests", "repository": "git://git.linaro.org/qa/test-definitions.git",
          "yaml_line": 32}, {"path": "singlenode01.yaml", "from": "git", "name": "singlenode-basic",
          "repository": "git://git.linaro.org/people/neilwilliams/multinode-yaml.git",
          "yaml_line": 40}], "name": "kvm-basic-singlenode", "yaml_line": 28}, "os":
          "debian", "root_partition": 1}', summary: loading test definitions, valid: true}
      description: load test definitions into image
      summary: loading test definitions
  - - 1.5.1
    - content: {description: apply git repository of tests to the test image, level: 1.5.1,
        max_retries: 5, name: git-repo-action, parameters: '{"from": "git", "name":
          "smoke-tests", "repository": "git://git.linaro.org/qa/test-definitions.git",
          "image": "http://images.validation.linaro.org/kvm-debian-wheezy.img.gz",
          "to": "tmpfs", "timeout": "20m", "yaml_line": 13, "test": {"failure_retry":
          3, "definitions": [{"path": "ubuntu/smoke-tests-basic.yaml", "from": "git",
          "name": "smoke-tests", "repository": "git://git.linaro.org/qa/test-definitions.git",
          "yaml_line": 32}, {"path": "singlenode01.yaml", "from": "git", "name": "singlenode-basic",
          "repository": "git://git.linaro.org/people/neilwilliams/multinode-yaml.git",
          "yaml_line": 40}], "name": "kvm-basic-singlenode", "yaml_line": 28}, "path":
          "ubuntu/smoke-tests-basic.yaml", "os": "debian", "root_partition": 1}',
        sleep: 1, summary: clone git test repo, valid: true, vcs_binary: /usr/bin/git}
      description: apply git repository of tests to the test image
      summary: clone git test repo
  - - 1.5.2
    - content: {description: apply git repository of tests to the test image, level: 1.5.2,
        max_retries: 5, name: git-repo-action, parameters: '{"from": "git", "name":
          "singlenode-basic", "repository": "git://git.linaro.org/people/neilwilliams/multinode-yaml.git",
          "image": "http://images.validation.linaro.org/kvm-debian-wheezy.img.gz",
          "to": "tmpfs", "timeout": "20m", "yaml_line": 13, "test": {"failure_retry":
          3, "definitions": [{"path": "ubuntu/smoke-tests-basic.yaml", "from": "git",
          "name": "smoke-tests", "repository": "git://git.linaro.org/qa/test-definitions.git",
          "yaml_line": 32}, {"path": "singlenode01.yaml", "from": "git", "name": "singlenode-basic",
          "repository": "git://git.linaro.org/people/neilwilliams/multinode-yaml.git",
          "yaml_line": 40}], "name": "kvm-basic-singlenode", "yaml_line": 28}, "path":
          "singlenode01.yaml", "os": "debian", "root_partition": 1}', sleep: 1, summary: clone
          git test repo, valid: true, vcs_binary: /usr/bin/git}
      description: apply git repository of tests to the test image
      summary: clone git test repo


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
