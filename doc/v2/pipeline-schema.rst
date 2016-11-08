.. index:: pipeline schema

.. _pipeline_schema:

Pipeline schema
###############

In general, the schema used for the pipeline are constrained, not strict or
free form. This means that the schema requires that specific elements **must**
exist in specific formats but that other structures can be added without
invalidating the file according to the schema.

There are several types of schema in the pipeline:

* :ref:`job_submission_schema` - used by test writers
* Device schema - used internally to validate the output of calls to
  the :term:`device dictionary`.
* Dispatcher schema - a modified version of the job submission schema
  to handle the changes imposed when splitting multinode jobs.

As high level constrained schema, the detail of valid files can change without
needing a change in the schema. Schema will update only if large additions are
made, for example is a new protocol is added but the schema itself is not
versioned. The strategy classes impose any change of requirements in a much
more precise manner than any schema.

.. _job_submission_schema:

Job Submission Schema
*********************

The Job Submission Schema exists to act as an initial filter on strings
submitted over XML-RPC. Only a simple, fast, check is made on YAML syntax and
basic object structure. Once this test passes, the YAML is entered into the
database and a JobID is returned to the submitter.

After submission, jobs are subject to full validation by the dispatcher where
the details of the submission will be checked against the requirements of the
pipeline determined by the strategies requested within the job. This validation
check happens after the scheduler has assigned a device to the job but before
the job starts Running. If this check fails, the job will be marked as
Incomplete with a failure comment. During the check, URLs included in the job
submission will be checked as well as whether the job submission can be
successfully built into a valid pipeline. This validation step can only be
repeated with full access to the device configuration of the instance.

During the submission process, there are also checks on the device type, device
restrictions and other scheduler criteria. These are checked after the schema
check.

An example pipeline job for a QEMU device looks like:

.. code-block:: yaml

 # Sample JOB definition for a KVM

 device_type: qemu
 job_name: qemu-pipeline
 timeouts:
  job:
    minutes: 15            # timeout for the whole job (default: ??h)
  action:
    minutes: 5         # default timeout applied for each action; can be overriden in the action itself (default: ?h)
 priority: medium

 actions:

    - deploy:
        timeout:
          minutes: 20
        to: tmpfs
        image: https://images.validation.linaro.org/kvm/standard/stretch-2.img.gz
        compression: gz
        os: debian
        # if root_partition partition is not present:
        # - look for a partitions labelled "root" or "ROOT" or "Root" (i.e. case insensitive)
        # - look into device configuration
        root_partition: 1

    - boot:
        prompts:
          - 'linaro-test'
          - 'root@debian:~#'
        method: qemu
        media: tmpfs
        failure_retry: 2

    - test:
        failure_retry: 3
        name: kvm-basic-singlenode  # is not present, use "test $N"
        # only s, m & h are supported.
        timeout:
          minutes: 5 # uses install:deps, so takes longer than singlenode01
        definitions:
            - repository: git://git.linaro.org/qa/test-definitions.git
              from: git
              path: ubuntu/smoke-tests-basic.yaml
              name: smoke-tests
            - repository: https://git.linaro.org/lava-team/lava-functional-tests.git
              from: git
              path: lava-test-shell/single-node/singlenode03.yaml
              name: singlenode-advanced

The submission schema for pipeline jobs can be represented as follows:

.. code-block:: yaml

 device_type: qemu

 job_name: string (max 200 chars) Required
 timeouts: Required Extra
  job: Required
    days|hours|minutes|seconds: integer Required
  action: Required
    days|hours|minutes|seconds: integer Required
 priority: high|medium|low
 protocols:
   lava-multinode:
     timeout: days|hours|minutes|seconds: integer Required
     roles: dictionary
 context:
   string: string
 actions: Required
    - deploy: Extra
        timeout:
          minutes: integer
        to: string Required
    - boot: Extra
        prompts: Required
          - string Required
        method: string Required
    - test: Extra
        timeout:
          minutes: integer
        definitions: Required Extra
            - repository: string|inline
              from: string
              path: string
              name: string

* Elements indicated as **Required** must be provided if the element has
  no parent or if that parent is also Required. All other elements are
  optional.
* Elements indicated with **Extra** can have arbitrary other values
  inserted as long as the YAML remains valid. These extra values must
  still make sense to the dispatcher validation process.
* The type of the element is enforced within the meaning of that
  type to the python interpreter and the python YAML parser.
* Where alternatives are shown, only one of those alternatives is allowed,
  anything else is disallowed.
* Where the YAML indicates a list or a dictionary, that list or
  dictionary can be extended with other allowed elements.

.. _schema_elements:

Schema elements
===============

Comments
--------

Comments in YAML start with ``#`` and continue to the end of that line.

Comments are retained in the submission and are stored in the database as part
of the job definition. If the job is multinode, no comments are generated for
individual nodes but comments in the multinode job submission YAML are retained
in the Multinode Definition.

.. _job_name_element:

Job Name
--------

* ``job_name``: string
* **Required**, max length 200 characters, minimum length 1 character.

