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

.. _repeat_single_action:

Repeating single actions
========================

Selected actions (``RetryAction``) within a pipeline (as determined by the
Strategy) support repetition of all actions below that point. There will only
be one ``RetryAction`` per top level action in each pipeline. e.g. a top level
:ref:`boot_action` action for U-Boot would support repeating the attempt to
boot the device but not the actions which substitute values into the U-Boot
commands as these do not change between boots (only between deployments).

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

.. _failure_retry_interval:

Retry interval on failure
-------------------------

By default, individual action would be retried after 1 second, but you could
specify ``failure_retry_interval`` to increase the interval between retries.

.. code-block:: yaml

  - deploy:
     failure_retry_interval: 10

RetryActions will only repeat if a :ref:`job_error_exception` or
:ref:`infrastructure_error_exception` exception is raised in any action inside
the internal pipeline of that action. This allows for multiple actions in any
one deployment to be RetryActions without repeating unnecessary tasks. e.g.
download is a RetryAction to allow for intermittent internet issues with third
party downloads.

Repeating blocks of actions
===========================

To repeat block of actions, it's advised to use a templating engine, like
jinja2, and to use it to generate a job definition where the blocks are
repeated. ``repeat`` parameter is currently not supported in LAVA.
