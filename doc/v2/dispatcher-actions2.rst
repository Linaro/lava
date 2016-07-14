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
    one or more images, appending specified arguments to a predetermined
    QEMU command line::

     to: tmpfs

    * Requires an ``images`` parameter, e.g.::

        images:
          rootfs:
              image_arg: -drive format=raw,file={rootfs}
              url: http://images.validation.linaro.org/kvm-debian-wheezy.img.gz
              compression: gz

      * The ``image_arg`` determines how QEMU handles the image. The
        arguments **must** include a placeholder which exactly matches
        the key of the same block in the list of images. The actual
        location of the downloaded file will then replace the placeholder.
        Multiple images can be supplied but the test writer is responsible
        for ensuring that the ``image_arg`` make sense to QEMU.

      * If the image is compressed, the compression method **must** be
        specified if any ``test`` actions are defined in the job. Supported
        values are ``gz``, ``bz2`` and ``xz``::

         compression: gz

      * The checksum of the file to download can be provided to be checked
        against the downloaded content. This can help if there is a transparent
        proxy between the dispatcher as a proxy might return a cached file if
        the content of the URL has changed without changing the URL itself.
        If compression is used, the checksum to specify is the checksum of the
        compressed file, irrespective of whether that file is decompressed
        later.::

         md5sum: 6ea432ac3c23210c816551782346ed1c
         sha256sum: 1a76b17701b9fdf6346b88eb49b0143a9c6912701b742a6e5826d6856edccd21

    * The operating system of the image **must** be specified so that the
      LAVA scripts can install packages and identify other defaults in the
      deployment data. Supported values are ``android``, ``ubuntu``,
      ``debian`` or ``oe``::

        os: debian

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

       kernel:
         url: http://images.validation.linaro.org/functional-test-images/bbb/zImage

    * **dtb** - in an appropriate format to what the commands require::

       dtb:
         url: http://images.validation.linaro.org/functional-test-images/bbb/am335x-bone.dtb

    * **modules** - a tarball of kernel modules for the supplied kernel::

       modules:
         url: http://images.validation.linaro.org/modules.tgz
         compression: gz

      The file **must** be a tar file and the compression method **must**
      be specified.

      If the kernel requires these modules to be able to locate the rootfs,
      e.g. when using NFS or if certain required filesystem drivers are
      only available as modules, the ramdisk can be unpacked and the
      modules added. Modules may also be required to run tests within
      the ramdisk itself.

    * **ramdisk** - in an appropriate format to what the commands require.

      The ramdisk needs to be unpacked and modified in either of the
      following two use cases:

      * the lava test shell is expected to run inside the ramdisk, or
      * the deployment needs modules to be added to the ramdisk, for
        example to allow the device to load the network driver to be
        able to locate the NFS.

      To unpack the ramdisk, the test writer needs to specify details
      about how the ramdisk is prepared and used. If these details are
      not provided, the ramdisk will not be unpacked (potentially causing
      the test to fail in the above two use cases).

      If a header is already applied, the ``header`` value **must**
      specify the type of header, e.g. ``u-boot``. This header will
      be removed before unpacking, ready for the LAVA overlay files.
      If a header needs to be applied after any LAVA overlay files are
      added to the ramdisk, the ``add-header`` value must specify the type
      of header to add, e.g. ``u-boot``.
      The compression algorithm to be used to unpack the ramdisk **must**
      be specified explicitly.
      ::

       ramdisk:
         url: http://images.validation.linaro.org/functional-test-images/common/linaro-image-minimal-initramfs-genericarmv7a.cpio.gz.u-boot
         compression: gz
         header: u-boot
         add-header: u-boot

      If the ramdisk is not to be modified, the ``allow_modify`` option
      **must** be specified as ``false`` (without quotes). This means
      that a test shell will not be able to run inside the ramdisk. If
      ``modules`` are specified as well, these will not be added to the
      ramdisk. For example, if the ramdisk is signed or if modules are
      not required for NFS::

       ramdisk:
         url: file://tmp/uInitrd
         allow_modify: false

      ``allow_modify: true`` is equivalent to not specifying ``allow_modify``
      at all.

    * **nfsrootfs** - **must** be a tarball and supports one of ``gz``, ``xz`` or
      ``bz2`` compression. The NFS is unpacked into a temporary directory onto the
      dispatcher in a location supported by NFS exports.
      The compression algorithm to be used to unpack the nfsrootfs **must**
      be specified explicitly.
      ::

       nfsrootfs:
         url: http://images.validation.linaro.org/debian-jessie-rootfs.tar.gz
         compression: gz

    * **nfs_url** - use a persistent NFS URL instead of a compressed tarball. See
      :ref:`persistence` for the limitations of persistent storage. The creation and
      maintenance of the persistent location is **solely** the responsibility of the
      test writer. The ``nfs_url`` **must** include the IP address of the NFS server
      and the full path to the directory which contains the root filesystem, separated
      by a single colon. In the YAML, all values containing a colon **must** be quoted::

       nfs_url: "127.0.0.1:/var/lib/lava/dispatcher/tmp/armhf/jessie"

      .. note:: LAVA does not shutdown the device or attempt to unmount the NFS when the
         job finishes, the device is simply powered off. The test writer needs to ensure
         that any background processes started by the test have been stopped before the
         test finishes.

    * **os** -  The operating system of the NFS **must** be specified so
      that the LAVA scripts can install packages and identify other
      defaults in the deployment data. Supported values are ``android``,
      ``ubuntu``, ``debian`` or ``oe``::

       os: debian

  * **usb**: Deploy unchanged images to secondary USB media. Any bootloader
    inside the image will **not** be used. Instead, the files needed for the
    boot are specified in the deployment. The entire physical device is
    available to the secondary deployment. Secondary relates to the expected
    requirement of a primary boot (e.g. ramdisk or NFS) which provides a
    suitable working environment to deploy the image directly to the
    secondary device. See :ref:`secondary_media`.

    Not all devices support USB media.

    The test writer needs to provide the following information about the
    image:

     * **kernel**: The path, within the image, to the kernel which will
       be used by the bootloader.
     * **ramdisk**: (optional). If used, must be a path, within the image,
       which the bootloader can use.
     * **dtb**: The path, within the image, to the dtb which will
       be used by the bootloader.
     * **UUID**: The UUID of the partition which contains the root filesystem
       of the booted image.
     * **boot_part**: the partition on the media from which the bootloader
       can read the kernel, ramdisk & dtb.

    .. note:: If the image mounts the boot partition at a mounpoint below
              the root directory of the image, the path to files within that
              partition must **not** include that mountpoint. The bootloader
              will read the files directly from the partition.

    The UUID can be obtained by writing the image to local media and checking
    the contents of ``/dev/disk/by-uuid``

    The ramdisk may need adjustment for some bootloaders (like UBoot), so
    mount the local media and use something like::

     mkimage -A arm -T ramdisk -C none -d /mnt/boot/init.. /mnt/boot/init..u-boot

  * **sata**: Deploy unchanged images to secondary SATA media. Any bootloader
    inside the image will **not** be used. Instead, the files needed for the
    boot are specified in the deployment. The entire physical device is
    available to the secondary deployment. Secondary relates to the expected
    requirement of a primary boot (e.g. ramdisk or NFS) which provides a
    suitable working environment to deploy the image directly to the
    secondary device. See :ref:`secondary_media`.

    Not all devices support SATA media.

    The test writer needs to provide the following information about the
    image:

     * **kernel**: The path, within the image, to the kernel which will
       be used by the bootloader.
     * **ramdisk**: (optional). If used, must be a path, within the image,
       which the bootloader can use.
     * **dtb**: The path, within the image, to the dtb which will
       be used by the bootloader.
     * **UUID**: The UUID of the partition which contains the root filesystem
       of the booted image.
     * **boot_part**: the partition on the media from which the bootloader
       can read the kernel, ramdisk & dtb.

    .. note:: If the image mounts the boot partition at a mounpoint below
              the root directory of the image, the path to files within that
              partition must **not** include that mountpoint. The bootloader
              will read the files directly from the partition.

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

