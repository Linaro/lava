.. index:: test definition repository

.. _test_repos:

Test definitions in version control
###################################

LAVA supports git and bzr version control for use with test definitions, and
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

  https://git.linaro.org/lava-team/refactoring.git/blob_plain/HEAD:/panda-multinode.yaml

There are numerous test repositories in use daily in Linaro that may be good
examples for you, including:

* https://git.linaro.org/lava-team/lava-functional-tests.git
* https://git.linaro.org/qa/test-definitions.git

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
        - repository: git://git.linaro.org/qa/test-definitions.git
          from: git
          path: ubuntu/smoke-tests-basic.yaml
          name: smoke-tests
        - repository: http://git.linaro.org/lava-team/lava-functional-tests.git
          from: git
          path: lava-test-shell/single-node/singlenode03.yaml
          name: singlenode-advanced
          revision: 441b61

Sharing the contents of test definitions
****************************************

A YAML test definition file can clone another repository by specifying the
address of the repository to clone

.. code-block:: yaml

  install:
      bzr-repos:
          - lp:lava-test
      git-repos:
          - git://git.linaro.org/people/davelong/lt_ti_lava.git

  run:
      steps:
          - cd lt_ti_lava
          - echo "now in the git cloned directory"

This allows a collection of LAVA test definitions to re-use other YAML custom
scripts without duplication. The tests inside the other repository will **not**
be executed.

.. index:: test definition dependencies

Adding test definition dependencies
***********************************

If your test depends on other tests to be executed before you run the current
test, add an explicit dependency in the test definition YAML:

.. code-block:: yaml

 test-case-deps:
   - git-repo: git://git.linaro.org/qa/test-definitions.git
     testdef: common/passfail.yaml
   - bzr-repo: lp:~stylesen/lava-dispatcher/sampletestdefs-bzr
     testdef: testdef.yaml
   - url: https://people.linaro.org/~senthil.kumaran/deps_sample.yaml

The test cases specified within ``test-case-deps`` section will be fetched from
the given repositories or url and then executed in the same specified order.

Test repository for functional tests in LAVA
********************************************

LAVA regularly runs a set of test definitions to check for regressions and the
set is available for others to use as a template for their own tests::

* https://git.linaro.org/lava-team/lava-functional-tests.git
