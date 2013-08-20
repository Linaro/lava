Use Case Two - Setting up the same job on multiple devices
**********************************************************

One test definition (or one set of test definitions) to be run on
multiple devices of the same device type.

Source Code
===========

The test definition itself could be an unchanged singlenode test definition, e.g. 

 https://git.linaro.org/gitweb?p=qa/test-definitions.git;a=blob_plain;f=ubuntu/smoke-tests-basic.yaml;hb=refs/heads/master

Alternatively, it could use the MultiNode API to synchronise the devices, e.g.

  https://git.linaro.org/gitweb?p=people/neilwilliams/multinode-yaml.git;a=blob_plain;f=multinode01.yaml;hb=refs/heads/master

  https://git.linaro.org/gitweb?p=people/neilwilliams/multinode-yaml.git;a=blob_plain;f=multinode02.yaml;hb=refs/heads/master

  https://git.linaro.org/gitweb?p=people/neilwilliams/multinode-yaml.git;a=blob_plain;f=multinode03.yaml;hb=refs/heads/master

Requirements
============

 * Multiple devices running the same test definition.
 * Running multiple test definitions at the same time on all devices in the group.
 * Synchronising multiple devices during a test.
 * Filter the results by device name.

Preparing the YAML
==================

In this use case, the same YAML file is to be used to test multiple devices.
Select your YAML file and, if appropriate, edit the name in the metadata.

TBD: MultiNode API

Preparing the JSON
===================

The change from a standard single-node JSON file is to expand the device_type
or device field to a device_group.

The change for multiple devices in MultiNode is within the ```device_group```. To run the test
multiple devices of the same type, simply increase the ```count``:

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

If the rest of the JSON refers to a ```role``` other than the one specified
in the ```device_group```, those JSON sections are ignored.

If other actions in the JSON do not mention a ```role```, the action will
occur on all devices in the ```device_group```. So with a single role,
it only matters that a role exists in the ```device_group```.

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

The filter for this use case uses a ```required attribute``` 
of **target.device_type** to only show results for the specified
devices (to cover reuse of the YAML on other boards later).

It is also possible to add a second filter which matches a specific **target**
device.

Summary
=======

http://git.linaro.org/gitweb?p=people/neilwilliams/multinode-yaml.git;a=blob_plain;f=json/panda-only-group.json;hb=refs/heads/master

http://multinode.validation.linaro.org/dashboard/image-reports/panda-multinode

