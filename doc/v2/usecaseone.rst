.. index:: client-server test

.. _use_case_one:

Use Case One - Setting up a simple client:server test definition.
*****************************************************************

One device needs to obtain / prepare some data and then make the data
available to another device in the same group.

# FIXME: this needs the multi-test support in multinode to be working!

Source Code
===========

This example keeps all of the :ref:`multinode_api` calls to the inline
definitions. This is a recommended practice and future developments will
make it easier to match up the synchronisation calls from inline
definitions.

.. include:: examples/test-jobs/bbb-forward-receive.yaml
   :code: yaml

Requirements
============

1. A mechanism to obtain the data, presumably from some third-party source
2. A sync to ensure that the file is ready to be offered to the other device

 2.1. This ensures that the attempt to receive does not start early

3. A message to the original board that the data has been received and verified

 3.1. This ensures that any cleanup of the data does not happen before the transfer is complete.

Methods
=======

* Install a package which can obtain the data from the third party source
* Install a package which can provide the means to get the data to the other board

Control flow
============

+------------------------------+----------------------------------------+
|sender starts                 | receiver starts                        |
+------------------------------+----------------------------------------+
|sender obtains the data       | receiver waits for sender to be ready  |
+------------------------------+----------------------------------------+
|sender modifies the data      | wait                                   |
+------------------------------+----------------------------------------+
|sender notifies receiver      | wait                                   |
+------------------------------+----------------------------------------+
|sender waits for completion   | receiver initiates transfer            |
+------------------------------+----------------------------------------+
|wait                          | receiver notifies sender of completion |
+------------------------------+----------------------------------------+
|sender cleans up              | receiver processes the modified data   |
+------------------------------+----------------------------------------+

It is clear from the flow that the sender and the receiver are doing
different things at different times and may well need different packages
installed. The simplest way to manage this is to have two YAML files.

In this example, sender is going to use wget to obtain the data and
apache to offer it to the receiver. The receiver will only need wget.
The example won't actually modify the data, but for the purposes of the
example, the documentation will ignore the fact that the receiver could
just get the data directly.

Preparing the YAML
==================

The name field specified in the YAML will be used later as the basis
of the filter. To start each YAML file, ensure that the metadata contains
two metadata fields:

* format : **Lava-Test Test Definition 1.0**
* description : your own descriptive text

It is useful to also add the maintainer field with your email address
as this will be needed later if the test is to be added to one of the
formal test sets.

::

 metadata:
    format: Lava-Test Test Definition 1.0
    name: multinode-usecaseone
    description: "MultiNode network test commands"
    maintainer:
        - neil.williams@linaro.org

Installing packages for use in a test
-------------------------------------

If your test image raises a usable network interface by default on boot,
the YAML can specify a list of packages which need to be installed for
this test definition:

::

 install:
    deps:
        - wget
        - apache2

If your test needs to raise the network interface itself, the package
installation will need to be done in the run steps::

 run:
    steps:
        - lava-test-case linux-linaro-ubuntu-route-ifconfig-up --shell ifconfig eth0 up
        - lava-test-case apt-update --shell apt update
        - lava-test-case install-deps --shell apt -y install wget apache2

Preparing the test to send data
-------------------------------

A real test would, presumably, unpack the data, modify it in
some way and pack it back up again. Modification would happen before
the :ref:`lava_sync` ``download`` which tells the receiver that the
data is ready to be transferred.

The sender then waits for the receiver to acknowledge a correct download
using :ref:`lava_sync` ``received`` and cleans up.

sender.yaml
^^^^^^^^^^^

::

 install:
    deps:
        - wget
        - apache2

 run:
   steps:
        - lava-test-case multinode-network --shell lava-network broadcast eth0
        - lava-test-case wget-file --shell wget -O /var/www/testfile http://images.validation.linaro.org/production-repo/services-trace.txt
        # could modify the download here
        - lava-test-case file-sync --shell lava-sync download
        - lava-test-case done-sync --shell lava-sync received
        - lava-test-case remove-tgz --shell rm /var/www/testfile

Handling the transfer to the receiver
-------------------------------------

The receiver needs to know where to find the data. The sender can ensure that the
file is in a particular location, it is up to the YAML to get the rest of the
information of the network address of the sender.

The LAVA :ref:`multinode_api` provides ways of querying the network information of devices
within the group. In order to offer the data via apache, the sender needs to
raise a suitable network interface, so it calls ifconfig as a lava test case
first and then uses the lava-network API call to broadcast network information
about itself.

Equally, the receiver needs to raise a network interface, broadcast
it's network information and then collect the network information for
the group.

