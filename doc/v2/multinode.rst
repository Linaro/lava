.. index:: MultiNode - outline

.. _multinode:

MultiNode LAVA
##############

.. seealso:: :ref:`multinode_protocol` and
  :ref:`Using the multinode protocol <writing_multinode>`

LAVA multi-node support allows users to use LAVA to schedule, synchronise and
combine the results from tests that span multiple targets. Jobs can be arranged
as groups of devices (of any type) and devices within a group can operate
independently or use the MultiNode API to communicate with other devices in the
same group during tests.

Within a MultiNode group, devices of the same device type are assigned a role and a
``count`` of devices to include into that role. Role labels must be unique across the
entire MultiNode job. Each role has a ``device_type`` and any number of roles can
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

.. index:: multinode timeouts

LAVA MultiNode timeout behaviour
********************************

The submitted YAML includes a timeout value - in single node LAVA, this is applied to each individual action
executed on the device under test (not for the entire job as a whole). i.e. the default timeout can be smaller
than any one individual timeout used in the YAML or internally within LAVA.

In MultiNode LAVA, this timeout is also applied to individual polling operations, so an individual lava-sync
or a lava-wait will fail on any node which waits longer than the default timeout. The node will receive a failure
response.

.. _multinode_timeouts:

Recommendations on timeouts for MultiNode
=========================================

.. seealso:: :ref:`timeouts`

MultiNode operations have implications for the timeout values used in YAML submissions. If one of the
synchronisation primitives times out, the sync will fail and the job itself will then time out.
One reason for a MultiNode job to timeout is if one or more boards in the group failed to boot the
test image correctly. In this situation, all the other boards will continue until the first
synchronisation call is made in the test definition for that board.

The time limit applied to a synchronisation primitive starts when the board makes the first request
to the Coordinator for that sync. Slower boards may well only get to that point in the test definition
after faster devices (especially KVM devices) have started their part of the sync and timed out
themselves.

Always review the protocol timeout and job timeouts in the YAML submission.
Excessive timeouts would prevent other jobs from using boards where the
waiting jobs have already failed due to a problem elsewhere in the group.
If timeouts are too short, jobs will fail unnecessarily.

.. comment FIXME: this needs to be updated with the Essential role
   support once that is implemented.

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
