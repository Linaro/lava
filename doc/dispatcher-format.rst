.. _dispatcher_yaml:

Writing YAML files for the refactored dispatcher
################################################

To use the new features in the refactored dispatcher, a new submission
format was required and as YAML supports comments, it was decided to
adopt YAML as the new format.

`Online YAML`_ Parser.

.. _Online YAML: http://yaml-online-parser.appspot.com/

The submission format schema has not been created, so the detail may
change and errors in the content might not be picked up by the code,
so take care when preparing new files.

.. warning:: This code is in ongoing development and the formats may
             change without notice. Only a very restricted set of
             actions and device types are supported. The refactored
             code can only be used from the command line and requires
             ``sudo`` access on the dispatcher. No-one except LAVA
             developers should be expecting to use any of these files.

.. _yaml_job:

Basics of the YAML format
*************************

Basic structure for job submission
==================================

The basic structure of the submission YAML is:

#. parameters for the job
#. list of actions.

The parameters for a job **must include**:

#. a ``device_type``
#. a ``job_name``

Other parameters commonly supported include:

#. ``job_timeout`` - the default for this is not currently decided, so
   always specify a timeout for the job as a whole.
#. ``action_timeout`` - the default timeout for each individual action
   within the job, unless an explicit timeout is set later in the YAML.
#. ``priority`` - not currently used as submission via the scheduler is
   not supported.

.. code-block:: yaml

 device_type: kvm
 job_name: kvm-pipeline
 job_timeout:
   minutes: 15            # timeout for the whole job (default: ??h)
 action_timeout:
   minutes: 5         # default timeout applied for each action; can be overriden in the action itself (default: ?h)
 priority: medium

In YAML, a list has a name, then a colon then an indented set of
items, each of which is preceded by a hyphen:

.. code-block:: yaml

 actions:
    - deploy:

Within a single action, like ``deploy``, the parameters for that
action are expressed as a hash (or dict in python terminology). In
YAML, this is presented as an indented block of lines **without** a
preceding hyphen.

.. code-block:: yaml

 actions:
    - deploy:
        timeout:
          minutes: 20
        to: tmpfs
        image: http://images.validation.linaro.org/kvm-debian-wheezy.img.gz
        os: debian

This stanza describes a deployment strategy where the timeout for the
entire deployment action is 20 minutes, the deployment happens to ``tmpfs``
(it is up to the python code for the strategy to work out what this means
or fail the validation of the pipeline). The deployment uses an ``image``
and the deployment data to be used is that for a Debian system.

As the refactoring proceeds, other media can be supported in the ``to``
instruction and other deployment types can be supported apart from
``image``. The final schema will need to express the available values
for deployment strategies, boot strategies and test strategies. A new
strategy will need support in the :ref:`yaml_device_type` for each
type which supports that strategy and in the python code to implement
a pipeline for that strategy.

The rest of the actions are listed in the same way - the name of the
top level Strategy Action class as a list item, the parameters for
that action class as a dictionary.

Individual actions and parameters are described under :ref:`dispatcher_actions`.

Sample JOB definition for a KVM
===============================

.. code-block:: yaml

 device_type: kvm

 job_name: kvm-pipeline
 job_timeout:
   minutes: 15            # timeout for the whole job (default: ??h)
 action_timeout:
   minutes: 5         # default timeout applied for each action; can be overriden in the action itself (default: ?h)
 priority: medium

 actions:

    - deploy:
        timeout:
          minutes: 20
        to: tmpfs
        image: http://images.validation.linaro.org/kvm-debian-wheezy.img.gz
        os: debian
        # if root_partition partition is not present:
        # - look for a partitions labelled "root" or "ROOT" or "Root" (i.e. case insensitive)
        # - look into device configuration
        root_partition: 1

    - boot:
        method: kvm
        media: tmpfs
        failure_retry: 2

    - test:
        failure_retry: 3
        name: kvm-basic-singlenode  # is not present, use "test $N"
        timeout:
          minutes: 5 # uses install:deps, so takes longer than singlenode01
        definitions:
            - repository: git://git.linaro.org/qa/test-definitions.git
              from: git
              path: ubuntu/smoke-tests-basic.yaml
              # name: if not present, use the name from the YAML. The name can
              # also be overriden from the actual commands being run by
              # calling the lava-test-suite-name API call (e.g.
              # `lava-test-suite-name FOO`).
              name: smoke-tests
            - repository: http://git.linaro.org/lava-team/lava-functional-tests.git
              from: git
              path: lava-test-shell/single-node/singlenode03.yaml
              name: singlenode-advanced

    - submit_results:
        stream: /anonymous/codehelp/

To see an example of how the sample YAML would look as a python snippet,
use the `Online YAML`_ Parser.

