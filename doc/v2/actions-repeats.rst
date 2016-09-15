.. _repeat_action:

Repeat
######

See :ref:`repeats`.

.. _repeats:

Handling repeats
****************

Selected Actions within the dispatcher support repeating an individual action
(along with any internal pipelines created by that action) - these are
determined within the codebase.

Blocks of actions can also be repeated to allow a boot and test cycle to be
repeated. Only :ref:`boot_action` and :ref:`test_action` are supported inside
repeat blocks.

.. _repeat_single_action:

Repeating single actions
========================

Selected actions (``RetryAction``) within a pipeline (as determined by the
Strategy) support repetition of all actions below that point. There will only
be one ``RetryAction`` per top level action in each pipeline. e.g. a top level
:ref:`boot_action` action for U-Boot would support repeating the attempt to
boot the device but not the actions which substitute values into the U-Boot
commands as these do not change between boots (only between deployments).

Any action which supports ``failure_retry`` can support ``repeat`` but not in
the same job. (``failure_retry`` is a conditional repeat if the action fails,
``repeat`` is an unconditional repeat).

.. _failure_retry:

Retry on failure
----------------

Individual actions can be retried a specified number of times if the a
:ref:`job_error_exception` or :ref:`infrastructure_error_exception` is raised
during the ``run`` step by this action or any action within the internal
pipeline of this action.

Specify the number of retries which are to be attempted if a failure is
detected using the ``failure_retry`` parameter.

.. code-block:: yaml

  - deploy:
     failure_retry: 3

RetryActions will only repeat if a :ref:`job_error_exception` or
:ref:`infrastructure_error_exception` exception is raised in any action inside
the internal pipeline of that action. This allows for multiple actions in any
one deployment to be RetryActions without repeating unnecessary tasks. e.g.
download is a RetryAction to allow for intermittent internet issues with third
party downloads.

Unconditional repeats
---------------------

Individual actions can be repeated unconditionally using the ``repeat``
parameter. This behaves similarly to :ref:`failure_retry` except that the
action is repeated whether or not a failure was detected. This allows a device
to be booted repeatedly or a test definition to be re-run repeatedly. This
repetition takes the form:

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

To repeat a specific boot and a specific test definition as one block (``[boot,
test], [boot, test], [boot, test] ...``), nest the relevant :ref:`boot_action`
and :ref:`test_action` actions in a repeat block.

.. code-block:: yaml

 actions:

    - deploy:
        timeout:
          minutes: 20
        to: tmpfs
        image: https://images.validation.linaro.org/kvm-debian-wheezy.img.gz
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

This provides a shorthand which will get expanded by the parser into a
deployment and (in this case) 6 identical blocks of boot and test.
