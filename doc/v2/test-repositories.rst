.. index:: test definition repository

.. _test_repos:

Test definitions in version control
###################################

LAVA supports git version control for use with test definitions, and
this is the recommended way to host and use test definitions for LAVA. When a
repository is listed in a test definition, the entire repository is checked
out. This allows YAML files in the repository to reliably access scripts and
other files which are part of the repository, inside the test image.

.. code-block:: yaml

  - test:
     role:
     - server
     - client
     definitions:
     - repository: http://git.linaro.org/lava-team/lava-functional-tests.git
       from: git
       path: lava-test-shell/multi-node/multinode02.yaml
       name: multinode-intermediate

When this test starts, the entire repository will be available in the current
working directory of the test. Therefore, ``multinode/multinode02.yaml`` can
include instructions to execute ``multinode/get_ip.sh``.

Job definitions in version control
**********************************

It is normally recommended to also store your test job YAML files in the
repository. This helps others who may want to use your test definitions.::

  https://git.linaro.org/lava-team/refactoring.git/tree/panda-multinode.yaml

There are numerous test repositories in use daily in Linaro that may be good
examples for you, including:

* https://git.linaro.org/lava-team/lava-functional-tests.git
* https://git.linaro.org/qa/test-definitions.git

Using specific branch of a test definition repository
*****************************************************

If a public branch is specified as a parameter in the job submission YAML,
that branch of the repository will be used instead of the default 'master'
branch.

.. code-block:: yaml

 - test:
     timeout:
       minutes: 5
     definitions:
     - repository: https://git.linaro.org/lava-team/lava-functional-tests.git
       from: git
       path: lava-test-shell/android/get-adb-serial-hikey.yaml
       name: get-hikey-serial
       branch: stylesen

.. note:: Do not supply anything other than a branch name to this parameter,
          like tag or revision as this would create a clone in a 'detached
          HEAD' state.

Using specific revisions of a test definition
*********************************************

If a specific revision is specified as a parameter in the job submission YAML,
that revision of the repository will be used instead of HEAD.

.. code-block:: yaml

 - test:
    failure_retry: 3
    timeout:
      minutes: 10
    name: kvm-basic-singlenode
    definitions:
        - repository: git://git.linaro.org/lava-team/lava-functional-tests.git
          from: git
          path: lava-test-shell/smoke-tests-basic.yaml
          name: smoke-tests
        - repository: http://git.linaro.org/lava-team/lava-functional-tests.git
          from: git
          path: lava-test-shell/single-node/singlenode03.yaml
          name: singlenode-advanced
          revision: 441b61

Shallow clones in GIT
*********************

Some git repositories have a long history of commits and using a full clone
takes up a lot of space. When a test job involves multiple test repositories,
this can cause issues with adding the LAVA overlay to the test job. For
example, ramdisks could become too large or there could be insufficient
space in the partition used for the test shell or it could take longer than
desired to transfer the overlay to the device.

When ``git`` support is requested for a test shell definition, LAVA will
default to making a **shallow** clone using ``--depth=1``. The git history
will be truncated to the single most recent commit.

A full clone can be requested by passing the ``shallow`` parameter with a
value of ``False``. If the ``revision`` option is used, shallow clone
support will need to be turned off or the change to specified revision
will fail.

.. seealso:: https://git-scm.com/docs/git-clone

.. code-block:: yaml

 - test:
    failure_retry: 3
    timeout:
      minutes: 10
    name: kvm-basic-singlenode
    definitions:
        - repository: http://git.linaro.org/lava-team/lava-functional-tests.git
          from: git
          path: lava-test-shell/single-node/singlenode03.yaml
          name: singlenode-advanced
          shallow: False


Removing git history
********************

The size of the overlay can be an issue for jobs running on small devices.
By default, when cloning test definition from a git repository, LAVA will keep
the **.git** directory.
If needed, this directory can be removed from the overlay by setting
``history`` to **false**.

.. code-block:: yaml

 - test:
    failure_retry: 3
    timeout:
      minutes: 10
    name: kvm-basic-singlenode
    definitions:
        - repository: http://git.linaro.org/lava-team/lava-functional-tests.git
          from: git
          path: lava-test-shell/single-node/singlenode03.yaml
          name: singlenode-advanced
          history: False


Sharing the contents of test definitions
****************************************

A YAML test definition file can clone another repository by specifying the
address of the repository to clone

.. code-block:: yaml

  install:
      git-repos:
          - git://git.linaro.org/people/davelong/lt_ti_lava.git

  run:
      steps:
          - cd lt_ti_lava
          - echo "now in the git cloned directory"

This allows a collection of LAVA test definitions to re-use other YAML custom
scripts without duplication. The tests inside the other repository will **not**
be executed.

Test repository for functional tests in LAVA
********************************************

LAVA regularly runs a set of test definitions to check for regressions and the
set is available for others to use as a template for their own tests::

* https://git.linaro.org/lava-team/lava-functional-tests.git

.. _test_definition_kmsg:

Using kernel messages in a test shell
*************************************

.. seealso:: :ref:`Simple test job flow <simple_job_flow>` for
   background on serial corruption and interleaving of kernel
   messages with test output. Also :ref:`isolating_kernel_messages`
   for information on using multiple serial connections to prevent
   such issues.

In situations where multiple serial ports are not available, there is
a possible mitigation to the problem of serial corruption of test shell
messages by kernel messages.

This is an example of the interleaving of kernel messages and test
shell messages:

