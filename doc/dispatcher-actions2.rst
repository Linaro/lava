.. _new_dispatcher_actions:

Refactored Dispatcher Actions
#############################

The refactored dispatcher uses a Pipeline structure, see
:ref:`pipeline_construction`. Actions can have internal pipelines
containing more actions. Actions are selected for a particular job
using a Strategy (see :ref:`using_strategy_classes`) which uses the
parameters in the job submission and the device configuration to build
the top level pipeline.

The refactored dispatcher does not make assumptions or guesses - if the
job submission does not specify a piece of data, that piece of data will
not be available to the pipeline. This may cause the job submission to
be rejected if one or more Actions selected by the Strategy require
this information. See :ref:`keep_dispatcher_dumb`.

Dispatcher Actions
******************

Job submissions for the refactored dispatcher use YAML and can create
a pipeline of actions based on five basic types. Parameters in the YAML
and in the device configuration are used to select the relevant Strategy
for the job and this determines which actions are added to the pipeline.

In addition, the job has some general parameters, including a job name
and :ref:`dispatcher_timeouts`.

.. _deploy_action:

Deploy
******

Many deployment strategies will run on the dispatcher. As such, these
actions may contain commands which cannot be overridden in the job. See
:ref:`essential_components`.

In general, the deployments do not modify the downloaded files. Where
the LAVA scripts and test definitions need to be added, these are first
prepared as a standalone tarball which is also retained within the final
job data and is available for download later. Exceptions include specific
requirements of bootloaders (like u-boot) to have a bootloader-specific
header on a ramdisk to which LAVA needs to add the LAVA extensions.

* Download files required by the job to the dispatcher, decompressing
  only if requested.
* Prepare a LAVA extensions tarball containing the test definitions and
  LAVA API scripts, only if a :ref:`test_action` action is defined.
* Depending on the deployment, apply the LAVA extensions tarball to the
  deployment.
* Deploy does not support repeat blocks but does support :ref:`failure_retry`.

Parameters
==========

Every deployment **must** specify a ``to`` parameter. This value is then
used to select the appropriate Strategy class for the deployment which,
in turn, will require other parameters to provide the data on how to
deploy to the requested location.

* **to**

  * **tmpfs**: Used to support QEMU device types which run on a dispatcher.
    The file is downloaded to a temporary directory and made available as
    an image to a predetermined QEMU command line::

     to: tmpfs

    * Requires an ``image`` parameter::

        image: http://images.validation.linaro.org/kvm-debian-wheezy.img.gz

    * The operating system of the image **must** be specified so that the
      LAVA scripts can install packages and identify other defaults in the
      deployment data. Supported values are ``android``, ``ubuntu``,
      ``debian`` or ``oe``::

        os: debian

    * If the image is compressed, the compression method **must** be
      specified if any ``test`` actions are defined in the job. Supported
      values are ``gz``, ``bz2`` and ``xz``::

       compression: gz

  * **tftp**: Used to support TFTP deployments, e.g. using UBoot. Files
    are downloaded to a temporary directory in the TFTP tree and the
    filenames are substituted into the bootloader commands specified in
    the device configuration or overridden in the job. The files to
    download typically include a kernel but can also include any file
    which the substitution commands need for this deployment. URL support
    is handled by the python ``requests`` module.

    ::

     to: tftp

    * **kernel** - in an appropriate format to what the commands require::

       kernel: http://images.validation.linaro.org/functional-test-images/bbb/zImage

    * **dtb** - in an appropriate format to what the commands require::

       dtb: http://images.validation.linaro.org/functional-test-images/bbb/am335x-bone.dtb

    * **ramdisk** - in an appropriate format to what the commands require.
      If a UBoot header is required, it **must** have already been added
      prior to download and the ``ramdisk-type: u-boot`` option added.
      The original header is removed before unpacking so that the LAVA
      scripts can be overlaid and the header replaced::

       ramdisk: http://images.validation.linaro.org/functional-test-images/common/linaro-image-minimal-initramfs-genericarmv7a.cpio.gz.u-boot
       ramdisk-type: u-boot

    * **nfsrootfs** - **must** be a tarball and supports either ``gz`` or
      ``bz2`` compression using the standard python ``tarfile`` support. The
      NFS is unpacked into a temporary directory onto the dispatcher in a
      location supported by NFS exports::

       nfsrootfs: http://images.validation.linaro.org/debian-jessie-rootfs.tar.gz

    * **os** -  The operating system of the NFS **must** be specified so
      that the LAVA scripts can install packages and identify other
      defaults in the deployment data. Supported values are ``android``,
      ``ubuntu``, ``debian`` or ``oe``::

       os: debian

