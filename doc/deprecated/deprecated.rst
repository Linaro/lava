.. index:: deprecated

.. _deprecated_features:

Deprecated features
###################

All features of the current dispatcher and some features of the server
UI which are bound to features of the current dispatcher are deprecated
in favour of the :term:`pipeline`. Support for these features will be
removed in a future release.

.. index:: submit_json

.. _submit_json_job:

Submitting a *JSON* job
***********************

A job defines what image to deploy on the DUT and further actions that
should be performed on the DUT. JSON jobs are supported until such time
as support becomes available in the :term:`pipeline` and the teams can
migrate to the new jobs.

Job Definition
==============

Here's a minimal job that could be executed ::

    {
      "job_name": "kvm-test",
      "device_type": "kvm",
      "timeout": 1800,
      "actions": [
        {
          "command": "deploy_linaro_image",
          "parameters":
            {
              "image": "http://images.validation.linaro.org/kvm-debian-wheezy.img.gz"
            }
        },
        {
          "command": "boot_linaro_image"
        },
        {
          "command": "submit_results",
          "parameters":
            {
              "server": "http://<username>@validation.linaro.org/RPC2/",
              "stream": "/anonymous/test/"
            }
        }
      ]
    }

.. note:: Replace *username* with your username.

JSON and test definitions
=========================

In order to run a test definition with a minimal *JSON* job file, the
following job json could be used and submitted using the command line
or the web UI ::

  {
      "job_name": "kvm-test",
      "device_type": "kvm",
      "timeout": 1800,
      "actions": [
          {
              "command": "deploy_linaro_image",
              "parameters": {
                  "image":
                  "http://images.validation.linaro.org/kvm-debian-wheezy.img.gz"
              }
          },
          {
              "command": "lava_test_shell",
              "parameters": {
                  "testdef_urls": [
                      "http://people.linaro.org/~senthil.kumaran/test.yaml"
                  ]
              }
          },
          {
              "command": "boot_linaro_image"
          },
          {
              "command": "submit_results",
              "parameters": {
                  "server":
                  "http://stylesen@validation.linaro.org/RPC2/",
                  "stream": "/anonymous/test/"
              }
          }
      ]
  }

.. note:: The test definition is uploaded to an URL that will be
          accessible over http which is referred in the job json.

.. note:: Test definitions could be referred from git
          repositories. The official upstream Linaro git repository
          for test definitions is
          https://git.linaro.org/gitweb?p=qa/test-definitions.git

.. _writing_json_tests:

Writing a LAVA test using JSON
******************************

A LAVA Test Definition comprises of two parts:

#. the data to setup the test, expressed as a JSON file.
#. the instructions to run inside the test, expressed as a YAML file.

This allows the same tests to be easily migrated to a range of different
devices, environments and purposes by using the same YAML files in
multiple JSON files. It also allows tests to be built from a range of
components by aggregating YAML files inside a single JSON file.

.. _json_contents:

Contents of the JSON file
=========================

The JSON file is submitted to the LAVA server and contains:

#. Demarcation as a :term:`health check` or a user test.
#. The default timeout of each action within the test.
#. The :term:`logging level` for the test, DEBUG or INFO.
#. The name of the test, shown in the list of jobs.
#. The location of all support files.
#. All parameters necessary to use the support files.
#. The declaration of which device(s) to use for the test.
#. The location to which the results should be uploaded.

The JSON determines how the test is deployed onto the device and
where to find the tests to be run.

All user tests should use::

    "health_check": false,

See :ref:`health_checks`.

Multiple tests can be defined in a single JSON file by listing multiple
locations of YAML files. Each set of instructions in the YAML files can
be run with or without a reboot between each set.

If a test needs to use more than one device, it is the JSON file which
determines which other devices are available within the test and how
the test(s) are deployed to the devices in the group.

Support files
=============

These include:

#. Files to boot the device: Root filesystem images, kernel images,
   device tree blobs, bootloader parameters
