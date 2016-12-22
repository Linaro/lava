.. index: hacking session

.. _hacking_session:

LAVA Hacking Sessions
*********************

A LAVA hacking session is a special lava-test-shell test that provides
interactive ssh access to a LAVA device inside a defined test environment. This
support differs from the normal LAVA SSH protocol support in that the job waits
for a real user to log in, instead of using an ssh connection to run a test
shell.

Assumptions
===========

* The user has TCP/IP access to the device (this may require a VPN or other
  access if firewalls exist between the user and the device).

* The test job deployment raises a usable networking interface.

.. _hacking_session_limitations:

Limitations
===========

The session connection is SSH, not serial. This can change the way that certain
operations run within the session compared to an automated test job. In
particular, the :ref:`multinode_api` does not operate either within a hacking
session or between two hacking sessions. A test definition which runs either
before or after the hacking session **will** be able to use the full MultiNode
API.

Device requirements
===================

Some devices may need parameters to configure the network correctly to allow
the user to log in to the hacking session. e.g. QEMU jobs need to setup a
``tap`` device:

.. code-block:: yaml

 context:
   arch: amd64
   netdevice: tap

Definitions
===========

There are test definitions for hacking sessions provided by the LAVA developers
at https://git.linaro.org/lava-team/hacking-session.git . Currently the
following definitions are supported:

* `hacking-session-debian.yaml`_ - Run the hacking session on a Debian or
  Ubuntu filesystem. The package **openssh-server will be installed using the
  package manager** if not already installed in the test image. The test image
  **must** raise a network interface automatically (this can be done with
  ``lava_command_run``, see `example`_).

* `hacking-session-fedora.yaml`_ - Run the hacking session on a Fedora
  filesystem. The package **openssh-server will be installed using the package
  manager** if not already installed in the test image. The test image **must**
  raise a network interface automatically (this can be done with
  ``lava_command_run``, see `example`_).

* `hacking-session-oe.yaml`_ - Run the hacking session on an Open Embedded
  filesystem. **openssh-server must be installed in the test image**, as it
  cannot easily be installed afterwards.

Parameters
==========

There are several extra parameters to set when using these test
definitions, some optional:

* ``PUB_KEY``: A plain-text string containing the ssh public key(s) you wish to
  use when connecting to the device

* ``GATEWAY``: (optional) The gateway for the network the test device is on.
  This only needs to be set if the test is unable to determine the gateway
  correctly - check with your LAVA admins

* ``IRC_USER``: (optional) IRC nick - this user will be alerted when the
  hacking session is ready for a connection with a private IRC message
  containing the details of how to connect to the session. (Debian hacking
  sessions only.)

* ``IRC_SERVER``: (optional) The IRC network to use for notifications, used if
  IRC_USER is also set. This defaults to ``irc.freenode.net``

.. _hacking-session-debian.yaml: https://git.linaro.org/lava-team/hacking-session.git/tree/hacking-session-debian.yaml
.. _hacking-session-fedora.yaml: https://git.linaro.org/lava-team/hacking-session.git/tree/hacking-session-fedora.yaml
.. _hacking-session-oe.yaml: https://git.linaro.org/lava-team/hacking-session.git/tree/hacking-session-oe.yaml
.. _example: https://staging.validation.linaro.org/scheduler/job/138105/definition

Starting a Hacking Session
==========================

* Create a test job with your desired target and image

* Add a lava-test-shell action at the point where you want hacking access:

.. code-block:: yaml

  - test:
        failure_retry: 3
        name: kvm-basic-hacking-session
        timeout:
          minutes: 5
        definitions:
         - repository: https://git.linaro.org/lava-team/hacking-session.git
           from: git
           path: hacking-session-debian.yaml
           name: hacking
           parameters:
              "IRC_USER": "TYPE YOUR IRC NICK HERE"
              "PUB_KEY": "PASTE_PUBKEY(S) HERE"

It is possible to include multiple hacking sessions in the same job, even
interleaved with other test actions.

.. seealso:: :ref:`inactivity_termination` and :ref:`timeouts` for clarification of the timeout
   support.

Connecting to a Hacking Session
===============================

The hacking session test definition will log the ssh command line needed for
connection into the LAVA log file. To access the log file, you can use a web
browser; navigate to your hacking session and scroll to the end of the job to
see this command line, For an example see:

* https://validation.linaro.org/scheduler/job/116632/log_file#L_5_7

SSH tunnels
-----------

If your test device is located on a remote network, you may need to gain access
via an ssh tunnel. If so:

#. verify your SSH key is setup and configured to connect::

    ~# ssh -T username@example.com

#. Modify your SSH config to allow agent forwarding::

    Host example.com
       ForwardAgent yes

lava-test-shell helper functions in a hack session
--------------------------------------------------

Once logged in to the hacking session, the lava-test-shell helper functions can
be found on the test device in the directory ``/lava/bin``

Record text to the LAVA log
---------------------------

During a hacking session, LAVA listens to the primary serial connection for the
duration of the hacking session. From within the test device, any text you echo
to that serial connection will therefore be recorded within LAVA. You may need
to work out the correct device name for this connection, for example by looking
at the CONSOLE setting in /proc/cmdline.

