.. _test_developer:

Introduction to the LAVA Test Developer Guide
#############################################

This guide aims to enable engineers to be able to

#. Submit desired jobs/tests on target deployed where the LAVA server
   is located and report results.
#. Understand how .json file need to be written so that jobs get
   submitted properly.
#. Understand how test files (.yaml) need to be written.

Ensure you have read through the introduction on
:ref:`writing_tests`.

Pay particular attention to sections on:

* :ref:`json_contents`
* :ref:`basic_json`
* :ref:`yaml_contents`
* :ref:`writing_test_commands`
* :ref:`custom_scripts`
* :ref:`best_practices`

Guide Contents
**************

* :ref:`available_actions`
* :ref:`lava_test_shell`
* :ref:`multinode`
* :ref:`boot_management`
* :ref:`deploy_bootloader`
* :ref:`hooks_external_measurement`

Assumptions at the start of this guide
**************************************

#. The desired board is already deployed at the LAVA Server location.
#. A bundle stream for your test results is already created by the LAVA
   administrator on your behalf.
#. A user account (username, password, email address) is already created
   by a LAVA administrator on your behalf, with permissions to submit jobs.
#. You are running Ubuntu 12.04. All steps have been tested on Ubuntu
   12.04LTS (precise pangolin) so if you are using some other variant or
   distribution your results may vary.
#. ``lava-tool`` is already installed on your test system and a suitable
   token has been added.
#. You are familiar with submitting jobs written by someone else, including
   viewing the log file for a job, viewing the definition used for that
   job and accessing the complete log.

If your desired board is not available in the LAVA instance you want to
use, see :ref:`deploy_boards`.

If a suitable bundle stream does not exist, see :ref:`bundle_stream`.

To install ``lava-tool``, see :ref:`lava_tool`.

To authenticate ``lava-tool``, see :ref:`authentication_tokens`.

To find out more about submitting tests written by someone else, see
:ref:`submit_first_job`.

To find out more about viewing job details, see :ref:`job_submission`.

.. index:: availability

Checking device availability
****************************

Use the LAVA scheduler to view available device types and devices. The
main scheduler status page shows data for each :term:`device type` as
well as the currently active jobs. Also check the Devices pages:

* All Devices - includes retired devices to which jobs cannot be
  submitted.
* All Active Devices - lists only devices to which jobs can be submitted
* All Devices Health - limited to just the latest health status of each
  device.

.. Add details of My Devices table when it is ready to cover the
   limitation below.

.. note:: One or more of the devices of the type you want could be a :term:`restricted device`
   so that even if it is Idle, you may not have permission to submit to that
   device. See :ref:`device_capabilities`.

For a :ref:`multinode` job, you may need to check more than one
:term:`device type`.

Devices are considered available for new jobs according to the
:ref:`device_status`.

* Idle, Reserved, Offline, Offlining - jobs can be submitted.
* restricted - only available for submissions made by declared users.
* Retired - jobs will be rejected if all remaining devices of this type
  are retired.

Finding an image to run on the device
*************************************

Start with an image which is already in use in LAVA. You can find one
of these images by checking the :term:`device type` in LAVA and viewing
some of the jobs for devices of this type from the table on that page.
e.g. for KVM devices on validation.linaro.org:

https://validation.linaro.org/scheduler/device_type/kvm

The :term:`job definition` will provide information on the image or the
:ref:`interactive_boot_cmds` which started the job.

Actions to be run for a LAVA test
*********************************

#. Deploy an image:

   #. :ref:`deploy_linaro_image`
   #. :ref:`deploy_linaro_kernel`
   #. :ref:`interactive_boot_cmds`

#. Boot the image into a test shell

   #. :ref:`lava_test_shell` - supports multiple :ref:`test_repos`.

#. Submit results

   #. :ref:`initial_json_actions`

Actions to be run to simply deploy without tests
************************************************

#. Deploy an image:

   #. :ref:`deploy_linaro_image`
   #. :ref:`deploy_linaro_kernel`
   #. :ref:`interactive_boot_cmds`

