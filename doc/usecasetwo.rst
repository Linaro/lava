.. index:: multiple devices

.. _use_case_two:

Use Case Two - Setting up the same job on multiple devices
**********************************************************

One test definition (or one set of test definitions) to be run on
multiple devices of the same device type.

Source Code
===========

The test definition itself could be an unchanged singlenode test definition, e.g.

 https://git.linaro.org/qa/test-definitions.git/blob/HEAD:/ubuntu/smoke-tests-basic.yaml

Alternatively, it could use the MultiNode API to synchronise the devices, e.g.

  https://git.linaro.org/people/neil.williams/multinode-yaml.git/blob_plain/HEAD:/multinode01.yaml

  https://git.linaro.org/people/neil.williams/multinode-yaml.git/blob_plain/HEAD:/multinode02.yaml

  https://git.linaro.org/people/neil.williams/multinode-yaml.git/blob_plain/HEAD:/multinode03.yaml

Requirements
============

 * Multiple devices running the same test definition.
 * Running multiple test definitions at the same time on all devices in the group.
 * Synchronising multiple devices during a test.
 * Filter the results by device name.

Preparing the YAML
==================

In the first part of this use case, the same YAML file is to be used to
test multiple devices. Select your YAML file and, if appropriate, edit
the name in the metadata.

Preparing the JSON
===================

The change from a standard single-node JSON file is to expand the device_type
or device field to a device_group.

The change for multiple devices in MultiNode is within the ``device_group``. To run the test
multiple devices of the same type, simply increase the ``count``:

::

 {
    "device_group": [
        {
            "role": "bear",
            "count": 2,
            "device_type": "panda",
            "tags": [
                "use-case-two"
            ]
        }
 }

If the rest of the JSON refers to a ``role`` other than the one specified
in the ``device_group``, those JSON sections are ignored.

If other actions in the JSON do not mention a ``role``, the action will
occur on all devices in the ``device_group``. So with a single role,
it only matters that a role exists in the ``device_group``.

actions
-------

::

 {
        {
            "command": "deploy_linaro_image",
            "parameters": {
                "image": "https://releases.linaro.org/13.03/ubuntu/panda/panda-quantal_developer_20130328-278.img.gz"
            }
           "role": "bear"
        }
 }

lava_test_shell
^^^^^^^^^^^^^^^

To run multiple test definitions from one or multiple testdef repositories,
expand the testdef_repos array:

.. tip:: Remember the JSON syntax.

 - continuations need commas, completions do not.

::

 {
        {
            "command": "lava_test_shell",
            "parameters": {
                "testdef_repos": [
                    {
                        "git-repo": "git://git.linaro.org/people/neilwilliams/multinode-yaml.git",
                        "testdef": "multinode01.yaml"
                    },
                    {
                        "git-repo": "git://git.linaro.org/people/neilwilliams/multinode-yaml.git",
                        "testdef": "multinode02.yaml"
                    },
                    {
                        "git-repo": "git://git.linaro.org/people/neilwilliams/multinode-yaml.git",
                        "testdef": "multinode03.yaml"
                    }
                ],
                "role": "sender"
            }
        },
 }

submit_results
^^^^^^^^^^^^^^

The results for the entire group get aggregated into a single result
bundle.

::

 {
        {
            "command": "submit_results_on_host",
            "parameters": {
                "stream": "/anonymous/instance-manager/",
                "server": "http://validation.linaro.org/RPC2/"
            }
        }
 }

Prepare a filter for the results
================================

The filter for this use case uses a ``required attribute``
of **target.device_type** to only show results for the specified
devices (to cover reuse of the YAML on other boards later).

It is also possible to add a second filter which matches a specific **target**
device.

Adding synchronisation
======================

So far, the multiple devices have been started together but then had no
further interaction.

The :ref:`multinode_api` supports communication between devices within
a group and provides synchronisation primitives. The simplest of these
primitives, :ref:`lava_sync` was used in :ref:`use_case_one` but there are more
possibilities available.

:ref:`lava_sync` is a special case of a :ref:`lava_send` followed by a
:ref:`lava_wait_all`.

Sending messages
----------------

Messages can be sent using :ref:`lava_send` which is a non-blocking call.
At a later point, another device in the group can collect the message
using ``lava-wait`` or ``lava-wait-all`` which will block until
the message is available.

The message can be a simple identifier (e.g. 'download' or 'ready') and
is visible to all devices in the group.

Key value pairs can also be sent using the API to broadcast particular
information.

If multiple devices send the same message ID, the data is collated by
the LAVA Coordinator. Key value pairs sent with any message ID are
tagged with the device name which sent the key value pairs.

Receiving messages
------------------

Message reception will block until the message is available.

For :ref:`lava_wait`, the message is deemed available as soon as any device
in the group has sent a message with the matching ID. If no devices have
sent such a message, any device asking for ``lava-wait`` on that ID
will block until a different board uses ``lava-send`` with the expected
message ID.

For :ref:`lava_wait_all`, the message is only deemed available if **all
devices in the group** have already sent a message with the expected message
ID. Therefore, using ``lava-wait-all`` requires a preceding
``lava-send``.

When using ``lava-wait-all MESSAGEID ROLE``, the message is only deemed
available if **all devices with the matching role in the group** have
sent a message with the expected message ID. If the receiving device has
the specified role, that device must use a ``lava-send`` for the same
message ID before using ``lava-wait-all MESSAGEID ROLE``.

::

        - lava-test-case multinode-send-network --shell lava-send ready
        - lava-test-case multinode-get-network --shell lava-wait ready

It is up to the test writer to ensure that when :ref:`lava_wait` is used,
that the message ID is sufficiently unique that the first use of that
message ID denotes the correct point in the YAML.

::

        - lava-test-case multinode-send-message --shell lava-send sending source=$(lava-self) role=$(lava-role) hostname=$(hostname -f) kernver=$(uname -r) kernhost=$(uname -n)
        - lava-test-case multinode-wait-message --shell lava-wait-all sending

This example will wait until all devices in the group have sent the
message ID ''sending'' (with or without the associated key value pairs).

Summary
=======

http://git.linaro.org/people/neil.williams/multinode-yaml.git/blob_plain/HEAD:/json/panda-only-group.json

http://multinode.validation.linaro.org/dashboard/image-reports/panda-multinode

