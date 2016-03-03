.. index:: iterating using role

.. _use_case_four:

Use Case Four - Iterating through devices using roles
*****************************************************

Writing general-purpose test definitions
========================================

How to test that the test definition assumptions are valid.

Requirements
============

* Multi-Node job with at least two devices with usable network interfaces.
* Run operations on each device with a specified role.
* Scale the tests as the group size changes.

Background
==========

YAML test definition files are commonly reused between jobs and scalable
tests need to cope with changes in the size of the MultiNode job. Tests
should use iteration whenever any kind of comparative performance, saturation
or load measurements are required. This allows someone to later amend
the JSON to increase the number of clients per server with the valid
expectation that all clients will operate equally and that the test
definition will not fail when it finds six clients instead of one or
two.

It is particularly important that test writers should use iteration
whenever any kind of comparative performance, saturation testing or
load measurements are required. These are just the kind of jobs
where someone will later modify the JSON to increase the number of
clients per server, expecting all clients to operate equally and for
the YAML to not care that it suddenly has six clients rather than one
or two.

Recommendations
===============

.. _test_roles:

Test the defined roles
----------------------

Always test that any role required by the YAML **does** exist in the MultiNode job.::

  - lava-test-case check-server-role --shell lava-group server
  - lava-test-case check-slave-role --shell lava-group slave

This test will fail (:ref:`lava_group` returns non-zero) if the specified
role has not been defined for this MultiNode job.

.. _iterate_role:

Iterate over each role
----------------------

::

    #!/bin/sh
    for role in `lava-role list`; do
        echo $role
    done

.. _iterate_device:

Iterate over each device with a specified role
----------------------------------------------

Using ``set -e`` will allow the script to fail if the requested
role is not defined::

    #!/bin/sh
    set -e
    for device in `lava-group backend`; do
        echo $device
    done

.. _iterate_all_by_role:

Iterate over all devices by role
--------------------------------

::

    #!/bin/sh
    for role in `lava-role list`; do
        if [ "${role}" = "exception" ]; then
            continue
        fi
        for device in `lava-group $role`; do
            echo $device
        done
    done

.. _indicate_fixed_groups:

Clearly indicate test definitions with fixed group sizes.
---------------------------------------------------------

If the test definition assumes that the group is a particular size or
a particular group composition, make this clear to other test writers.
To make it obvious when test writers are editing JSON, rename the test
definition YAML file to include the word **static**. To make it obvious
to test writers are viewing result bundles and job lists, include the
same indication in the test definition name.

.. _role_aliases:

Creating an alias in /etc/hosts based on the role
=================================================

:ref:`lava_network` has optional support via the ``alias-hosts``
command to create an alias for each device based on the role of that
device. The device names are unique and will vary on each run but
are guaranteed to be usable as hostnames. The alias only uses the
alphanumeric characters within the role - ``[a-z0-9]`` - and appends
a two digit count suffix for each device assigned that role.

If the device fails to return a fully qualified hostname, ``lava-network``
uses the unqualified hostname (which is the same as the device name). In
this example, staging-kvm02 was the only device in the group to
return a value for ``hostname -f``::

  10.1.1.2	staging-kvm01	slave01
  10.1.1.6	staging-kvm02.localdomain	box01
  10.1.1.2	staging-kvm03	slave02
  10.1.1.3	staging-kvm04	slave03

.. caution:: **Resist the temptation to hardcode aliases into scripts**

YAML and the scripts called by the YAML should not make assumptions about
the group size or group constitution as those are defined in the JSON. The
same YAML file should be to be usable in multiple groups of varying
sizes. e.g. if the test definition relies on two roles, ``server`` and
``client``, the YAML and the scripts called from the YAML must not fail if
there is no ``server03`` or ``client7`` - equally the YAML must still test
``server08`` and ``client12`` if those exist.