#. Files containing the tests: The YAML files, either alone or as part
   of a repository, are added to the test by LAVA.

.. expand this section to go through each way of specifying support
   files by summaries with links to full sections.

Using local files
------------------

Support files do not need to be at remote locations, all files specified
in the JSON can be local to the :term:`dispatcher` executing the test. This
is useful for local tests on your own LAVA instance, simply ensure that
you use the ``file://`` protocol for support files. Note that a local
YAML file will still need to download any custom scripts and required
packages from a remote location.

.. _initial_json_actions:

Initial actions in the JSON
===========================

The simplest tests involve using a pre-built image, a test definition
and submission of the results to the server.

Actions defined in the JSON will be executed in the order specified
in the JSON file, so a deployment is typically followed by a
test shell and then submission of results.

#. **deploy_linaro_image** : Download a complete image (usually but not
   necessarily compressed) containing the kernel, kernel modules and
   root filesystem. The LAVA overlay will be applied on top before the
   image boots, to provide access to the LAVA test tools and the test
   definitions defined in the subsequent ``actions``.
#. **lava_test_shell** : Boots the deployed image and starts the
   ``lava_test_runner`` which starts the execution of the commands
   defined in the YAML.
#. **submit_results_on_host** : (Equivalent to **submit_results**)
   Collects the result data from the image after the completion of
   all the commands in the YAML and submits a bundle containing the
   results and metadata about the job to the server, to be added to
   the :term:`bundle stream` listed in the submission. These result bundles can then
   be viewed, downloaded and used in filters and reports.

See :ref:`available_actions`

.. _basic_json:

Basic JSON file
===============

Your first LAVA test should use DEBUG logging so that it is easier
to see what is happening.

See :ref:`timeouts` for detailed information on how LAVA handles the
timeouts. A suitable example for your first tests is 900 seconds.

Make the ``job_name`` descriptive and explanatory, you will want to be
able to tell which job is which when reviewing the results.

Make sure the :term:`device type` matches exactly with one of the suitable
device types listed on the server to which you want to submit this job.

Change the :term:`stream` to one to which you are allowed to upload results,
on your chosen server. If you use ``localhost``, note that this will
be replaced by the fully qualified domain name of the server to which
the job is submitted.

::

 {
    "health_check": false,
    "logging_level": "DEBUG",
    "timeout": 900,
    "job_name": "kvm-basic-test",
    "device_type": "kvm",
    "actions": [
        {
            "command": "deploy_linaro_image",
            "parameters": {
                "image": "http://images.validation.linaro.org/kvm-debian-wheezy.img.gz"
            }
        },
        {
            "command": "lava_test_shell",
            "parameters": {
                "testdef_repos": [
                    {
                        "git-repo": "git://git.linaro.org/qa/test-definitions.git",
                        "testdef": "ubuntu/smoke-tests-basic.yaml"
                    }
                ],
                "timeout": 900
            }
        },
        {
            "command": "submit_results_on_host",
            "parameters": {
                "stream": "/anonymous/example/",
                "server": "http://localhost/RPC2/"
            }
        }
    ]
 }

.. note:: Always check your JSON syntax. A useful site for this is
          http://jsonlint.com.

For more on the contents of the JSON file and how to construct JSON
for devices known to LAVA or devices new to LAVA, see the
:ref:`test_developer`.

Best practices for writing a LAVA JSON job
******************************************

Use a limited number of test definitions per job
================================================

Whilst LAVA tries to ensure that all tests are run, endlessly adding
test repositories to a single LAVA job only increases the risk that
one test will fail in a way that prevents the results from all tests
being collected.

Overly long sets of test definitions also increase the complexity of
the log files and the result bundles, making it hard to identify why
a particular job failed.

LAVA supports filters and image reports to combine result bundles into
a single analysis.

LAVA also support retrieving individual result bundles using ``lava-tool``
so that the bundles can be aggregated outside LAVA for whatever tests
and export the script writer chooses to use.

Splitting a large job into smaller chunks also means that the device can
run other jobs for other users in between the smaller jobs.