Deploy example
==============

.. code-block:: yaml

 actions:

    - deploy:
        timeout:
          minutes: 2
        to: tmpfs
        image: http://images.validation.linaro.org/kvm-debian-wheezy.img.gz
        compression: gz
        os: debian

.. _boot_action:

Boot
****

Cause the device to boot using the deployed files. Depending on the
Strategy class, this could be by executing a command on the dispatcher
(for example ``qemu``) or by connecting to the device. Depending on the
power state of the device and the device configuration, the device may
be powered up or reset to provoke the boot.

Every ``boot`` action **must** specify a method which is used by the
Strategy classes to determine how to boot the deployed files on the
device. Depending on the method, other parameters will be required.

* **method**

  * **qemu** - boot the downloaded ``image`` from the deployment action
    using QEMU. This is the ``kvm`` device type and runs on the dispatcher.
    The QEMU command line is **not** available for modification. See
    :ref:`essential_components`.
  * **media** is ignored for the ``qemu`` method.

  ::

     - boot:
         method: qemu


  * **u-boot** - boot the downloaded files using UBoot commands.
  * **commands** - the predefined set of UBoot commands into which the
    location of the downloaded files can be substituted (along with details
    like the SERVERIP and NFS location, where relevant). See the device
    configuration for the complete set of commands.
  * **type** - the type of boot, dependent on the UBoot configuration.
    This needs to match the supported boot types in the device
    configuration, e.g. it may change the load addresses passed to
    UBoot.

  ::

    - boot:
       method: u-boot
       commands: nfs
       type: bootz

Boot example
============

.. code-block:: yaml

    - boot:
        method: qemu
        media: tmpfs
        failure_retry: 2


.. _test_action:

Test
****

The refactoring has retained compatibility with respect to the content of
Lava-Test-Shell Test Definitions although the submission format has changed:

#. The :ref:`test_action` will **never** boot the device - a :ref:`boot_action`
   **must** be specified. Multiple test operations need to be specified as
   multiple definitions listed within the same test block.
#. The LAVA support scripts are prepared by the :ref:`deploy_action` action
   and the same scripts will be used for all test definitions until another
   ``deploy`` block is encountered.

.. note:: There is a FIXME outstanding to ensure that only the test
          definitions listed in this block are executed for that
          test action - this allows different tests to be run after
          different boot actions, within the one deployment.

::

  - test:
     failure_retry: 3
     name: kvm-basic-singlenode  # is not present, use "test $N"


Definitions
===========

* **repository** - a publicly readable repository location.
* **from** - the type of the repository is **not** guessed, it **must**
  be specified explicitly. Support is planned for ``bzr``, ``url``,
  ``file`` and ``tar``.

  * **git** - a remote git repository which needs to be cloned by the
    dispatcher.
  * **inline** - a simple test definition present in the same file as
    the job submission, allowing tests to run based on a single file.
    When combined with ``file://`` URLs to the ``deploy`` parameters,
    this allows tests to run without needing external access. See
    :ref:`inline_test_definition_example`.

* **path** - the path within that repository to the YAML file containing
  the test definition.
* **name** (optional) if not present, use the name from the YAML. The
  name can also be overriden from the actual commands being run by
  calling the lava-test-suite-name API call (e.g. `lava-test-suite-name FOO`).