Convention in the current dispatcher is that the job name does not use
whitespace. This convention does not need to be observed with the refactoring
as the job name is only stored in the database, the dispatcher does not care.
As a database field, there is a maximum character length of 200 characters. A
Job Name is Required as it becomes an important part of how the web frontend
displays information about the job. The name itself should be a description of
the objective of the test job rather than duplicating information already
available, like the type of device or the submitter.

.. _device_type_element:

Device Type
-----------

* ``device_type``: string
* minimum length 1 character.

Although not required by the schema, single node jobs will fail to validate if
no device type is given. Multi node jobs need the device type of particular
roles to be specified.

The :term:`device type` **must** exist on that instance for the submission to
be accepted by the scheduler even if the schema is otherwise valid.

.. _timeout_element:

Timeouts
--------

.. seealso:: :ref:`timeouts`

* ``timeouts``: dictionary
* **Required**

The refactoring introduces a new method of determining timeouts. The schema
requires that a job timeout is specified and that the default timeout for each
action is also specified. See :ref:`dispatcher_timeouts`.

A job timeout and an action timeout must be specified for the schema to
validate.

Timeouts should be specified as integers of the number of days, hours, minutes
or seconds required. There is generally no need to specify more than one
designator, just round up to the nearest. e.g. instead of 90 seconds, use 2
minutes. Timeouts lasting longer than 1 day should be used with extreme
caution. Being a good citizen in a LAVA instance means not blocking other users
from using the device, should your job fail early in a way that can only be
cleared via a timeout.

Use :ref:`individual_action_timeout` to handle situations where the job can
hang until it times out. The named action which is running at the time that the
job can hang should have a timeout which stops the action within a time period
*around twice the average duration* of the same action when the job is
successful.

.. code-block:: yaml

 timeouts:
   job:
     minutes: 15

Priority
--------

* ``priority``: high, medium or low.

Same as the existing :term:`priority` support.

Context
-------

Context allows individual jobs to override selected device configuration
values. The fields which can and cannot be overridden are not (yet) obvious but
include the architecture of the QEMU command and the console device and/or baud
rate of other devices. It is also possible to override the NFS args and UEFI
Menu selections. See :ref:`override_support`

.. code-block:: yaml

  context:
    menu_interrupt_prompt: 'Default boot will start in'

(The default values and which values can be overridden will be exposed in the
next stages of development.)

Some menu selections may embed device-specific information, e.g.:

.. code-block:: yaml

 -  'TFTP on MAC Address: 00:01:73:69:5A:EF'

The MAC address is a fixed part of the device configuration for a particular
physical interface on that device and therefore needs to be retained even if an
update causes other elements of the menu to change.

This is handled by asking the template to retain the MAC address specified for
that device using a placeholder in the context specified in the job submission:

.. code-block:: yaml

  context:
    mustang_menu_list:
    # ... other menu entries
    - 'item': "TFTP on MAC Address: tftp_mac"
    # ... other menu entries

Always take care to quote all strings containing a colon when using YAML.

Details of which placeholders are available for which devices and which
values has not yet been collated.

.. _protocols_element:

Protocols
---------



.. _actions_element:

Actions
-------

* **Required**: list of action dictionaries, **Extra**
* List entries **must** each be one of **deploy**, **boot** or **test**
  and can be repeated or omitted, as long as at least one action is
  specified.

Each action element allows **Extra** which means that the full list of
dictionary items which can be included beneath the action is defined by the
pipeline, not by the schema. The schema only asserts that selected fields must
exist (like where to deploy data to and how to boot or the definitions to be
used for the test).

.. _deploy_action_element:

Deploy Action
^^^^^^^^^^^^^

* **to** element is Required.

The deploy action dictates the deployment strategy for the pipeline. The
elements of the deploy action (and details from the assigned device) are used
by the pipeline to determine how the deployment will happen and whether the
submission is able to build a valid pipeline. If a **test** action is also
defined, the **deploy** action also uses the deploy elements to determine which
type of operating system support will be included into the deployment data.

Deploy Actions will typically occur on the dispatcher and are collectively
assigned tasks which prepare the device to be booted in preparation for the
test.

.. _boot_action_element:

Boot Action
^^^^^^^^^^^

* **prompts** element is Required.

The boot action prompts is a list of strings or a single string which will be
matched against the prompt of the booted system.

* **method** element is Required.

The boot action dictates the boot strategy for the pipeline. The elements of
the boot action (and details of the assigned device) are used by the pipeline
to determine the boot commands and boot sequence as well as whether the
submission is able to build a valid pipeline.

The first action in a boot strategy will typically be an attempt to establish a
connection to the device and cause either a reboot or a power-on event.

Some boot actions do not actually involve a reboot but can simply be a
connection to a device which is already running. Boot Actions are collectively
assigned tasks which communicate with the device in such a way as to allow the
test to start.

.. _test_action_element:

Test Action
^^^^^^^^^^^

* **repository** element is Required.

The test action dictates the test definitions which will be used by the
pipeline. The elements of the test action are used by the pipeline to prepare
the overlay of test definitions and test script helpers which will be deployed
to the assigned device and then executed after the device has booted.