Note that collect is a blocking call - each of the devices needs to
broadcast before collect will return. (There is support for collecting
data only for specific roles but that's outside the scope of this example.)

receiver.yaml
^^^^^^^^^^^^^

::

 install:
    deps:
        - wget

 run:
   steps:
        - lava-test-case linux-linaro-ubuntu-route-ifconfig-up --shell ifconfig eth0 up
        - lava-test-case multinode-network --shell lava-network broadcast eth0
        - lava-test-case multinode-get-network --shell lava-network collect eth0
        - lava-test-case file-sync --shell lava-sync download
        - lava-test-case wget-from-group --shell ./get-data.sh
        - lava-test-case get-sync --shell lava-sync received
        - lava-test-case list-file --shell ls -l /tmp/testfile
        - lava-test-case remove-file --shell rm /tmp/testfile


The receiver then needs to obtain that network information and process
it to get the full URL of the data. To do command line processing and
pipes, a helper script is needed:

# FIXME: multiple test actions support is needed here.

get-data.sh
^^^^^^^^^^^

Always use **set -x** in any wrapper / helper scripts which you expect
to use in a test run to be able to debug test failures.

Ensure that the scripts are marked as executable in your VCS and
that the appropriate interpreter is installed in your test image.

::

 #!/bin/sh
 set -e
 set -x
 DEVICE=`lava-group | grep -m1 receiver|cut -f2`
 SOURCE=`lava-network query $DEVICE ipv4|grep -v LAVA|cut -d: -f2`
 wget -O /tmp/testfile http://${SOURCE}/testfile


The ``$DEVICE`` simply matches the first device name in this group
which contains the string 'receiver' (which comes from the ``role``
specified in the JSON) and returns the full name of that device,
e.g. multinode-kvm02 or staging-beagleblack03

This device name is then passed to lava-network query to get the ipv4
details of that device within this group. The value of ``$SOURCE``
is an IPv4 address of the sender (assuming that your JSON has defined a
role for the sender which would contain the 'receiver' string in the name.)

Finally, ``get-data.sh`` does the work of receiving the data from
the sender. The verification of the data is left as an exercise for
the reader - one simple method would be for the sender to checksum the
(modified) data and use ``lava-send`` to make that checksum available
to devices within the group. The receiver can then use ``lava-wait``
to get that checksum.

Once ``get-data.sh`` returns, the receiver notifies the sender that
the transfer is complete, processes the data as it sees fit and cleans up.

Preparing the JSON
===================

The JSON ties the YAML test definition with the hardware and software to
run the test definition. The JSON is also where multiple test
definitions are combined into a single MultiNode test.

device_group
------------

The device_group collates the device-types and the role of each device
type in the group along with the number of boards to allocate to each
role.

If count is larger than one, enough devices will be allocated to match
the count and all such devices will have the same role and use the same
commands and the same actions. (The job will be rejected if there are
not enough devices available to satisfy the count.)

.. code-block:: yaml

  protocols:
    lava-multinode:
      roles:
        client:
          device_type: beaglebone-black
          count: 1
        server:
          device_type: beaglebone-black
          count: 1
      timeout:
        minutes: 6

actions
-------

When mixing different device_types in one group, the images to deploy
will probably vary, so use the role parameter to determine which image
gets used on which board(s).

deploy
^^^^^^

.. code-block:: yaml

  actions:
  - deploy:
      role:
      - client
      - server
      timeout:
        minutes: 10
      to: tftp
      kernel:
        url: http://people.linaro.org/~neil.williams/opentac/zImage
      ramdisk:
        url: http://images.validation.linaro.org/functional-test-images/common/linaro-image-minimal-initramfs-genericarmv7a.cpio.gz.u-boot
        compression: gz
        header: u-boot
        add-header: u-boot
      os: oe
      dtb:
        url: http://people.linaro.org/~neil.williams/opentac/am335x-boneblack.dtb

boot
^^^^

.. code-block:: yaml

    - boot:
        role:
        - server
        - client
        timeout:
          seconds: 60
        method: u-boot
        commands: ramdisk
        type: bootz
        prompts:
        - 'linaro-test'


lava_test_shell
^^^^^^^^^^^^^^^

If specific actions should only be used for particular roles, add a role
field to the parameters of the action.

If any action has no role specified, it will be actioned for all roles.

.. code-block:: yaml

    - test:
        role:
        - client
        timeout:
          minutes: 5
        definitions:
        - from: inline
          repository:
            metadata:
              format: Lava-Test Test Definition 1.0
              name: forwarder
              description: "MultiNode network test commands"
            install:
              deps:
              - curl
              - realpath
              - lsb-release
              - usbutils
              - wget
              - ntpdate
              - apache2
            run:
              steps:
              - lava-test-case multinode-role-output --shell lava-role
              - lava-test-case multinode-sync --shell lava-sync running
              - lava-test-case multinode-send-message --shell lava-send sending source=$(lava-self) role=$(lava-role) hostname=$(hostname -f) kernver=$(uname -r) kernhost=$(uname -n)
              - lava-test-case multinode-group --shell lava-group
              - lava-group

Prepare a Query for the results
===============================

Now decide how you are going to analyse the results of tests using
this definition, using the name of the test definition specified in
the YAML metadata.

Unique names versus shared names
--------------------------------

Each YAML file can have a different name or the name can be shared amongst
many YAML files at which point those files form one test definition, irrespective
of what each YAML file actually does. Sharing the name means that the results
of the test definition always show up under the same test name. While this
can be useful, be aware that if you subsequently re-use one of the YAML files
sharing a name in a test which does not use the other YAML files sharing
the same name, there will be gaps in your data. When the filter is later
used to prepare a graph, these gaps can make it look as if the test
failed for a period of time when it was simply that the not all of the
tests in the shared test definition were run.

A single filter can combine the results of multiple tests, so it is
generally more flexible to have a unique name in each YAML file and
combine the tests in the filters.

If you use a unique test definition name for every YAML file, ensure that
each name is descriptive and relevant so that you can pick the right test
definition from the list of all tests when preparing the filter. If you
share test definition names, you will have a shorter list to search.

Filters also allow results to be split by the device type and, in
Multi-Node, by the role. Each of these parameters is defined by the JSON,
not the YAML, so care is required when designing your filters to cover
all uses of the test definition without hiding the data in a set of
unrelated results.

Create a filter
---------------

To create or modify filters (and the graphs which can be based on them)
you will need appropriate permissions on the LAVA instance to which are
you submitting your JSON.

On the website for the instance running the tests, click on Dashboard
and Filters. If you have permissions, there will be a link entitled
*Add new filter...*.

The filter name should include most of the data about what this filter
is intended to do, without whitespace. This name will be preserved through
to the name of the graph based on this filter and can be changed later if
necessary. Choose whether to make the filter public and select the bundle
stream(s) to add into the filter.

If the filter is to aggregate all results for a test across all
devices and all roles, simply leave the *Attributes* empty. Otherwise,
*Add a required attribute* and start typing to see the available fields.

To filter by a particular device_type, choose **target.device_type**.

To filter by a particular role (Multi-Node only), choose **role**.

Click *Add a test* to get the list of test definition names for which
results are available.

Within a test definition, a filter can also select only particular test
cases. In this Use Case, for example, the filter could choose only the
``multinode-network``, ``multinode-get-network`` or ``file-sync``
test cases. Continue to add tests and/or test cases - the more tests
and/or test cases are added to the filter, the fewer results will
match.

Click the *Preview* button to apply the filter to the current set of
results **without saving the filter**.

In the preview, if there are columns with no data or rows with no data
for specific columns, these will show up as missing data in the filter
and in graphs based on this filter. This is an indication that you need
to refine either the filter or the test definitions to get a cohesive
set of results.

If you are happy with the filter, click on save.

The suggested filter for this use case would simply have a suitable name,
no required attributes and a single test defined - using a shared name
specified in each of the YAML files.

::

 Bundle streams     /anonymous/instance-manager/
 Test cases         multinode-network 	any

Prepare a graph based on the filter
===================================

A graph needs an image and the image needs to be part of an image set to
be visible in the dashboard image reports. Currently, these steps need
to be done by an admin for the instance concerned.

Once the image exists and it has been added to an image set, changes in
the filter will be reflected in the graph without the need for
administrator changes.

Each graph is the result of a single image which itself is basde on a
single filter. Multiple images are collated into image sets.

Summary
=======

The full version of this use case are available:

https://git.linaro.org/people/neil.williams/multinode-yaml.git/blob_plain/HEAD:/json/kvm-beagleblack-group.json

Example test results are visible here:

http://multinode.validation.linaro.org/dashboard/image-reports/kvm-multinode

http://multinode.validation.linaro.org/dashboard/streams/anonymous/instance-manager/bundles/da117e83d7b137930f98d44b8989dbe0f0c827a4/

This example uses a kvm device as the receiver only because the test environment
did not have a bridged configuration, so the internal networking of the kvm meant
that although the KVM could connect to the beaglebone-black, the beaglebone-black
could not connect to the kvm.

https://git.linaro.org/people/neil.williams/multinode-yaml.git/blob_plain/HEAD:/json/beagleblack-use-case.json

https://staging.validation.linaro.org/dashboard/image-reports/beagleblack-usecase

https://staging.validation.linaro.org/dashboard/streams/anonymous/codehelp/bundles/cf4eb9e0022232e97aaec2737b3cd436cd37ab14/

This example uses two beaglebone-black devices.
