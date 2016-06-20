.. index:: MultiNode

.. _multinode:

FIXME - DEAD?

Multi-Node LAVA (JSON)
######################

.. warning:: This chapter discusses a model
   which is being superceded by the :term:`pipeline` model.

.. seealso:: :ref:`Using the multinode protocol <writing_multinode>`

LAVA multi-node support allows users to use LAVA to schedule, synchronise and
combine the results from tests that span multiple targets. Jobs can be arranged
as groups of devices (of any type) and devices within a group can operate
independently or use the MultiNode API to communicate with other devices in the
same group during tests.

Within a MultiNode group, devices of the same device type are assigned a role and a
``count`` of devices to include into that role. Role labels must be unique across the
entire multinode job. Each role has a ``device_type`` and any number of roles can
have the same ``device_type``. Each role can be assigned device ``tags``.

Once roles are defined, actions (including test images and test definitions) can be marked
as applying to specific roles (if no role is specified, all roles use the action).

If insufficient boards exist to meet the combined requirements of all the roles specified
in the job, the job will be rejected.

If there are not enough idle boards of the relevant types to meet the combined requirements
of all the roles specified in the job, the job waits in the Submitted queue until all
devices can be allocated.

Once each board has booted the test image, the MultiNode API will be available for use within
the test definition in the default PATH.

.. toctree::
   :maxdepth: 3

   ../multinodeapi.rst
   ../debugging.rst

Hardware requirements and virtualisation
****************************************

Multi-Node is explicitly about synchronising test operations across multiple boards and running
Multi-Node jobs on a particular instance will have implications for the workload of that instance.
This can become a particular problem if the instance is running on virtualised hardware with
shared I/O, a limited amount of RAM or a limited number of available cores.

e.g. Downloading, preparing and deploying test images can result in a lot of synchronous I/O and
if this instance is running the server and the dispatcher, this can cause the load on that machine
to rise significantly, possibly causing the server to become unresponsive.

It is strongly recommended that Multi-Node instances use a separate dispatcher running on
non-virtualised hardware so that the (possibly virtualised) server can continue to operate.

Also, consider the number of boards connected to any one dispatcher. MultiNode jobs will commonly
compress and decompress several test image files of several hundred megabytes at precisely the same
time. Even with a powerful multi-core machine, this has been shown to cause appreciable load. It
is worth considering matching the number of boards to the number of cores for parallel decompression
and matching the amount of available RAM to the number and size of test images which are likely to
be in use.

Extending existing LAVA submissions
***********************************

To extend an existing JSON file to start a MultiNode job, some changes are required to define the
``device_group``. If all devices in the group are to use the same actions, simply create a single
role with a count for how many devices are necessary. Usually, a MultiNode job will need to assign
different test definitions to different boards and this is done by adding more roles, splitting the
number of devices between the differing roles and assigning different test definitions to each role.

If a MultiNode job includes devices of more than one ``device_type``, there needs to be a role for
each different ``device_type`` so that an appropriate image can be deployed.

Where all roles share the same action (e.g. ``submit_results_on_host``), omit the role parameter from
that action.

If more than one, but not all, roles share one particular action, that action will need to be repeated
within the JSON file, once for each role using that action.

.. _changes_to_json:

Changes to submission JSON
==========================

1. ``device`` or ``device_type`` move into a **device_group** list
2. Each device type has a ``count`` assigned

  1. If a ``device`` is specified directly, count needs to be one.
  2. If ``device_type`` is used and count is larger than one, enough
     devices will be allocated to match the count and all such devices will
     have the same role and use the same commands and the same actions.

3. Add :term:`device tag` to each role, if supported for the relevant devices.
4. If specific actions should only be used for particular roles, add a
   role field to the parameters of the action.
5. If any action has no role specified, it will be actioned for all roles.