As an example, in a QEMU test, the device name will be ``/dev/ttyS0``. From
within the hacking session::

 root@kvm01:~# echo "This is a test statement" > /dev/ttyS0

will output to the LAVA log like::

 This is a test statement

There is an example of this online at
https://validation.linaro.org/scheduler/job/116632/log_file#L_5_12

.. _stop_hacking:

Stopping a Hacking Session
==========================

During a hacking session, your test device can't be used for other tasks. This
will block other users who may want to run tests using the device. For that
reason, your session is monitored for :ref:`inactivity_termination`, or you can
complete your session immediately:

* **Log out** of your session (you can avoid closing the session on logout
  using the :ref:`continue_hacking` support).

* **Cancel** the job in the LAVA using the link in the job detail or job log
  pages.

* **Stop** - Use the helper function ``stop_hacking`` from the command line
  within the hacking session

.. note:: ``Cancel`` will end the entire job immediately. Use ``stop_hacking``
   to close the session and complete normal job processing that may be defined
   after the hacking session.

.. _inactivity_termination:

Hacking Session timeouts
========================

.. note:: This behaviour changed after a session at
   `Connect HKG15 <http://www.slideshare.net/linaroorg/hkg15402-orphan-hacking-sessions>`_

All hacking sessions will **time out after 1 hour** if a login has not been
detected. If an ``IRC_USER`` is specified, another IRC private messages will be
sent to that user explaining the termination.

The timer is running for the lifetime of the hacking session, so if you use
:ref:`continue_hacking` and logout, you will still need to log back in within
one hour.

The session will timeout, regardless of activity, when the top-level timeout
specified in the job is reached.

This support is *separate* from the :ref:`timeouts` handling of the test job.

.. _continue_hacking:

Continuing a Hacking Session
============================

If you want to be able to log out of a hacking session and log back in within
the inactivity timeout, call the ``continue_hacking`` script from the command
line within the hacking session. The hacking session is still monitored for
:ref:`inactivity_termination`, so do remember to log back in.

.. _multiple_hacking_sessions:

Multiple hacking sessions
=========================

It is possible to use :ref:`secondary connections <secondary_connection>` to
allow more than one person to have a hacking session on a device. Depending on
how the test job is designed, it is possible to have two hacking sessions into
the same machine or to contain each hacking session within a separate virtual
machine. The secondary connection acts exactly as a second root login to the
device, so it is up to the test writer to handle possible collisions between
the sessions. It is possible to have multiple hacking sessions per person or
one hacking session each for multiple users. Secondary connections separate
each session as a single node in the MultiNode group.

.. note:: The :ref:`multinode_api` does **not** support the synchronisation or
   message sending primitives inside hacking sessions. Interactive users are
   required to exchange information between users in other means, either by
   using common files on a shared filesystem or other external methods like
   email or IRC.

Sharing a single device
-----------------------

The basis of a test job to share a device between multiple hacking sessions is
the same as any other secondary connection test job on that device, all that
changes is the test definition.

If using multiple users on a single device, it will be necessary to create a
:term:`role` for each user in the MultiNode group. This allows a separate test
definition for each role, including details of the public SSH key and IRC nick
of the user who will be able to use that session. Each hacking session test
definition will notify the specified user individually, when that session is
ready.

The ``count`` specified in the MultiNode group determines how many secondary
connections are made using any one ``role``. For one session per user, the
count for each role would be one with the number of roles determining the
number of users.

.. note:: Remember: this test job will result in multiple individuals all
   having a **root** user login on the device at the same time. Users must
   co-operate and consider that some tasks (like installing new packages) will
   prevent other users from doing their tasks at the same time. It is exactly
   the same as giving multiple people SSH access to a server and giving all
   those users ``sudo`` privileges - the users need to work together.

Separating users using virtual machines
---------------------------------------

If users are to be separated within virtual machines, one test definition will
be responsible for starting each of those machines and this definition will
have full control of the QEMU command line for each machine. (It is therefore
possible to launch virtual machines of different architectures or
configurations for specific purposes.)

Notifying users in this situation is more difficult but the existing support
within the standard hacking session can be re-used as it is simply a script
being called with parameters from the test job. In particular, the notification
will have to allow for declaring the IP address of the virtual machine for
each user.

.. caution:: Separating hacking sessions into virtual machines is a more
   complex task and requires a lot of setup on the device. Consider if it is
   really necessary for each user to be on this one device at the same time or
   whether the separation between users would be better done with separate
   hacking session test jobs. Remember, users may not be able to share data or
   files across different virtual machines on one device. This method is
   **not** a workaround for a lack of hardware of a particular type of device.

In particular, pay attention to:

* Identify unique MAC addresses for each virtual machine and check with the
  lab admins to ensure that these do not clash with any other device on the
  lab network.

* Setup the bridging on the device before starting any virtual machines so that
  the machine will get an IP address which is visible to the user.

Start by creating a test job which can launch multiple virtual machines and
identify the IP address of each machine. The exact mechanisms used to obtain
this information will vary by use case. The IP address is then passed back to
the dispatcher to initiate the secondary connection into the running virtual
machine. The hacking session can then start as normal inside that virtual
machine.

.. seealso:: :ref:`delayed_start_multinode` for more information on creating
   a test job which can delay starting the secondary connections until the
   first test job has successfully launched the virtual machines.
