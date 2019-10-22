.. index:: MultiNode - outline

.. _multinode:

MultiNode LAVA
##############

.. seealso:: :ref:`multinode_protocol` and
  :ref:`Using the multinode protocol <writing_multinode>`

LAVA multi-node support allows users to use LAVA to schedule, synchronize and
combine the results from tests that span multiple targets. Jobs can be arranged
as groups of devices (of any type) and devices within a group can operate
independently or use the MultiNode API to communicate with other devices in the
same group during tests.

Within a MultiNode group, devices of the same device type are assigned a role
and a ``count`` of devices to include into that role. Role labels must be
unique across the entire MultiNode job. Each role has a ``device_type`` and any
number of roles can have the same ``device_type``. Each role can be assigned
device ``tags``.

Once roles are defined, actions (including test images and test definitions)
can be marked as applying to specific roles (if no role is specified, all roles
use the action).

If insufficient boards exist to meet the combined requirements of all the roles
specified in the job, the job will be rejected.

If there are not enough idle boards of the relevant types to meet the combined
requirements of all the roles specified in the job, the job waits in the
Submitted queue until all devices can be allocated.

Each test job is put into a :term:`MultiNode group <target_group>` and basic
information about other jobs in that group will be available in each test shell
using the MultiNode API.

.. index:: MultiNode - synchronization

.. _multinode_synchronization:

Using LAVA MultiNode synchronization
************************************

MultiNode is implemented using a :term:`protocol` which allows test writers to
access synchronization calls in any part of a test job by sending a request to
the :ref:`multinode_protocol`.

.. seealso:: :ref:`delayed_start_multinode` which is used when
   :ref:`writing_secondary_connection_jobs`

Once each board has booted the test image, the :ref:`MultiNode API
<multinode_api>` will also be available for use within each test definition
using scripts placed into the default PATH by the LAVA overlay.

Unless two or more roles use the MultiNode API to synchronize operations at
some point within the test job submission, the test jobs will start at the same
time but run independently. Even if the test jobs in a MultiNode group are
identical, the time taken to download, deploy and boot into the test shell will
vary. There is no guarantee that a service will be available for another role
in the MultiNode group unless the test writer uses the synchronization
primitives in the MultiNode API. This also applies to tests where one role
needs to send data (like an IP address) to another role. One of the first tasks
for many MultiNode test jobs is to synchronize specific roles.

To synchronize all roles within the :term:`MultiNode group <target_group>`, use
:ref:`lava_sync`. If any role fails to execute this call, the entire group will
fail the synchronization.

In **all** roles in this MultiNode group:

.. code-block:: yaml

   - lava-sync server

To synchronize only specific roles, send a specific string using
:ref:`lava_send` and make the other role use :ref:`lava_wait` with that same
string. Then send another message from the waiting role and make the first role
wait for the second message.

In the role acting as a server:

.. code-block:: yaml

   - lava-send server
   - lava-wait client

In the role acting as a client:

.. code-block:: yaml

   - lava-wait server
   - lava-send client

If one role is **essential** to all other roles in the test job, for example if
a role has to install and configure a server which is to be contacted by other
roles within the group, :ref:`mark that role as essential
<multinode_essential_roles>`. When the job(s) marked with the essential role
fail, all test jobs in the MultiNode group will terminate.

To make your test job submissions more portable, it is recommended to use
:ref:`inline test definitions <inline_test_definitions>` when calling the
MultiNode API from the test shell. All MultiNode API calls can also be executed
from :ref:`custom scripts <custom_scripts>` although this can make things
harder to debug.

MultiNode synchronization calls will exit non-zero if the attempt times out or
fails in some other way. The test shell definition will then exit at this
point.

It is **not** recommended to wrap MultiNode synchronization calls in calls to
``lava-test-case`` because if the API call fails, ``lava-test-case`` will
report a fail result but the test definition itself will continue as if the
synchronization succeeded. The synchronization calls themselves will create
results based on the operation requested.

.. index:: MultiNode - results

.. _multinode_results:

MultiNode Results
=================

Each call to :ref:`lava_send`, :ref:`lava_sync`, :ref:`lava_wait` or
:ref:`lava_wait_all` will generate a :term:`test case` with a ``multinode-``
prefix in the current :term:`test suite` of the results for this test job. If
the synchronization completes within the timeout, the result will be a
``pass``. If the attempt to synchronize times out, the result will be a
``fail``.

For example:

.. code-block:: yaml

   - lava-wait server
   - lava-send client

Would generate test case results like ``multinode-wait-server`` and
``multinode-send-client``.

.. seealso:: :ref:`test_definition_portability`

.. index:: MultiNode - timeouts

LAVA MultiNode timeout behavior
********************************

The submitted YAML includes a timeout value - in single node LAVA, this is
applied to each individual action executed on the device under test (not for
the entire job as a whole). i.e. the default timeout can be smaller than any
one individual timeout used in the YAML or internally within LAVA.

In MultiNode LAVA, this timeout is also applied to individual polling
operations, so an individual lava-sync or a lava-wait will fail on any node
which waits longer than the default timeout. The node will receive a failure
response.

.. seealso:: :ref:`multinode_essential_roles` - if your test job involves a
   long running server and clients, marking the server as essential allows the
   client test jobs to fail early instead of waiting for a long timeout.

.. _multinode_timeouts:

Recommendations on timeouts for MultiNode
=========================================

.. seealso:: :ref:`timeouts`

MultiNode operations have implications for the timeout values used in YAML
submissions. If one of the synchronization primitives times out, the sync will
fail and the job itself will then time out. One reason for a MultiNode job to
timeout is if one or more boards in the group failed to boot the test image
correctly. In this situation, all the other boards will continue until the
first synchronization call is made in the test definition for that board.

The time limit applied to a synchronization primitive starts when the board
makes the first request to the Coordinator for that sync. Slower boards may
well only get to that point in the test definition after faster devices
(especially KVM devices) have started their part of the sync and timed out
themselves.

Always review the protocol timeout and job timeouts in the YAML submission.
Excessive timeouts would prevent other jobs from using boards where the waiting
jobs have already failed due to a problem elsewhere in the group. If timeouts
are too short, jobs will fail unnecessarily.

.. comment FIXME: this needs to be updated with the Essential role
   support once that is implemented.

Running a server on the device-under-test
*****************************************

If this server process runs as a daemon, the test definition will need to
define something for the device under test to actually do or it will simply get
to the end of the tests and reboot. For example, if the number of operations is
known, would be to batch up commands to the daemon, each batch being a test
case. If the server program can run without being daemonised, it would need to
be possible to close it down at the end of the test (normally this is the role
of the sysadmin in charge of the server box itself).

Making use of third party servers
=================================

A common part of a MultiNode setup is to download components from third party
servers but once the test starts, latency and connectivity issues could
interfere with the tests.

Using wrapper scripts
=====================

Wrapper scripts make it easier to test your definitions before submitting to
LAVA. The wrapper lives in a VCS repository which is specified as one of the
testdef_repos and will be available in the same directory structure as the
original repository. A wrapper script also helps the tests to fail early
instead of trying to do the rest of the tests.