.. _tests_and_reboots:

Minimise the number of reboots within a single test
===================================================

In many cases, if a test definition needs to be isolated from another
test case by a reboot (to prevent data pollution etc.) it is likely that
the tests can be split into different LAVA jobs.

To run two test definitions without a reboot, simply combine the JSON
to not use two ``lava_test_shell`` commands::

        {
            "command": "lava_test_shell",
            "parameters": {
                "testdef_repos": [
                    {
                        "git-repo": "git://git.linaro.org/qa/test-definitions.git",
                        "testdef": "ubuntu/smoke-tests-basic.yaml"
                    }
                ],
                "timeout": 900
            }
        },
        {
            "command": "lava_test_shell",
            "parameters": {
                "testdef_repos": [
                    {
                        "git-repo": "https://git.linaro.org/people/neil.williams/temp-functional-tests.git",
                        "testdef": "singlenode/singlenode01.yaml"
                    }
                ],
                "timeout": 900
            }
        }

Becomes::

        {
            "command": "lava_test_shell",
            "parameters": {
                "testdef_repos": [
                    {
                        "git-repo": "git://git.linaro.org/qa/test-definitions.git",
                        "testdef": "ubuntu/smoke-tests-basic.yaml"
                    },
                    {
                        "git-repo": "https://git.linaro.org/people/neil.williams/temp-functional-tests.git",
                        "testdef": "singlenode/singlenode01.yaml"
                    }
                ],
                "timeout": 900
            }
        },

A note on Heartbeat
===================

The heartbeat data of the dispatcher node is sent to the database via
xmlrpc. For this feature to work correctly the ``rpc2_url`` parameter
should be set properly. Login as an admin user and go to
``http://localhost/admin/lava_scheduler_app/worker/``. Click on the
machine which is your master (in case of distributed deployment), or
the machine that is listed in the page (in case of single LAVA instance).
In the page that opens, set the "Master RPC2 URL:" with the correct
value, if it is not set properly, already. Do not touch any other
values in this page except the description, since all the other fields
except description is populated automatically. The following figure
illustrates this:

.. image:: ../images/lava-worker-rpc2-url.png

.. index:: bundle-stream

.. _bundle_stream:

Bundle Stream Overview
======================

What is a Bundle Stream?
------------------------

LAVA runs tests which produce results with multiple tests being run for
each submitted job. The collection of results from any one submitted
job is termed a Result Bundle. Each bundle can contain multiple sets
of test results, as well as other information about the system where the
testing was performed.

Within a single result bundle are the results of each test definition
execution, termed a Test Run. Each Test Run is typically a single YAML
file and is listed in the bundle via the description of the test
definition. The individual id and result of a single test within a test
run is called the Test Case, typically a single line in the YAML file.
If the job ran across multiple devices, the bundle can include test
runs from each device from that job.

Result Bundles are uploaded to the server at the end of the test run
into a Bundle Stream which is a way of organising related results
bundles. A bundle stream could be imagined as a folder within which all
related result bundle will be stored. A bundle stream could be private
or anonymous. The name of the stream is specified in the job definition to
determine where the result bundle from the job should be submitted.

How to setup a Bundle Stream?
-----------------------------

A public/anonymous bundle stream could be setup with the help of
lava-tool as follows,

::

  $ lava-tool make-stream --dashboard-url
  http://<username>@validation.linaro.org/RPC2/ /anonymous/USERNAME/

.. note:: Replace *username* and *USERNAME* with your
          username. Alternatively an existing stream like
          anonymous/test could be used for initial testing purposes.

.. _writing_json_multinode:

Writing MultiNode JSON tests
****************************

LAVA supports running a single test across multiple devices, combining
groups of devices (of any type) within a group with the results being
aggregated into a single set. Devices within the same group can
communicate with each other using the :ref:`multinode_api`.

The YAML files used in MultiNode tests do not have to differ from
single node tests, unless the tests need to support communication
between devices in the same group.

