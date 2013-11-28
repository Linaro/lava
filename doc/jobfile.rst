.. _jobfile:

Writing a Dispatcher Job File
*****************************
There are dozens of permutations for creating job files in the dispatcher.
This page goes through some common scenarios:

The base skeleton job files should look like:

 * `Deploy a Pre-Built Image <jobfile-prebuilt.html>`_
 * `Deploy Using linaro-media-create <jobfile-lmc.html>`_
 * `Deploy an Android Image <jobfile-android.html>`_

**NOTE:** Each of the above jobs uses the ``target`` parameter to specify the
exact target to run the job on. If submitting a job via the scheduler, you'll
likely want to just choose the ``device_type`` and let the scheduler find an
idle device for you. This is done by removing the target line and adding::

        "device_type": "panda",

Executing Tests on Ubuntu
=========================

Tests are executed on Ubuntu by adding a ``lava_test_install`` and
``lava_test_run`` action to your base job file::

    {
        "command": "lava_test_install",
        "parameters": {
            "tests": ["stream"]
        }
    },
    {
        "command": "boot_linaro_image"
    },
    {
        "command": "lava_test_run",
        "parameters": {
            "test_name": "stream"
        }
    },

**NOTE:** The ``lava_test_install`` action should follow the
``deploy_linaro_image`` action.

Executing Tests on Android
==========================

Tests are executed on Android  by adding a ``lava_android_test_install`` and
``lava_android_test_run`` action to your base job file::

    {
        "command": "lava_android_test_install",
        "parameters": {
            "tests": ["busybox"]
        }
    },
    {
        "command": "boot_linaro_android_image"
    },
    {
        "command": "lava_android_test_run",
        "parameters": {
            "test_name": "busybox"
        }
    },

Using LAVA Test Shell
=====================
The ``lava_test_shell`` action provides a way to employ a more black-box style
testing approach with the target device. The action only requires that a
deploy action (deploy_linaro_image/deploy_linaro_android_image) has been
executed. Its format is::

    {
        "command": "lava_test_shell",
        "parameters": {
            "testdef_urls": [
                "http://people.linaro.org/~doanac/lava/lava_test_shell/testdefs/lava-test.yaml"
            ],
            "timeout": 1800
        }
    }

You can put multiple test definition URLs in "testdef_urls"
section. The "testdef_urls" section takes a list of strings which are
URLs. These will be run sequentially without reboot. Alternatively,
you can specify each URL in a separate ``lava_test_shell`` action
which will allow for a reboot between each test.

But "testdef_urls" can't support "parameters" function.
To pass parameters to variables in YAML files, see :ref:`testdef_repos`.

If your test definitions can be downloaded by a url link then
``lava_test_shell`` can automatically download the test definition from
the url and execute it. The format is::

    {
      "command": "lava_test_shell",
      "parameters": {
          "testdef_repos": [
              {"url": "file:///home/tekkamanninja/json_file/repo_parameter/lmp-test-c.yaml",
               "parameters": {"TEST_1": "pass"}
              }],
      "timeout": 1800
      }
    }

.. caution:: When using "url" in "testdef_repos", **lava-dispatcher will ignore**
 ```revision``` and ```testdef```.

If your test definitions are available in a git repository then
``lava_test_shell`` can automatically pull the test definition from
the git repository and execute it. The format is::

    {
      "command": "lava_test_shell",
      "parameters": {
          "testdef_repos": [
              {"git-repo": "git://git.linaro.org/people/stylesen/sampletestdefs.git",
               "revision": "91df22796f904677c0fe5df787fc04234bf97691",
               "testdef": "testdef.yaml",
               "parameters": {"TEST_1": "pass"}
              }],
      "timeout": 1800
      }
    }

Alternatively, if your test definitions are available in a bzr repository then
``lava_test_shell`` can automatically pull the test definition from
the bzr repository and execute it. The format is::

    {
      "command": "lava_test_shell",
      "parameters": {
          "testdef_repos": [
              {"bzr-repo": "lp:~stylesen/lava-dispatcher/sampletestdefs-bzr",
               "revision": "1",
               "testdef": "testdef.yaml",
               "parameters": {"TEST_1": "pass"}
              }],
      "timeout": 1800
      }
    },

In both the above formats "revision", "testdef" and "parameters" are
optional. If "revision" is not specified then the latest revision in
the repository is cloned. If there is no "testdef" specified, then inside
the cloned directory of the repository a file with name "lavatest.yaml" is
looked up which is the default name for test definitions. The "testdef"
parameter could be used in order to override the default name for test
definition file. The "parameters" could be used in order to pass the
parameters for those variables, If your test definition file include
Shell variables in "install" and "run" sections.

.. seealso:: The test definition format for `lava_test_shell actions <lava_test_shell.html>`_

             Developer documentation for `lava_test_shell <http://validation.linaro.org/static/docs/lava-dispatcher/lava_test_shell.html>`_

.. _testdef_repos:

Passing parameters to test definition variables, the format should be like this::

    "parameters": {"VARIABLE_NAME_1" : "value_1", "VARIABLE_NAME_2" : "value_2"}

If you didn't use "parameters" here, the lava-dispatcher will use the default
values that defined in your test definition file.

Adding Meta-Data
================

Both deploy actions support an optional field, ``metadata``. The value of this
option is a set of key-value pairs like::

    {
        "command": "deploy_linaro_image",
        "parameters": {
            "image": "http://releases.linaro.org/12.09/ubuntu/leb-panda/lt-panda-x11-base-precise_ubuntu-desktop_20120924-329.img.gz",
            "metadata": {
                "ubuntu.image_type": "ubuntu-desktop",
                "ubuntu.build": "61"
            }
        }
    }

This data will be uploaded into the LAVA dashboard when the results are
submitted and can then be used as filter criteria for finding data.