#. Boot the image without tests

   #. :ref:`boot_linaro_image` - no support for :ref:`test_repos`.

#. Submit results

   #. :ref:`initial_json_actions`


Examples
********

Deploying a pre-built image to a device
=======================================

::

 {
    "job_name": "panda-prebuilt",
    "target": "panda01",
    "timeout": 18000,
    "actions": [
        {
            "command": "deploy_linaro_image",
            "parameters": {
                "image": "http://releases.linaro.org/12.09/ubuntu/leb-panda/lt-panda-x11-base-precise_ubuntu-desktop_20120924-329.img.gz"
            }
        },
        {
            "command": "boot_linaro_image"
        },
        {
            "command": "submit_results",
            "parameters": {
                "server": "http://localhost/lava-server/RPC2/",
                "stream": "/anonymous/test/"
            }
        }
    ]
 }

Deploying an image using linaro-media-create
============================================

::

 {
    "job_name": "panda-lmc",
    "target": "panda01",
    "timeout": 18000,
    "actions": [
        {
            "command": "deploy_linaro_image",
            "parameters": {
                "rootfs": "http://releases.linaro.org/12.09/ubuntu/precise-images/nano/linaro-precise-nano-20120923-417.tar.gz",
                "hwpack": "http://releases.linaro.org/12.09/ubuntu/leb-panda/hwpack_linaro-lt-panda-x11-base_20120924-329_armhf_supported.tar.gz"
            }
        },
        {
            "command": "boot_linaro_image"
        },
        {
            "command": "submit_results",
            "parameters": {
                "server": "http://localhost/lava-server/RPC2/",
                "stream": "/anonymous/test/"
            }
        }
    ]
 }

Deploying an Android image
==========================

::

 {
    "job_name": "android_test",
    "target": "panda01",
    "timeout": 18000,
    "actions": [
        {
            "command": "deploy_linaro_android_image",
            "parameters": {
                "boot": "http://releases.linaro.org/12.09/android/leb-panda/boot.tar.bz2",
                "system": "http://releases.linaro.org/12.09/android/leb-panda/system.tar.bz2",
                "data": "http://releases.linaro.org/12.09/android/leb-panda/userdata.tar.bz2"
            }
        },
        {
            "command": "boot_linaro_android_image"
        },
        {
            "command": "lava_android_test_install",
            "parameters": {
                "tests": [
                    "0xbench"
                ]
            }
        },
        {
            "command": "lava_android_test_run",
            "parameters": {
                "test_name": "0xbench"
            }
        },
        {
            "command": "submit_results_on_host",
            "parameters": {
                "server": "http://validation.linaro.org/lava-server/RPC2/",
                "stream": "/anonymous/lava-android-leb-panda/"
            }
        }
    ]
 }

.. _device_tags_example:

Using device tags
=================

A :term:`device tag` marks a specified device as having specific hardware
capabilities which other devices of the same :term:`device type` do not.
To test these capabilities, a Test Job can specify a list of tags which
the device **must** support. If no devices exist which match all of the
required tags, the job submission will fail. If devices support a wider
range of tags than required in the Test Job (or the Test Job requires
no tags), any of those devices can be used for the Test Job.

.. note:: Test jobs which use :term:`device tag` support can **only** be
          submitted to instances which have those tags defined **and**
          assigned to the requested boards. Check the device information
          on the instance to get the correct tag information.

Singlenode example
------------------

::

 {
    "job_name": "panda-lmc",
    "target": "panda01",
    "timeout": 18000,
    "tags": [
        "hdmi",
        "usbstick"
    ]
    "actions": [
        {
            "command": "deploy_linaro_image",
            "parameters": {
                "rootfs": "http://releases.linaro.org/12.09/ubuntu/precise-images/nano/linaro-precise-nano-20120923-417.tar.gz",
                "hwpack": "http://releases.linaro.org/12.09/ubuntu/leb-panda/hwpack_linaro-lt-panda-x11-base_20120924-329_armhf_supported.tar.gz"
            }
        },
        {
            "command": "boot_linaro_image"
        },
        {
            "command": "submit_results",
            "parameters": {
                "server": "http://localhost/RPC2/",
                "stream": "/anonymous/test/"
            }
        }
    ]
 }