Boot actions which result in a POSIX type login or shell must specify a list
of expected prompts which will be matched against the output to determine the
endpoint of the boot process.

* **prompts**

  ::

     - boot:
         prompts:
           - 'linaro-test'
           - 'root@debian:~#'

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
       prompts:
         - 'linaro-test'
         - 'root@debian:~#'

Boot example
============

.. code-block:: yaml

    - boot:
        method: qemu
        media: tmpfs
        failure_retry: 2
        prompts:
          - 'linaro-test'
          - 'root@debian:~#'


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
     name: kvm-basic-singlenode

.. _test_action_definitions:

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
* **name** (required) - replaces the name from the YAML.
* **params** (optional): Pass parameters to the Lava Test Shell
  Definition. The format is a YAML dictionary - the key is the name of
  the variable to be made available to the test shell, the value is the
  value of that variable.

  .. code-block:: yaml

     definitions:
         - repository: http://git.linaro.org/lava-team/hacking-session.git
           from: git
           path: hacking-session-debian.yaml
           name: hacking
           params:
            IRC_USER: ""
            PUB_KEY: ""

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

Skipping elements of test definitions
=====================================

When a single test definition is to be used across multiple deployment
types (e.g. Debian and OpenEmbedded), it may become necessary to only
perform certain actions within that definition in specific jobs. The
``skip_install`` support has been migrated from V1 for compatibility.
Other methods of optimising test definitions for specific deployments
may be implemented in V2 later.

