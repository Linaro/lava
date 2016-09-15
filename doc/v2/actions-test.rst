.. _test_action:

Test Action Reference
#####################

The pipeline has retained compatibility with respect to the content of
Lava-Test-Shell Test Definitions although the submission format has changed:

#. The :ref:`test_action` will **never** boot the device - a :ref:`boot_action`
   **must** be specified. Multiple test operations need to be specified as
   multiple definitions listed within the same test block.

#. The LAVA support scripts are prepared by the :ref:`deploy_action` action
   and the same scripts will be used for all test definitions until another
   ``deploy`` block is encountered.

.. note:: There is a FIXME outstanding to ensure that only the test definitions
   listed in this block are executed for that test action - this allows
   different tests to be run after different boot actions, within the one
   deployment.

::

  - test:
     failure_retry: 3

.. contents::
   :backlinks: top

.. _test_action_definitions:

Definitions
***********

repository
==========

a publicly readable repository location.

from
====

the type of the repository is **not** guessed, it **must** be specified
explicitly. Support is planned for ``bzr``, ``url``, ``file`` and ``tar``.

git
---

a remote git repository which needs to be cloned by the dispatcher.

inline
------

 a simple test definition present in the same file as the job submission,
 instead of from a separate file or VCS repository. This allows tests to be run
 based on a single file. When combined with ``file://`` URLs to the ``deploy``
 parameters, this allows tests to run without needing external access. See
 :ref:`inline_test_definition_example`.

path
----

the path within that repository to the YAML file containing the test
definition.

name
----

(required) - replaces the name from the YAML.

params
------

(optional): Pass parameters to the Lava Test Shell Definition. The format is a
YAML dictionary - the key is the name of the variable to be made available to
the test shell, the value is the value of that variable.

.. code-block:: yaml

 definitions:
     - repository: https://git.linaro.org/lava-team/hacking-session.git
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
         - repository: https://git.linaro.org/lava-team/lava-functional-tests.git
           from: git
           path: lava-test-shell/single-node/singlenode03.yaml
           name: singlenode-advanced

Skipping elements of test definitions
=====================================

When a single test definition is to be used across multiple deployment types
(e.g. Debian and OpenEmbedded), it may become necessary to only perform certain
actions within that definition in specific jobs. The ``skip_install`` support
has been migrated from V1 for compatibility. Other methods of optimising test
definitions for specific deployments may be implemented in V2 later.

The available steps which can be (individually) skipped are:

deps
----

skip running ``lava-install-packages`` for the ``deps:`` list of the
``install:`` section of the definition.

keys
----

skip running ``lava-add-keys`` for the ``keys:`` list of the ``install:``
section of the definition.

sources
-------

skip running ``lava-add-sources`` for the ``sources:`` list of the ``install:``
section of the definition.

steps
-----

skip running any of the ``steps:``of the ``install:`` section of the
definition.

all
---

identical to ``['deps', 'keys', 'sources', 'steps']``

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

The following will skip dependency installation and key addition in
the same definition:

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


Additional support
==================

The V2 dispatcher supports some additional elements in Lava Test Shell which
will not be supported in the older V1 dispatcher.

Result checks
-------------

LAVA collects results from internal operations as well as from the submitted
test definitions, these form the ``lava`` test suite results. The full set of
results for a job are available at::

 results/1234

LAVA records when a submitted test definition starts execution on the test
device. If the number of test definitions which started is not the same as the
number of test definitions submitted (allowing for the ``lava`` test suite
results), a warning will be displayed on this page.

TestSets
--------

A TestSet is a group of lava test cases which will be collated within the LAVA
Results. This allows queries to look at a set of related test cases within a
single definition.

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

This results in the ``date`` and ``mount`` test cases being included into a
``first_set`` TestSet, independent of other test cases. The TestSet is
concluded with the ``lava-test-set stop`` command, meaning that the ``uname``
test case has no test set, providing a structure like:

.. code-block:: yaml

 results:
   first_set:
     date: pass
     mount: pass
   uname: pass

.. code-block:: python

 {'results': {'first_set': {'date': 'pass', 'mount': 'pass'}, 'uname': 'pass'}}

Each TestSet name must be valid as a URL, which is consistent with the
requirements for test definition names and test case names in the V1
dispatcher.

For TestJob ``1234``, the ``uname`` test case would appear as::

 results/1234/testset-def/uname

The ``date`` and ``mount`` test cases are referenced via the TestSet::

 results/1234/testset-def/first_set/date
 results/1234/testset-def/first_set/mount

A single test definition can start and stop different TestSets in sequence, as
long as the name of each TestSet is unique for that test definition.