.. code-block:: none

    <LAVA_SIGNAL_ENDRUN 0_network[   31.811978] ------------[ cut here ]------------
    -inline 14658_3.[   31.818261] WARNING: CPU: 4 PID: 2576 at /srv/oe/build/tmp-rpb-glibc/work-shared/hikey/kernel-source/include/net/sock.h:1703 af_alg_accept+0x1d8/0x208 [af_alg]
    2.3.1>
    <LAVA_TE[   31.834094] Modules linked in: algif_hash af_alg smsc75xx usbnet adv7511 kirin_drm drm_kms_helper dw_drm_dsi drm fuse
    Received signal: <ENDRUN> 0_network[   31.811978] ------------[ cut here ]------------
    -inline 14658_3.[   31.818261] WARNING: CPU: 4 PID: 2576 at /srv/oe/build/tmp-rpb-glibc/work-shared/hikey/kernel-source/include/net/sock.h:1703 af_alg_accept+0x1d8/0x208 [af_alg]
    2.3.1
    Ending use of test pattern.
    Ending test lava.0_network[ (31.811978]), duration 1.92
    case: 0_network[
    case_id: 875068
    definition: lava
    duration: 1.92
    namespace: hikey-oe
    path: None
    repository: None
    result: pass
    revision: unspecified
    uuid: 31.811978]
    _on_endrun() takes exactly 3 arguments (20 given)

The expected signal would have been more like the another message
of this type in the same test job:

.. code-block:: none

    <LAVA_SIGNAL_ENDRUN 1_kselftest 14658_3.2.3.5>
    Received signal: <ENDRUN> 1_kselftest 14658_3.2.3.5
    Ending use of test pattern.
    Ending test lava.1_kselftest (14658_3.2.3.5), duration 0.00
    case: 1_kselftest
    case_id: 876176
    commit_id: fd1f392f983803e7189e264dda22790c54950c8f
    definition: lava
    duration: 0.0057
    namespace: hikey-oe
    path: automated/linux/kselftest/kselftest.yaml
    repository: git://git.linaro.org/qa/test-definitions.git
    result: pass
    revision: unspecified
    uuid: 14658_3.2.3.5
    <LAVA_TEST_RUNNER>: 1_kselftest exited with: 0

As described in :ref:`isolating kernel messages <simple_job_flow>` in
the section on Multiple serial port support, this happens because the
test shell message ``<LAVA_SIGNAL_ENDRUN 1_kselftest 14658_3.2.3.5>``
is sent to ``stdout``. If the message was sent to ``/dev/kmsg`` then
the kernel would take care of emitting the entire line **before** (or
just **after**) emitting the warning. The test shell message would
remain intact and processing could continue normally.

Syntax
======

Test writers can decide which test shell definitions need to use this
support and which continue to use ``stdout``.

.. literalinclude:: examples/test-jobs/qemu-kmsg-events.yaml
     :language: yaml
     :linenos:
     :lines: 47-56
     :emphasize-lines: 3

By specifying ``lava-signal: kmsg`` for the first test shell definition
in the test job submission example above, LAVA can output the test
shell messages to ``/dev/kmsg``, resulting in output like:

.. code-block:: none

    [    8.862986] <LAVA_SIGNAL_ENDRUN 0_smoke-tests 1998_1.2.3.1>
    + export TESTRUN_ID=1_singlenode-advanced
    + TESTRUN_ID=1_singlenode-advanced
    + cd /lava-1998/0/tests/1_singlenode-advanced
    ++ cat uuid
    + UUID=1998_1.2.3.5
    + set +x
    <LAVA_SIGNAL_STARTRUN 1_singlenode-advanced 1998_1.2.3.5>
    + apt-get update -q
    Received signal: <TESTCASE> TEST_CASE_ID=linux-linaro-ubuntu-lsb_release RESULT=fail
    case: linux-linaro-ubuntu-lsb_release
    case_id: 49920
    definition: 0_smoke-tests
    result: fail
    Received signal: <ENDRUN> 0_smoke-tests 1998_1.2.3.1

.. note::
   * The LAVA test shell messages are now prefixed with the kernel
     message time stamp - this does not affect processing which is
     restricted to the content between the ``<`` and ``>`` markers.

   * When describing ``stdout``, ``stderr`` is implicitly included.

   * The ordering of messages in the output shows the inherent
     latency in the message processing.

.. _kmsg_signal_limitations:

Limitations
===========

.. seealso:: If the limitations with this approach make it unsuitable,
    :ref:`multiple_serial_support` is preferred, where available.

Login
-----

The login shell is not part of the LAVA test shell, it is the final
part of the boot sequence and the input/output of the login shell is
not under the control of LAVA. If kernel messages appear when the
device is attempting to read in the username or password or if a
message appears when the login shell is attempting to output the
prompt, then the parsing will still fail.

stdout
------

The problem of interleaving messages from multiple inputs onto a single
output has not gone away by sending the LAVA test shell messages to
``/dev/kmsg``. There is still only a single serial connection which
**must** be shared between all ``stdout`` output and all ``console``
output. Test shell operations which produce a lot of ``stdout`` and/or
``stderr`` output can still flood the serial connection and interrupt
kernel message lines.

Definitions
-----------

Not all LAVA test shell operations can be sent to ``/dev/kmsg`` - some
will go to ``stdout`` even if all test definitions are marked to use
``/dev/kmsg`` because the test shell runner script needs to be the same
for all definitions.