The available steps which can be (individually) skipped are:

* **deps** - skip running ``lava-install-packages`` for the ``deps:``
  list of the ``install:`` section of the definition.
* **keys** - skip running ``lava-add-keys`` for the ``keys:``
  list of the ``install:`` section of the definition.
* **sources** - skip running ``lava-add-sources`` for the ``sources:``
  list of the ``install:`` section of the definition.
* **steps** - skip running any of the ``steps:``of the ``install:``
  section of the definition.
* **all** - identical to ``['deps', 'keys', 'sources', 'steps']``

Example syntax:

.. code-block:: yaml

 - test:
     failure_retry: 3
     name: kvm-basic-singlenode
     timeout:
       minutes: 5
     definitions:
       - repository: git://git.linaro.org/qa/test-definitions.git
         from: git
         path: ubuntu/smoke-tests-basic.yaml
         name: smoke-tests
       - repository: http://git.linaro.org/lava-team/lava-functional-tests.git
         skip_install:
         - all
         from: git
         path: lava-test-shell/single-node/singlenode03.yaml
         name: singlenode-advanced

The following will skip dependency installation and key addition in the
same definition:

.. code-block:: yaml

 - test:
     failure_retry: 3
     name: kvm-basic-singlenode
     timeout:
       minutes: 5
     definitions:
       - repository: git://git.linaro.org/qa/test-definitions.git
         from: git
         path: ubuntu/smoke-tests-basic.yaml
         name: smoke-tests
       - repository: http://git.linaro.org/lava-team/lava-functional-tests.git
         skip_install:
         - deps
         - keys
         from: git
         path: lava-test-shell/single-node/singlenode03.yaml
         name: singlenode-advanced

Additional support
==================

The refactoring supports some additional elements in Lava Test Shell
which will not be supported in the current dispatcher.

Result checks
-------------

LAVA collects results from internal operations as well as from the
submitted test definitions, these form the ``lava`` test suite results.
The full set of results for a job are available at::

 results/1234

LAVA records when a submitted test definition starts execution on the
test device. If the number of test definitions which started is not the
same as the number of test definitions submitted (allowing for the ``lava``
test suite results), a warning will be displayed on this page.

TestSets
--------

A TestSet is a group of lava test cases which will be collated within
the LAVA Results. This allows queries to look at a set of related
test cases within a single definition.

.. code-block:: yaml

  name: testset-def
    run:
        steps:
            - lava-test-set start first_set
            - lava-test-case date --shell ntpdate-debian
            - ls /
            - lava-test-case mount --shell mount
            - lava-test-set stop
            - lava-test-case uname --shell uname -a

This results in the ``date`` and ``mount`` test cases being included
into a ``first_set`` TestSet, independent of other test cases. The
TestSet is concluded with the ``lava-test-set stop`` command, meaning
that the ``uname`` test case has no test set, providing a structure
like:

.. code-block:: yaml

 results:
   first_set:
     date: pass
     mount: pass
   uname: pass