.. note:: when viewing MultiNode log files, the original JSON submitted
          to start the job is available as the MultiNode Definition and
          it will be this which is used if you use Resubmit. The other
          definition is the parsed content which was sent to each node
          within the MultiNode job to create one log file and one test
          job for each node. It is not usually useful to submit the
          definition of one node of a MultiNode job as a separate job.

Writing a MultiNode JSON file
=============================

The JSON file needs changes to combine the devices into one group.
The :term:`device type` is replaced by a :term:`device group` which sets out
how the group will be created::

 {
    "timeout": 900,
    "job_name": "simple multinode job",
    "logging_level": "INFO",
    "device_group": [
        {
            "role": "target",
            "count": 2,
            "device_type": "panda"
        },
        {
            "role": "host",
            "count": 1,
            "device_type": "beaglexm"
        }
    ]
 }

This example creates a group of three devices, two of the ``device_type``
panda and one of the ``device_type`` beaglexm. The :term:`role` is an
arbitrary label which can be used later in the JSON to determine which
tests are run on the devices and inside the YAML to determine how the
devices communicate.

This change is enough to run a Multi-Node test in LAVA. Each device will
use the same YAML file, running the tests independently on each device.

The next stage is to allow devices to run different tests according to
the ``role`` which the device will have during the test::

 {
    "actions": [
        {
            "command": "lava_test_shell",
            "parameters": {
                "testdef_repos": [
                    {
                        "git-repo": "http://git.linaro.org/git/people/neil.williams/temp-functional-tests.git",
                        "testdef": "android/android-multinode01.yaml"
                    }
                ],
                "role": "target",
                "timeout": 900
            }
        },
        {
            "command": "lava_test_shell",
            "parameters": {
                "testdef_repos": [
                    {
                        "git-repo": "http://git.linaro.org/git/people/neil.williams/temp-functional-tests.git",
                        "testdef": "android/ubuntu-multinode01.yaml"
                    }
                ],
                "role": "host",
                "timeout": 900
            }
        }
    ]
 }

This will run the ``android/android-multinode01.yaml`` tests on every
device in the group which is assigned the role ``target``. The
``android/ubuntu-multinode01.yaml`` tests will run on every device in
the group which is assigned the role ``host``.

Using MultiNode commands to synchronise devices
===============================================

The most common requirement in a MultiNode test is that devices within
the group can be told to wait until another device in the group is
at a particular stage. This can be used to ensure that a device running
a server has had time to complete the boot and start the server before
the device running the client tries to make a connection to the server.
e.g. starting the server can involve installing the server and dependencies
and servers tend to have more dependencies than clients, so even if the
with similar devices, the only way to be sure that the server is ready
for client connections is to make every client in the group wait until
the server confirms that it is ready.

This is done using the :ref:`multinode_api` and :ref:`lava_wait`. The
YAML file specified for the role ``client`` causes the device to wait
until the YAML file specified for the role ``server`` uses
:ref:`lava_send` to signal that the server is ready.

Each message sent using the MultiNode API uses a :term:`messageID` which
is a string, unique within the group. It is recommended to make these
strings descriptive using underscores instead of spaces. The messageID
will be included in the log files of the test.

In the YAML file to be used by devices with the role ``server``::

 run:
    steps:
        - apt-get install myserver
        - lava-send server_installed

In the YAML file to be used by devices with the role ``client``::

 run:
    steps:
        - lava-wait server_installed

This means that each device using the role ``client`` will wait until
**any** one device in the group sends a signal with the messageID of
``server_installed``. The assumption here is that the group only has
one device with the label ``server``.

If devices need to wait until all devices with a specified role send a
signal, the devices which need to wait need to use :ref:`lava_wait_all`.

If the expected messageID is never sent, the job will timeout when the
default timeout expires. See :ref:`timeouts`.

Using MultiNode commands to pass data between devices
=====================================================