.. code-block:: yaml

     definitions:
         - repository: git://git.linaro.org/qa/test-definitions.git
           from: git
           path: ubuntu/smoke-tests-basic.yaml
           name: smoke-tests
         - repository: http://git.linaro.org/lava-team/lava-functional-tests.git
           from: git
           path: lava-test-shell/single-node/singlenode03.yaml
           name: singlenode-advanced

Test example
============

.. code-block:: yaml

    - test:
        failure_retry: 3
        name: kvm-basic-singlenode
        definitions:
            - repository: git://git.linaro.org/qa/test-definitions.git
              from: git
              path: ubuntu/smoke-tests-basic.yaml
              name: smoke-tests


.. _repeat_action:

Repeat
******

See :ref:`repeats`.

.. _submit_action:

Submit
******

.. warning:: As yet, pipeline data cannot be submitted - any details here are
             ignored.

.. _repeats:

Handling repeats
****************

Selected Actions within the dispatcher support repeating an
individual action (along with any internal pipelines created by that
action) - these are determined within the codebase.

Blocks of actions can also be repeated to allow a boot and test
cycle to be repeated. Only :ref:`boot_action` and :ref:`test_action`
are supported inside repeat blocks.

.. _repeat_single_action:

Repeating single actions
========================

Selected actions (``RetryAction``) within a pipeline (as determined
by the Strategy) support repetition of all actions below that point.
There will only be one ``RetryAction`` per top level action in each
pipeline. e.g. a top level :ref:`boot_action` action for UBoot would
support repeating the attempt to boot the device but not the actions
which substitute values into the UBoot commands as these do not change
between boots (only between deployments).

Any action which supports ``failure_retry`` can support ``repeat`` but
not in the same job. (``failure_retry`` is a conditional repeat if the
action fails, ``repeat`` is an unconditional repeat).

.. _failure_retry:

Retry on failure
----------------

Individual actions can be retried a specified number of times if the
a :ref:`job_error_exception` or :ref:`infrastructure_error_exception`
is raised during the ``run`` step by this action or any action within
the internal pipeline of this action.

Specify the number of retries which are to be attempted if a failure is
detected using the ``failure_retry`` parameter.

.. code-block:: yaml

  - deploy:
     failure_retry: 3

RetryActions will only repeat if a :ref:`job_error_exception` or
:ref:`infrastructure_error_exception` exception is raised in any action
inside the internal pipeline of that action. This allows for multiple
actions in any one deployment to be RetryActions without repeating
unnecessary tasks. e.g. download is a RetryAction to allow for
intermittent internet issues with third party downloads.

Unconditional repeats
---------------------

Individual actions can be repeated unconditionally using the ``repeat``
parameter. This behaves similarly to :ref:`failure_retry` except that
the action is repeated whether or not a failure was detected. This allows
a device to be booted repeatedly or a test definition to be re-run
repeatedly. This repetition takes the form:

.. code-block:: yaml

  - actions:
    - deploy:
        # deploy parameters
    - boot:
        method: qemu
        media: tmpfs
        repeat: 3
    - test:
        # test parameters

Resulting in::

 [deploy], [boot, boot, boot], [test]

Repeating blocks of actions
===========================

To repeat a specific boot and a specific test definition as one block
(``[boot, test], [boot, test], [boot, test] ...``), nest the relevant
:ref:`boot_action` and :ref:`test_action` actions in a repeat block.

.. code-block:: yaml

 actions:

    - deploy:
        timeout:
          minutes: 20
        to: tmpfs
        image: http://images.validation.linaro.org/kvm-debian-wheezy.img.gz
        os: debian
        root_partition: 1

    - repeat:
        count: 6

        actions:
        - boot:
            method: qemu
            media: tmpfs

        - test:
            failure_retry: 3
            name: kvm-smoke-test
            timeout:
              minutes: 5
            definitions:

This provides a shorthand which will get expanded by the parser into
a deployment and (in this case) 6 identical blocks of boot and test.

.. _dispatcher_timeouts:

Timeouts
********