Multinode example
-----------------

::

 {
    "health_check": false,
    "logging_level": "DEBUG",
    "timeout": 900,
    "job_name": "multinode-example",
    "device_group": [
        {
            "role": "felix",
            "count": 1,
            "device_type": "kvm",
            "tags": [
                "hdmi",
                "sata"
            ]
        },
        {
            "role": "rex",
            "count": 1,
            "device_type": "kvm",
            "tags": [
                "usbstick"
            ]
        }
    ],
    "actions": [
        {
            "command": "deploy_linaro_image",
            "parameters": {
                "image": "http://images.validation.linaro.org/kvm-debian-wheezy.img.gz"
            }
        },
        {
            "command": "boot_linaro_image"
        },
        {
            "command": "submit_results_on_host",
            "parameters": {
                "stream": "/anonymous/codehelp/",
                "server": "http://localhost/RPC2/"
            }
        }
    ]
 }


Installing Binary Blobs
=======================

Some Android builds for Panda require a binary blob to be installed. This can
be done by adding the ``android_install_binaries`` after the
``deploy_linaro_android_image``::

 {
    "actions": [
        {
            "command": "deploy_linaro_android_image",
            "parameters": {
                "boot": "http://releases.linaro.org/12.09/android/leb-panda/boot.tar.bz2",
                "system": "http://releases.linaro.org/12.09/android/leb-panda/system.tar.bz2",
                "data": "http://releases.linaro.org/12.09/android/leb-panda/userdata.tar.bz2"
            }
        },
        {
            "command": "android_install_binaries"
        }
    ]
 }

Executing Tests on Android
==========================

Tests are executed on Android  by adding a ``lava_android_test_install`` and
``lava_android_test_run`` action to your base job file::

 {
    "actions": [
        {
            "command": "lava_android_test_install",
            "parameters": {
                "tests": [
                    "busybox"
                ]
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
        }
    ]
 }

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
To pass parameters to variables in YAML files, see :ref:`test_repos`.

.. index:: parameters

If your test definitions can be downloaded by a url link then
``lava_test_shell`` can automatically download the test definition from
the url and execute it. The format is::

 {
    "command": "lava_test_shell",
    "parameters": {
        "testdef_repos": [
            {
                "url": "file:///home/tekkamanninja/json_file/repo_parameter/lmp-test-c.yaml",
                "parameters": {
                    "TEST_1": "pass"
                }
            }
        ],
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
            {
                "git-repo": "git://git.linaro.org/people/stylesen/sampletestdefs.git",
                "revision": "91df22796f904677c0fe5df787fc04234bf97691",
                "testdef": "testdef.yaml",
                "parameters": {
                    "TEST_1": "pass"
                }
            }
        ],
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
            {
                "bzr-repo": "lp:~stylesen/lava-dispatcher/sampletestdefs-bzr",
                "revision": "1",
                "testdef": "testdef.yaml",
                "parameters": {
                    "TEST_1": "pass"
                }
            }
        ],
        "timeout": 1800
    }
 }

In both the above formats "revision", "testdef" and "parameters" are
optional. If "revision" is not specified then the latest revision in
the repository is cloned. If there is no "testdef" specified, then inside
the cloned directory of the repository a file with name "lavatest.yaml" is
looked up which is the default name for test definitions. The "testdef"
parameter could be used in order to override the default name for test
definition file. The "parameters" could be used in order to pass the
parameters for those variables, If your test definition file include
Shell variables in "install" and "run" sections.

.. seealso:: ``lava_test_shell`` `developer documentation <lava_test_shell.html>`_

.. _testdef_repos:

Passing parameters to test definition variables, the format should be like this::

 {
    "parameters": {
        "VARIABLE_NAME_1": "value_1",
        "VARIABLE_NAME_2": "value_2"
    }
 }

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