:ref:`lava_send` can be used to send data between devices. A device can
send data at any time, that data is then broadcast to all devices in the
same group. The data can be downloaded by any device in the group using
the messageID using :ref:`lava_wait` or :ref:`lava_wait_all`. Data is
sent as key value pairs.

.. note:: The message data is stored in a cache file which will be
   overwritten when the next synchronisation call is made. Ensure
   that your custom scripts make use of the data before the cache
   is cleared.

For example, if a device raises a network interface and wants to make
that data available to other devices in the group, the device can send
the IP address using ``lava-send``::

 run:
    steps:
       - lava-send ipv4 ip=$(./get_ip.sh)

The contents of ``get_ip.sh`` is operating system specific.

On the receiving device, the YAML includes a call to ``lava-wait``
or ``lava-wait-all`` with the same messageID::

 run:
    steps:
       - lava-wait ipv4
       - ipdata=$(cat /tmp/lava_multi_node_cache.txt | cut -d = -f 2)

.. note:: Although multiple key value pairs can be sent as a single message,
   the API is **not** intended for large amounts of data (messages larger
   than about 4Kb are considered large). Use other transfer protocols
   like ssh or wget to send large amounts of data between devices.

Helper tools in LAVA
====================

LAVA provides some helper routines for common data transfer tasks and
more can be added where appropriate. The main MultiNode API calls are
intended to support all POSIX systems but helper tools like
:ref:`lava_network` may be restricted to particular operating
systems or compatible shells due to a reliance on operating system
tools like ``ifconfig``.

Other MultiNode calls
=====================

It is also possible for devices to retrieve data about the group itself,
including the role or name of the current device as well as the names
and roles of other devices in the group. See :ref:`multinode_api` and
:ref:`multinode_use_cases` for more information.

JSON Hacking Sessions
*********************

.. seealso:: `hacking_session`

.. toctree::
   :maxdepth: 2

   hacking-session.rst

JSON Multinode
**************

.. seealso:: `writing_multinode`

.. toctree::
   :maxdepth: 2

   multinode.rst

External measurements
*********************