Refactored timeouts now provide more detailed support. Individual actions
have uniquely addressable timeouts.

Timeouts are specified explicitly in days, hours, minutes and seconds.
Any unspecified value is set to zero.

The pipeline automatically records the amount of time elapsed for the
complete run of each action class as ``duration`` as well as the action
which sets the current timeout. Server side processing can now identify
when jobs are submitted with excessively long timeouts and highlight
exactly which actions can use shorter timeouts.

.. _total_job_timeout:

Job timeout
===========

The entire job will have an overall timeout - the job will fail if this
timeout is exceeded, whether or not any other timeout is longer.

A timeout for a job means that the current action will be allowed to
complete and the job will then fail.

.. code-block:: yaml

 timeouts:
   job:
     minutes: 15

.. _default_action_timeout:

Action timeout
==============

Each action has a default timeout which is handled differently according
to whether the action has a current connection to the device.

.. note:: This is per call made by each action class, not per top level
          action. i.e. the top level ``boot`` action includes many actions,
          from interrupting the bootloader and substituting commands to
          waiting for a shell session or login prompt once the boot starts.
          Each action class within the pipeline is given the action timeout
          unless overridden using :ref:`individual_action_timeout`.

Think of the action timeout as:

* no single operation of this class should possibly take longer than ...

along with

* the pipeline should wait no longer than ... to determine that the device is
  not responding.

When changing timeouts, review the pipeline logs for each top level action,
``deploy``, ``boot`` and ``test``.  Check the duration of each action
within each section and set the timeout for that top level action. Specific
actions can be extended using the :ref:`individual_action_timeout`
support.

Action timeouts behave differently, depending on whether the action has
a connection or not. This allows quicker determination of whether the
device has failed to respond. The type of action timeout can be determined
from the logs.

If no action timeout is given in the job, the default action timeout
of 30 seconds will be used.

Actions with connections
------------------------

These actions use the timeout to wait for a prompt after sending a
command over the connection. If the action times out, no further commands
are sent and the job is marked as Incomplete.

* Log message: ``${name}: Wait for prompt``::

   log: "expect-shell-connection: Wait for prompt. 24 seconds"

If the action has an active connection to a device, the timeout is set
for each operation on that connection. e.g. ``u-boot-commands`` uses
the same timeout for each line sent to UBoot.

Individual actions may make multiple calls on the connection - different
actions are used when a particular operation is expected to take longer
than other calls, e.g. boot.

Actions without connections
---------------------------

A timeout for these actions interrupts the executing action and marks
the job as Incomplete.

* Log message: ``${name}: timeout``::

   log: "git-repo-action: timeout. 45 seconds"

If the action has no connection (for example a deployment action), the
timeout covers the entire operation of that action and the action will
be terminated if the timeout is exceeded.

The log structure shows the action responsible for the command running
within the specified timeout.

::

   action:
     seconds: 45

.. note:: Actions which create a connection operate as actions **without**
          a connection. ``boot_qemu_image`` and similar actions will
          use the specified timeout for the complete operation, which is
          typically followed by an action (with a connection) which
          explicitly waits for the prompt (or performs an automatic
          login).

.. _individual_action_timeout:

Individual action timeouts
==========================

Individual actions can also be specified by name - see the pipeline
description output by the ``validate`` command to see the full name of
action classes::

   extract-nfsrootfs:
    seconds: 60

This allows typical action timeouts to be as short as practical, so that
jobs fail quickly, whilst allowing for individual actions to take longer.

Typical actions which may need timeout extensions:

#. **lava-test-shell** - unless changed, the :ref:`default_action_timeout`
   applies to running the all individual commands inside each test
   definition. If ``install: deps:`` are in use, it could take a lot longer
   to update, download, unpack and setup the packages than to run any
   one test within the definition.
#. **expect-shell-connection** - used to allow time for the device to
   boot and then wait for a standard prompt (up to the point of a login
   prompt or shell prompt if no login is offered). If the device is
   expected to raise a network interface at boot using DHCP, this could
   add an appreciable amount of time.