.. _yaml_device_type:

Basic structure for device_type configuration
=============================================

To take advantage of the new dispatcher design and to make the LAVA
device configuration more consistent, a new format is being created for
the device_type and device configuration files, again using YAML.

The device type outlines which strategies devices of this type are able
to support. The parameters and commands contained in the device_type
configuration will apply to all devices of this type.

The main block is a dictionary of actions. Each item is the name of the
strategy containing a list of arguments. All strategies require a
``method`` of how that strategy can be implemented. The methods supported
by this device type appear as a list.

.. code-block:: yaml

 actions:
  deploy:
    # list of deployment methods which this device supports
    methods:
      - image
    # no need for root-part, the MountAction will need to sort that out.

  boot:
    # list of boot methods which this device supports.
    methods:
      - qemu
    # Action specific stanza
    command:
      # allows for the one type to support different binaries
      amd64:
        qemu_binary: qemu-system-x86_64
    # only overrides can be overridden in the Job
    overrides:
      - boot_cmds
      - qemu_options
    parameters:
      boot_cmds:
        - root: /dev/sda1
        - console: ttyS0,115200
      qemu_options:
        - -nographic
      machine:
         accel=kvm:tcg
      net:
        - nic,model=virtio
        - user

.. _yaml_device:

Basic structure for device configuration
========================================

Individual devices then populate parameters for a specified device_type.
A device can only have one device_type.

.. code-block:: yaml

 device_type: kvm
 root_part: 1
 architecture: amd64
 memory: 512

.. _dispatcher_actions:

Dispatcher actions
******************

.. _mapping_yaml_to_code:

Mapping deployment actions to the python code
=============================================

#. See also :ref:`code_flow`
#. Start at the parser. Ensure that the parser can find the top level
   Strategy (the ``name`` in ``action_data``).
#. If a specific strategy class exists and is included in the parser,
   the Strategy class will be initialised with the current pipeline
   using the ``select`` classmethod of the strategy. Only subclasses
   of the Strategy class will be considered in the selection. The
   subclasses exist in the actions/ directory in a sub-directory named
   after the strategy and a python file named after the particular
   method.
#. The ``accepts`` classmethod of the Strategy subclass determines
   whether this subclass will be used for this job. Subclasses need to
   be imported into the parser to be considered. (``pylint`` will
   complain, so mark these import lines to disable ``unused-import``.)
#. The initialisation of the Strategy subclass instantiates the top-level
   Action for this Strategy.
#. The named Action then populates an internal pipeline when the Strategy
   subclass adds the top-level Action to the job pipeline.
#. Actions cascade, adding more internal pipelines and more Actions until
   the Strategy is complete. The Action instantiating the internal
   pipeline should generally be constrained to just that task as this
   makes it easier to implement RetryActions and other logical classes.
#. The parser moves on to the next Strategy.
#. If the parser has no explicit Strategy support, it will attempt to
   ``find`` an Action subclass which matches the requested strategy.
   This support may be removed once more strategies and Action
   sub-classes are defined.

Deployment actions
==================

Supported methods
-----------------

.. _image:

#. **image**

    An image deployment involves downloading the image and applying a
    LAVA overlay to the image using loopback mounts. The LAVA overlay
    includes scripts to automate the tests and the test definitions
    supplied to the ``test`` strategy.

   Example code block:

   .. code-block:: yaml

    - deploy:
        timeout:
          minutes: 20
        to: tmpfs
        image: http://images.validation.linaro.org/kvm-debian-wheezy.img.gz
        os: debian
        # if root_partition partition is not present:
        # - look for a partitions labelled "root" or "ROOT" or "Root" (i.e. case insensitive)
        # - look into device configuration
        root_partition: 1

Boot actions
============

Supported methods
-----------------

#. **kvm**

   The KVM method uses QEMU to boot an image which has been downloaded
   and had a LAVA overlay applied using an :ref:`Image <image>` deployment.

   Example code block:

   .. code-block:: yaml

       - boot:
        method: kvm
        media: tmpfs
        failure_retry: 2



Test actions
============

Currently, there is only one Test strategy and the method for
distinguishing between this and any later strategy has not been
finalised.

Example code block:

.. code-block:: yaml

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
              # name: if not present, use the name from the YAML. The name can
              # also be overriden from the actual commands being run by
              # calling the lava-test-suite-name API call (e.g.
              # `lava-test-suite-name FOO`).
              name: smoke-tests
            - repository: http://git.linaro.org/lava-team/lava-functional-tests.git
              from: git
              path: lava-test-shell/single-node/singlenode03.yaml
              name: singlenode-advanced


Submit actions
==============

The submission back to the server web frontend will include the entire
pipeline but the methods for doing this have not yet been written.