.. toctree::
   :maxdepth: 2

   external_measurement.rst

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
     "device_type": "panda",
     "timeout": 900
     "actions": [
         {
             "command": "deploy_linaro_android_image",
             "parameters": {
                 "images": [
                     {
                         "partition": "boot",
                         "url": "http://releases.linaro.org/12.07/android/leb-panda/boot.tar.bz2"
                     },
                     {
                         "partition": "userdata",
                         "url": "http://releases.linaro.org/12.07/android/leb-panda/userdata.tar.bz2"
                     },
                     {
                         "partition": "system",
                         "url": "http://releases.linaro.org/12.07/android/leb-panda/system.tar.bz2"
                     }
                 ]
             }
         },
         {
             "command": "boot_linaro_android_image",
             "parameters": {
                 "options": [ "boot_cmds=boot_cmds_android" ]
             }
         },
         {
             "command": "submit_results",
             "parameters": {
                 "server": "http://validation.linaro.org/RPC2/",
                 "stream": "/anonymous/lava-android-leb-panda/"
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

.. index:: json_parameters

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

.. _json_parameters:

default parameters
==================

The "params" section is optional. If your test definition file includes
shell variables in "install" and "run" sections, you can use a ``params``
section to set the default parameters for those variables.

The format should be like this::

    params:
      VARIABLE_NAME_1: value_1
      VARIABLE_NAME_2: value_2

    run:
        steps:
        - echo $VARIABLE_NAME_1


The JSON would override these defaults using the syntax::

        {
            "command": "lava_test_shell",
            "parameters": {
                "testdef_repos": [
                    {
                        "git-repo": "https://git.linaro.org/people/neil.williams/temp-functional-tests.git",
                        "testdef": "params.yaml",
                        "parameters": {"VARIABLE_NAME_1": "eth2"}
                    }
                ],
                "timeout": 900
            }
        }

Always set default values for all variables in the test definition file to
allow for missing values in the JSON file. In the example above, ``$VARIABLE_NAME_2``
is not defined in the JSON snippet, so the default would be used.

.. note:: The format of default parameters in yaml file is below, please note that
          there is **not** a hyphen at the start of the line and **not** quotes
          around either the variable name or the variable value::

            VARIABLE_NAME_1: value_1

.. note:: The code which implements this parameter function will put variable
          name and value at the head of test shell script like below::

            VARIABLE_NAME_1='value_1'

.. note:: Be mindful when using booleans as parameters. PyYAML converts such parameters
          into 'True' or 'False' regardless of the original case::

            VARIABLE_NAME_1: true
            $VARIABLE_NAME_1 == True

So please make sure you didn't put any special character(like single quote) into value or
variable name. But Spaces and double quotes can be included in value.
Because we use two single quote marks around value strings, if you put any variable into
value strings, that will **not** be expanded.


Examples:

http://git.linaro.org/people/neil.williams/temp-functional-tests.git/blob/HEAD:/kvm-parameters.json

http://git.linaro.org/people/neil.williams/temp-functional-tests.git/blob/HEAD:/params.yaml

.. _install_steps:

other parameters
================

LAVA adds other parameters which could be accessed within the
lava-test-shell test definition. Currently the following params are
available automatically::

* LAVA_SERVER_IP
* TARGET_TYPE

Example:

https://git.linaro.org/people/senthil.kumaran/test-definitions.git/blob/HEAD:/debian/other-params.yaml

Adding Meta-Data
================

Both deploy actions support an optional field, ``metadata``. The value of this
option is a set of key-value pairs like::

 {
    "command": "deploy_linaro_image",
    "parameters": {
        "image": "http://releases.linaro.org/12.09/ubuntu/leb-panda/lt-panda-x11-base-precise_ubuntu-desktop_20120924-329.img.gz"
    },
    "metadata": {
        "ubuntu.image_type": "ubuntu-desktop",
        "ubuntu.build": "61"
    }
 }

This data will be uploaded into the LAVA dashboard when the results are
submitted and can then be used as filter criteria for finding data.

Adding a highbank device
========================

sample device config file
-------------------------

*highbank01.conf*

::

  device_type = highbank
  hostname = calxeda01-01
  ecmeip = calxeda01-01-02
  test_shell_serial_delay_ms = 100

**hostname** refers to the first ethernet port that is accessible from the target OS.

**ecmeip** refers to the address of the control port used for sending ipmi commands.

**test_shell_serial_delay_ms** refers to the delay between characters
sent over the serial link. See :ref:`sol_closed_bmc`

Adding an iPXE device
=====================

sample device config file
-------------------------

*x86-01.conf*

::

  connection_command = telnet serial02 7020
  device_type = x86
  soft_boot_cmd = reboot
  hard_reset_command = /usr/local/lab-scripts/pduclient --daemon services --port 01 --hostname pdu03 --command reboot
  power_off_cmd = /usr/local/lab-scripts/pduclient --daemon services --port 01 --hostname pdu03 --command off
  lava_network_info=lava_mac=00:22:19:d6:b3:ec

**lava_network_info** can contain any extra kernel command line arguments you would like to be passed to the kernel

.. _distributed_instance:

Distributed Instance installation
=================================

A single master instance,  can also work with one :term:`Remote Worker` or more,
acting as the web frontend and database server for the remote
worker(s). Depending on load, the master can also have devices attached.

This installation type involves the use of two or more machines

* The master instance is installed and configured on one machine. Refer to
  :ref:`debian_installation` installation.
* On the other machine(s), the :term:`Remote Worker` is installed and configured.
  Refer to :ref:`distributed_deployment`

Remote workers are especially useful when the master instance is on a public server
or external virtual host, and the remote workers and the devices are
hosted in a separate location.

Distributed deployment
**********************

.. toctree::
   :maxdepth: 2

   ../distributed-deployment.rst

Migrating LAVA instances from deployment_tool
*********************************************

.. toctree::
   :maxdepth: 2

   precise.rst
