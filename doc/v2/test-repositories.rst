.. _test_repos:

Test definitions in version control
###################################

FIXME! This is still talking about JSON everywhere!

LAVA supports git and bzr version control for use with test
definitions, and this is the recommended way to host and use test
definitions for LAVA. When a repository is listed in a test
definition, the entire repository is checked out. This allows YAML
files in the repository to reliably access scripts and other files
which are part of the repository, inside the test image.::

 {
    "command": "lava_test_shell",
    "parameters": {
        "testdef_repos": [
            {
                "git-repo": "https://git.linaro.org/people/neil.williams/temp-functional-tests.git",
                "testdef": "multinode/multinode02.yaml"
            }
        ],
        "timeout": 900
    }
 }

When this test starts, the entire repository will be available in the
current working directory of the test. Therefore,
``multinode/multinode02.yaml`` can include instructions to execute
``multinode/get_ip.sh``.

Job definitions in version control
**********************************

FIXME! JSON

It is normally recommended to also store your test job YAML files in
the repository. This helps others who may want to use your test
definitions, but it is also useful when using the **Submit Job**
support in the LAVA web interface. Simply enter the full path to the
test job YAML file in your repository and LAVA will replace the URL
with the contents of the file before submission.::

  https://git.linaro.org/people/neil.williams/temp-functional-tests.git/blob_plain/HEAD:/singlenode/kvm-single-node.json

(When copying and pasting this example, ensure you remove the
trailing line ending and paste only a single line.)

There are numerous test repositories in use daily in Linaro that may
be good examples for you, including:

* https://git.linaro.org/lava-team/lava-functional-tests.git
* https://git.linaro.org/qa/test-definitions.git

Using specific revisions of a test definition
*********************************************

If a specific revision is specified as a parameter in the JSON, that
revision of the repository will be used instead of HEAD.::

 {
    "command": "lava_test_shell",
    "parameters": {
        "testdef_repos": [
            {
                "git-repo": "https://git.linaro.org/people/neil.williams/temp-functional-tests.git",
                "testdef": "multinode/multinode02.yaml",
                "revision": "3d555378"
            }
        ],
        "timeout": 900
    }
 }

Sharing the contents of test definitions
****************************************

A YAML test definition file can clone another repository by specifying
the address of the repository to clone::

  install:
      bzr-repos:
          - lp:lava-test
      git-repos:
          - git://git.linaro.org/people/davelong/lt_ti_lava.git

  run:
      steps:
          - cd lt_ti_lava
          - echo "now in the git cloned directory"

This allows a collection of LAVA test definitions to re-use other YAML
custom scripts without duplication. The tests inside the other repository
will **not** be executed.

.. index:: test definition dependencies

Adding test definition dependencies
***********************************

If your test depends on other tests to be executed before you run the
current test, add an explicit dependency in the test definition YAML::

 test-case-deps:
   - git-repo: git://git.linaro.org/qa/test-definitions.git
     testdef: common/passfail.yaml
   - bzr-repo: lp:~stylesen/lava-dispatcher/sampletestdefs-bzr
     testdef: testdef.yaml
   - url: https://people.linaro.org/~senthil.kumaran/deps_sample.yaml

The test cases specified within ``test-case-deps`` section will be fetched
from the given repositories or url and then executed in the same specified
order.

Test repository for functional tests in LAVA
********************************************

LAVA regularly runs a set of test definitions to check for regressions
and the set is available for others to use as a template for their
own tests::

* https://git.linaro.org/lava-team/lava-functional-tests.git