.. code-block:: python

 {'results': {'first_set': {'date': 'pass', 'mount': 'pass'}, 'uname': 'pass'}}

Each TestSet name must be valid as a URL, which is consistent with the
requirements for test definition names and test case names in the
current dispatcher.

For TestJob ``1234``, the ``uname`` test case would appear as::

 results/1234/testset-def/uname

The ``date`` and ``mount`` test cases are referenced via the TestSet::

 results/1234/testset-def/first_set/date
 results/1234/testset-def/first_set/mount

A single test definition can start and stop different TestSets in
sequence, as long as the name of each TestSet is unique for that
test definition.

.. _repeat_action:

Repeat
******

See :ref:`repeats`.

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
        prompts:
          - 'linaro-test'
          - 'root@debian:~#'
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
            prompts:
              - 'linaro-test'
              - 'root@debian:~#'

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

.. note:: The behaviour of actions and connections has changed during the
   development of the refactoring. See :ref:`connection_timeout` and
   :ref:`default_action_timeout`. Action timeouts can be specified for
   the default for all actions or for a specific action. Connection timeouts
   can be specified as the default for all connections or for the
   connections made by a specific action.

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

.. note:: This timeout covers each action class, not per top level
          action. i.e. the top level ``boot`` action includes many actions,
          from interrupting the bootloader and substituting commands to
          waiting for a shell session or login prompt once the boot starts.
          Each action class within the pipeline is given the action timeout
          unless overridden using :ref:`individual_action_timeout`.

Think of the action timeout as::

  "no single operation of this class should possibly take longer than ..."

along with::

  "the pipeline should wait no longer than ... to determine that the device is not responding."

When changing timeouts, review the pipeline logs for each top level action,
``deploy``, ``boot`` and ``test``.  Check the duration of each action
within each section and set the timeout for that top level action. Specific
actions can be extended using the :ref:`individual_action_timeout`
support.

Action timeouts only determine the operation of the action, not the operation of
any connection used by the action. See :ref:`connection_timeout`.

If no action timeout is given in the job, the default action timeout
of 30 seconds will be used.

A timeout for these actions interrupts the executing action and marks
the job as Incomplete.

* Log message is of the form: ``${name}: timeout``::

   log: "git-repo-action: timeout. 45 seconds"

The action timeout covers the entire operation of that action and the action will
be terminated if the timeout is exceeded.

The log structure shows the action responsible for the command running
within the specified timeout.

::

   action:
     seconds: 45


.. _individual_action_timeout:

Individual action timeouts
--------------------------

Individual actions can also be specified by name - see the pipeline
description output by the ``validate`` command or the Pipeline Description
on the job definition page to see the full name of action classes::

   extract-nfsrootfs:
    seconds: 60

Individual actions can be referenced by the :term:`action level` and the job ID,
in the form::

 http://<INSTANCE_URL>/scheduler/job/<JOB_ID>/definition#<ACTION_LEVEL>

The level string represents the sequence within the pipeline and is a key
component of how the pipeline data is organised. See also :ref:`pipeline_construction`.

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

.. _connection_timeout:

Connection timeout
==================

Actions retain the action timeout for the complete duration of the action
``run()`` function. If that function uses a connection to interact with the
device, each connection operation uses the **connection_timeout**, so the
action timeout **must** allow enough time for all the connection operations
to complete within expectations of normal latency.

* Log message is of the form: ``${name}: Wait for prompt``::

   log: "expect-shell-connection: Wait for prompt. 24 seconds"

Before the connection times out, a message will be sent to help prevent serial
corruption from interfering with the expected prompt.

 * Warning message is of the form:

 Warning command timed out: Sending ... in case of corruption

The character used depends on the type of connection - a connection which expects
a POSIX shell will use ``#`` as this is a neutral / comment operation.

A timeout for the connection interrupts the executing action and marks
the job as Incomplete.

* Log message is of the form: ``${name}: timeout``::

   log: "git-repo-action: timeout. 45 seconds"

Individual actions may make multiple calls on the connection - different
actions are used when a particular operation is expected to take longer
than other calls, e.g. boot.

Set the default connection timeout which all actions will use when using
a connection:

.. code-block:: yaml

 timeouts:
   connection:
     seconds: 20

Individual connection timeouts
------------------------------

A specific action can be given an individual connection timeout which will
be used by whenever that action uses a connection: If the action does not
use a connection, this timeout will have no effect.

.. code-block:: yaml

 timeouts:
   connections:
     uboot-retry:
       seconds: 120

.. note:: Note the difference between ``connection`` followed by a value for the
   default connection timeout and ``connections``, ``<action_name>`` followed
   by a value for the individual connection timeout for that action.

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
        prompts:
          - 'linaro-test'
          - 'root@debian:~#'

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

.. _protocols:

Protocols
#########

Protocols are similar to a Connection but operate over a known API
instead of a shell connection. The protocol defines which API calls
are available through the LAVA interface and the Pipeline determines
when the API call is made.

Not all protocols can be called from all actions. Not all protocols are
able to share data between actions.

A Protocol operates separately from any Connection, generally over a
predetermined layer, e.g. TCP/IP sockets. Some protocols can access
data passing over a Connection.

.. _multinode_protocol:

Multinode Protocol
******************

The initial protocol available with the refactoring is Multinode. This
protocol allows actions within the Pipeline to make calls using the
:ref:`multinode_api` outside of a test definition by wrapping the call
inside the protocol. Wrapped calls do not necessarily have all of the
functionality of the same call available in the test definition.

The Multinode Protocol allows data to be shared between actions, including
data generated in one test shell definition being made available over the
protocol to a deploy or boot action of jobs with a different ``role``. It
does this by adding handlers to the current Connection to intercept API
calls.

The Multinode Protocol can underpin the use of other tools without
necessarily needing a dedicated Protocol class to be written for those
tools. Using the Multinode Protocol is an extension of using the existing
:ref:`multinode_api` calls within a test definition. The use of the
protocol is an advanced use of LAVA and relies on the test writer
carefully planning how the job will work.

.. code-block:: yaml

        protocols:
          lava-multinode:
            action: umount-retry
            request: lava-sync
            messageID: test

This snippet would add a :ref:`lava_sync` call at the start of the
UmountRetry action:

* Actions which are too complex and would need data mid-operation need
  to be split up.
* When a particular action is repeatedly used with the protocol, a
  dedicated action needs to be created. Any Strategy which explicitly
  uses protocol support **must** create a dedicated action for each
  protocol call.
* To update the value available to the action, ensure that the key exists
  in the matching :ref:`lava_send` and that the value in the job submission
  YAML starts with **$** ::

          protocols:
          lava-multinode:
            action: execute-qemu
            request: lava-wait
            messageID: test
            message:
              ipv4: $IPV4

  This results in this data being available to the action::

   {'message': {'ipv4': '192.168.0.3'}, 'messageID': 'test'}

* Actions check for protocol calls at the start of the run step before
  even the internal pipeline actions are run.
* Only the named Action instance inside the Pipeline will make the call
* The :ref:`multinode_api` asserts that repeated calls to :ref:`lava_sync`
  with the same messageID will return immediately, so this protocol call
  in a Retry action will only synchronise the first attempt at the action.
* Some actions may make the protocol call at the end of the run step.

The Multinode Protocol also exposes calls which are not part of the
test shell API, which were formerly hidden inside the job setup phase.

.. _lava_start:

lava-start API call
===================

``lava-start`` determines when Multinode jobs start, according to the
state of other jobs in the same Multinode group. This allows jobs with
one ``role`` to determine when jobs of a different ``role`` start, so
that the delayed jobs can be sure that particular services required for
those jobs are available. For example, if the ``server`` role is actually
providing a virtualisation platform and the ``client`` is a VM to be
started on the ``server``, then a delayed start is necessary as the first
action of the ``client`` role will be to attempt to connect to the server
in order to boot the VM, before the ``server`` has even been deployed. The
``lava-start`` API call allows the test writer to control when the ``client``
is started, allowing the ``server`` test image to setup the virtualisation
support in a way that allows attaching of debuggers or other interventions,
before the VM starts.

The client enables a delayed start by declaring which ``role`` the client
can ``expect`` to send the signal to start the client.

