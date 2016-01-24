.. index: hacking session

.. _hacking_session:

LAVA Hacking Sessions
*********************

A LAVA hacking session is a lava-test-shell test that provides interactive
ssh access to a LAVA device inside a defined test environment. This support
differs from the SSH protocol support in that the job waits for a real
user to login instead of expecting a dynamic connection to run a test shell.

Assumptions
===========

 * The user has TCP/IP access to the device (this may require a VPN or
   other access if firewalls exist between the user and the device).
 * The test job deployment raises a usable networking interface.

Parameters
==========
 * ``PUB_KEY`` - A plain-text string containing the ssh public key(s) you
   wish to use to connect to the device over ssh
 * ``IRC_USER`` - your IRC nick - the user will be alerted when the hacking
   session is ready for a connection with a private IRC message containing
   the details of how to connect to the session. (Debian hacking sessions
   only.)
 * testdef - The test definition (distrbution specific)

  * `hacking-session-debian.yaml`_ - run the hacking session on a
    Debian or Ubuntu filesystem, **openssh-server will be installed
    using the package manager** if not already installed. The test
    image **must** raise a network interface automatically (this can be
    done with ``lava_command_run``, see `example`_).
  * `hacking-session-oe.yaml`_ - run the hacking session on an Open
    Embedded filesystem. **openssh-server must be installed in
    the test image**
  * **hacking-session-android.yaml** - run the hacking session on an
    Android filesystem **openssh-server must be installed in the
    test image**. (The YAML for this session is still in review).

Options
=======
 * ``GATEWAY`` - The gateway for the network the target device is on -
   only needs to be set if the test is unable to determine the gateway
   correctly. (check with your LAVA admins)
 * ``IRC_SERVER`` - defaults to ``irc.freenode.net``

.. _hacking-session-debian.yaml: https://git.linaro.org/lava-team/hacking-session.git/blob_plain/HEAD:/hacking-session-debian.yaml

.. _hacking-session-oe.yaml: https://git.linaro.org/lava-team/hacking-session.git/blob_plain/HEAD:/hacking-session-oe.yaml

.. _example: https://staging.validation.linaro.org/scheduler/job/138105/definition

Starting a Hacking Session
==========================

* Create a LAVA job file with your desired target and image
* Add a lava-test-shell action to your LAVA json job file where you want hacking access

.. code-block:: yaml

  - test:
        failure_retry: 3
        name: kvm-basic-hacking-session
        timeout:
          minutes: 5
        definitions:
         - repository: http://git.linaro.org/lava-team/hacking-session.git
           from: git
           path: hacking-session-debian.yaml
           name: hacking
           parameters:
              "IRC_USER": "TYPE YOUR IRC NICK HERE",
              "PUB_KEY": "PASTE_PUBKEY(S) HERE"

See :ref:`inactivity_termination` for clarification of the timeout
support.

Connecting to a Hacking Session
===============================

The hacking session test definition will report the commands to ssh within the
LAVA log file.  To access the log file, you can use a web browser; navigate to
your hacking session and scroll to the end of the job to see instructions

 * This hack session was executed on Linaro's LAVA system, job ID: 116632

  * https://validation.linaro.org/scheduler/job/116632/log_file#L_5_7

SSH tunneling
-------------

If your target device is located on a remote server, as is the case when
accessing the Linaro LAVA lab, you'll want to tunnel onto the Linaro network
to the device under test

#. verify your SSH key is setup and configured to connect::

    ~# ssh -T username@example.com

#. Modify your SSH config to allow agent forwarding::

    Host example.com
       ForwardAgent yes

lava-test-shell helper functions in a hack session
--------------------------------------------------

lava-test-shell helper functions can be found within target in the
directory ``/lava/bin``

Record text to the LAVA log
---------------------------

During a hacking session, LAVA is listening to ``/dev/ttyS0`` for the
duration of the hacking session.  From within the target any text you
echo to ``/dev/ttyS0`` will be recorded within LAVA.

 * From within the Test session::

    root@kvm01:~# echo "This is a test statement" > /dev/ttyS0

 * Viewing the output in the LAVA log

   https://validation.linaro.org/scheduler/job/116632/log_file#L_5_12

.. _stop_hacking:

Stopping a Hacking Session
==========================

During a hacking session, the target your are connected to can't be used for
other tasks, so this holds up other users who may want to run tests using
the device. Your session is monitored for :ref:`inactivity_termination`,
or you can complete your session immediately:

 * **logout** of your session (you can avoid closing the session on logout
   using the :ref:`continue_hacking` support).
 * **Cancel** the job in the LAVA using the link in the job detail or
   job log pages.
 * **Stop** - Use the helper function ``stop_hacking`` from the command-line
   within the hacking session

.. note:: Cancel will end the job immediately, there will not be any time
   to process the :term:`result bundle`. Use ``stop_hacking`` to close the
   session and complete normal job processing.

.. _inactivity_termination:

Hacking Session timeouts
========================

.. note:: This behaviour changed after a session at
   `Connect HKG15 <http://www.slideshare.net/linaroorg/hkg15402-orphan-hacking-sessions>`_

All hacking sessions will **timeout after 1 hour** if a login has not
been detected. If an ``IRC_USER`` is specified with a Debian hacking
session, that user will get another IRC private message explaining
the termination.

The timer is running for the lifetime of the hacking session, so if you
use :ref:`continue_hacking` and logout, you will still need to log back
in within one hour.

The session will timeout, regardless of activity, when the timeout
specified in the job is reached.

.. _continue_hacking:

Continuing a Hacking Session
============================

If you want to be able to logout of a hacking session and log back in
within the inactivity timeout, call the ``continue_hacking`` script from
the command line within the hacking session. The hacking session is still
monitored for :ref:`inactivity_termination`, so do remember to log back
in.