Example JSON::

 {
    "timeout": 900,
    "job_name": "simple multinode job",
    "logging_level": "INFO",
    "device_group": [
        {
            "role": "omap4",
            "count": 2,
            "device_type": "panda",
            "tags": [
                "usb-flash"
            ]
        },
        {
            "role": "omap3",
            "count": 1,
            "device_type": "beaglexm",
            "tags": [
                "audio-loopback"
            ]
        }
    ],

.. index:: role

Using actions for particular roles
==================================

Example JSON::

    "actions": [
        {
            "command": "deploy_linaro_image",
            "parameters": {
                "image": "file:///home/instance-manager/images/panda-raring_developer_20130529-347.img.gz",
                "role": "omap4"
            }
        },
        {
            "command": "deploy_linaro_image",
            "parameters": {
                "image": "file:///home/instance-manager/images/beagle-ubuntu-desktop.img.gz",
                "role": "omap3"
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
                "timeout": 1800
            }
        }
    }

..

.. note:: Consider using http://jsonlint.com to check your JSON before submission.

.. index:: timeout

LAVA Multi-Node timeout behaviour
*********************************

The submitted JSON includes a timeout value - in single node LAVA, this is applied to each individual action
executed on the device under test (not for the entire job as a whole). i.e. the default timeout can be smaller
than any one individual timeout used in the JSON or internally within LAVA.

In Multi-Node LAVA, this timeout is also applied to individual polling operations, so an individual lava-sync
or a lava-wait will fail on any node which waits longer than the default timeout. The node will receive a failure
response.

.. _timeouts:

Recommendations on timeouts
===========================

MultiNode operations have implications for the timeout values used in JSON submissions. If one of the
synchronisation primitives times out, the sync will fail and the job itself will then time out.
One reason for a MultiNode job to timeout is if one or more boards in the group failed to boot the
test image correctly. In this situation, all the other boards will continue until the first
synchronisation call is made in the test definition for that board.

The time limit applied to a synchronisation primitive starts when the board makes the first request
to the Coordinator for that sync. Slower boards may well only get to that point in the test definition
after faster devices (especially KVM devices) have started their part of the sync and timed out
themselves.

Always review the top level timeout in the JSON submission - a value of 900 seconds (15 minutes) has
been common during testing. Excessive timeouts would prevent other jobs from using boards where the
waiting jobs have already failed due to a problem elsewhere in the group. If timeouts are too short,
jobs will fail unnecessarily.

Balancing timeouts
^^^^^^^^^^^^^^^^^^

Individual actions and commands can have differing timeouts, so avoid the temptation to change the
default timeout when a particular action times out in a Multi-Node job. If a particular ``lava-test-shell``
takes a long time, set an explicit timeout for that particular action:

::

 {
    "timeout": 900,
    "job_name": "netperf multinode tests",
    "logging_level": "DEBUG",
 }


::

        {
            "command": "lava_test_shell",
            "parameters": {
                "testdef_repos": [
                    {
                        "git-repo": "git://git.linaro.org/people/guoqing.zhu/netperf-multinode.git",
                        "testdef": "netperf-multinode-c-network.yaml"
                    }
                ],
                "timeout": 2400,
                "role": "client"
            }
        },
        {
            "command": "lava_test_shell",
            "parameters": {
                "testdef_repos": [
                    {
                        "git-repo": "git://git.linaro.org/people/guoqing.zhu/netperf-multinode.git",
                        "testdef": "netperf-multinode-s-network.yaml"
                    }
                ],
                "timeout": 1800,
                "role": "server"
            }
        },


Running a server on the device-under-test
*****************************************

If this server process runs as a daemon, the test definition will need to define something for the device
under test to actually do or it will simply get to the end of the tests and reboot. For example, if the
number of operations is known, would be to batch up commands to the daemon, each batch being a test case.
If the server program can run without being daemonised, it would need to be possible to close it down
at the end of the test (normally this is the role of the sysadmin in charge of the server box itself).

Making use of third party servers
=================================

A common part of a MultiNode setup is to download components from third party servers but once the test
starts, latency and connectivity issues could interfere with the tests.

Using wrapper scripts
=====================

Wrapper scripts make it easier to test your definitions before submitting to LAVA.
The wrapper lives in a VCS repository which is specified as one of the testdef_repos and will be
available in the same directory structure as the original repository. A wrapper script also
helps the tests to fail early instead of trying to do the rest of the tests.


Booting a slave device
**********************

If one of the device is marked as ``slave``, one device in the MultiNode group
will have to boot this device itself.
In order to synchronize the slave and the master, the MultiNode API is
used to send the following messages::

 * @slave sends "lava_ms_slave_data" with the needed boot information
 * @master sends "lava_ms_ready" when it's ready to boot the slave
 * @slave sends "lava_ms_boot" when he is ready to be booted

The master device is responsible for booting the slave device correctly. Once
booted, LAVA will take care of the slave device by running the tests on it.

This feature can be used to boot devices that requires specific pieces of
software in the boot process.
The boot process is then described in a test definition, running on the master device.

MultiNode Result Bundles
************************

Results are generated by each device in the group. At submission time, one device in the group is
selected to run the job which gets the aggregated result bundle for the entire group.

.. index:: coordinator

LAVA Coordinator setup
**********************

Multi-Node LAVA requires a LAVA Coordinator which manages the messaging within a group of nodes involved in
a Multi-Node job set according to this API. The LAVA Coordinator is a singleton to which nodes need to connect
over a TCP port (default: 3079). A single LAVA Coordinator can manage groups from multiple instances.
If the network configuration uses a firewall, ensure that this port is open for connections from Multi-Node dispatchers.

If multiple coordinators are necessary on a single machine (e.g. to test different versions of the coordinator
during development), each coordinator needs to be configured for a different port.

If the dispatcher is installed on the same machine as the coordinator, the dispatcher can use the packaged
configuration file with the default hostname of ``localhost``.

Each dispatcher then needs a copy of the LAVA Coordinator configuration file, modified to point back to the
hostname of the coordinator:

Example JSON, modified for a coordinator on a machine with a fully qualified domain name::

  {
    "port": 3079,
    "blocksize": 4096,
    "poll_delay": 3,
    "coordinator_hostname": "control.lab.org"
  }

An IP address can be specified instead, if appropriate.

Each dispatcher needs to use the same port number and blocksize as is configured for the Coordinator
on the specified machine. The poll_delay is the number of seconds each node will wait before polling
the coordinator again.