Examples
********

.. note:: The unit tests supporting the refactoring contain a number of
          example jobs. However, these have been written to support the
          tests and might not be appropriate for use on actual hardware
          - the files specified are just examples of a URL, not a URL
          of a working file.

.. _kvm_x86_example:

KVM x86 example
===============

https://git.linaro.org/lava/lava-dispatcher.git/blob/HEAD:/lava_dispatcher/pipeline/test/sample_jobs/kvm.yaml

.. code-block:: yaml

 device_type: kvm

 job_name: kvm-pipeline
 timeouts:
  job:
    minutes: 5
  action:
    minutes: 1
  test:
    minutes: 3
 priority: medium

 actions:

    - deploy:
        timeout:
          minutes: 2
        to: tmpfs
        image: http://images.validation.linaro.org/kvm-debian-wheezy.img.gz
        compression: gz
        os: debian

    - boot:
        method: qemu
        media: tmpfs
        failure_retry: 2

    - test:
        failure_retry: 3
        name: kvm-basic-singlenode
        definitions:
            - repository: git://git.linaro.org/qa/test-definitions.git
              from: git
              path: ubuntu/smoke-tests-basic.yaml
              name: smoke-tests

.. _inline_test_definition_example:

Inline test definition example
==============================

https://git.linaro.org/lava/lava-dispatcher.git/blob/HEAD:/lava_dispatcher/pipeline/test/sample_jobs/kvm-inline.yaml

.. code-block:: yaml

    - test:
        failure_retry: 3
        name: kvm-basic-singlenode  # is not present, use "test $N"
        definitions:
            - repository:
                metadata:
                    format: Lava-Test Test Definition 1.0
                    name: smoke-tests-basic
                    description: "Basic system test command for Linaro Ubuntu images"
                    os:
                        - ubuntu
                    scope:
                        - functional
                    devices:
                        - panda
                        - panda-es
                        - arndale
                        - vexpress-a9
                        - vexpress-tc2
                run:
                    steps:
                        - lava-test-case linux-INLINE-pwd --shell pwd
                        - lava-test-case linux-INLINE-uname --shell uname -a
                        - lava-test-case linux-INLINE-vmstat --shell vmstat
                        - lava-test-case linux-INLINE-ifconfig --shell ifconfig -a
                        - lava-test-case linux-INLINE-lscpu --shell lscpu
                        - lava-test-case linux-INLINE-lsusb --shell lsusb
                        - lava-test-case linux-INLINE-lsb_release --shell lsb_release -a
              from: inline
              name: smoke-tests-inline
              path: inline/smoke-tests-basic.yaml


.. _tftp_example:

TFTP deployment example
=======================

NFS
---

https://git.linaro.org/lava/lava-dispatcher.git/blob/HEAD:/lava_dispatcher/pipeline/test/sample_jobs/uboot.yaml

.. code-block:: yaml

 actions:
  - deploy:
     timeout:
       minutes: 4
     to: tftp
     kernel: http://images.validation.linaro.org/functional-test-images/bbb/zImage
     nfsrootfs: http://images.validation.linaro.org/debian-jessie-rootfs.tar.gz
     os: oe
     dtb: http://images.validation.linaro.org/functional-test-images/bbb/am335x-bone.dtb

Ramdisk
-------

https://git.linaro.org/lava/lava-dispatcher.git/blob/HEAD:/lava_dispatcher/pipeline/test/sample_jobs/panda-ramdisk.yaml

.. code-block:: yaml

  # needs to be a list of hashes to retain the order
  - deploy:
     timeout: 2m
     to: tftp
     kernel: http://images.validation.linaro.org/functional-test-images/panda/uImage
     ramdisk: http://images.validation.linaro.org/functional-test-images/common/linaro-image-minimal-initramfs-genericarmv7a.cpio.gz.u-boot
     ramdisk-type: u-boot
     dtb: http://images.validation.linaro.org/functional-test-images/panda/omap4-panda-es.dtb