.. code-block:: yaml

        protocols:
          lava-multinode:
            request: lava-start
            expect_role: server
            timeout:
              minutes: 10

The timeout specified for ``lava_start`` is the amount of time the job
will wait for permission to start from the other jobs in the group.

Internally, ``lava-start`` is implemented as a :ref:`lava_send` and a
:ref:`lava_wait_all` for the role of the action which will make the
``lava_start`` API call using the message ID ``lava_start``.

It is an error to specify the same ``role`` and ``expect_role`` to
``lava-start``.

.. note:: Avoid confusing :ref:`host_role <host_role>` with ``expect_role``.
   ``host_role`` is used by the scheduler to ensure that the job
   assignment operates correctly and does not affect the dispatcher or
   delayed start support. The two values may often have the same
   value but do not mean the same thing.

It is an error to specify ``lava-start`` on all roles within a job or
on any action without a ``role`` specified.

All jobs without a ``lava-start`` API call specified for the ``role`` of
that job will start immediately. Other jobs will write to the log files
that the start has been delayed, pending a call to ``lava-start`` by
actions with the specified role(s).

Subsequent calls to ``lava-start`` for a role which has already started
will still be sent but will have no effect.

If ``lava-start`` is specified for a ``test`` action, the test definition
is responsible for making the ``lava-start`` call.

.. code-block:: yaml

 run:
   steps:
     - lava-send lava_start

.. _passing_data_at_startup:

Passing data at startup
=======================

The pipeline exposes the names of all actions and these names are
used for a variety of functions, from timeouts to protocol usage.

To see the actions within a specific pipeline job, see the job
definition (not the multinode definition) where you will find a Pipeline
Description.

Various delayed start jobs will need dynamic data from the "server" job
in order to be able to start, like an IP address. This is achieved by
adding the ``lava-start`` call to a specified ``test`` action of the server
role where the test definition initiates a :ref:`lava_send` message. When this
specific ``test`` action completes, the protocol will send the ``lava-start``.
The first thing the delayed start job does is a ``lava-wait`` which would
be added to the ``deploy`` action of that job.

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

.. note:: Some calls can only be made against specific actions.
   Specifically, the ``prepare-scp-overlay`` action needs the IP
   address of the host device to be able to copy the LAVA overlay
   (containing the test definitions) onto the device before connecting
   using ``ssh`` to start the test. This is a **complex** configuration
   to write.

.. seealso:: :ref:`writing_secondary_connection_jobs`

Depending on the implementation of the ``deploy`` action, determined by
the Strategy class, the ``lava-wait`` call will be made at a suitable
opportunity within the deployment. In the above example, the ``lava-send``
call is made before ``lava-start`` - this allows the data to be stored
in the lava coordinator and the ``lava-wait`` will receive the data
immediately.

The specified ``messageID`` **must** exactly match the message ID
used for the :ref:`lava_send` call in the test definition. (So an **inline**
test definition could be useful for the test action of the job definition
for the ``server`` role. See :ref:`inline_test_definition_example`)

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

The pipeline exposes the names of all actions and these names are
used for a variety of functions, from timeouts to protocol usage.

To see the actions within a specific pipeline job, see the job
definition (not the multinode definition) where you will find a Pipeline
Description.

Creating multinode jobs has always been complex. The consistent use of
inline definitions can significantly improve the experience and once
the support is complete, it may be used to invalidate submissions which
fail to match the synchronisation primitives.

The principle is to separate the synchronisation from the test operation.
By only using synchronisation primitives inside an inline definition,
the flow of the complete multinode group can be displayed. This becomes
impractical as soon as the requirement involves downloading a test
definition repository and possibly fishing inside custom scripts for the
synchronisation primitives.

Inline blocks using synchronisation calls can still do other checks and
tasks as well but keeping the synchronisation at the level of the
submitted YAML allows much easier checking of the job before the job
starts to run.

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

This is a small deviation from how existing Multinode jobs may be defined
but the potential benefits are substantial when combined with the other
elements of the Multinode Protocol.

VLANd protocol
**************

See :ref:`VLANd protocol <vland_in_lava>` - which uses the multinode protocol
to interface with :term:`VLANd` to support virtual local area networks in LAVA.
