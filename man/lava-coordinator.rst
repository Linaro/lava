Description
===========

Summary
#######

``lava-coordinator`` is a daemon to manage Multi-Node communications between
LAVA devices under test.

Options
#######

``--logfile=LOGFILE``
   Overrides the default log file location of
   /var/log/lava-coordinator.log

``--loglevel=LOGLEVEL``
   Overrides the default log level of INFO. Available options, in
   increasing order of verbosity, are: ERROR, WARNING, INFO, DEBUG.

``-h``; \ ``--help``
   Show summary of options.

FILES
#####

``/etc/lava-coordinator/lava-coordinator.conf``
   The system-wide configuration file to control the behaviour of
   DHPACKAGE. A LAVA NodeDispatcher installed on the same machine as the
   coordinator will use the same file. NodeDispatchers on remote
   machines need their own copy of this file, modified so that the
   ``coordinator_hostname`` field is the hostname or IP address of the
   machine running the coordinator.

.. _labsetup:

LAVA lab setup
##############

The LAVA Coordinator needs to be in lock-step with compatible versions
of the LAVA NodeDispatcher (part of lava-dispatcher / lava-server) but
the coordinator is a singleton and there can be multiple dispatchers,
none of which need to be on the same machine as the coordinator.

Additionally, when a dispatcher is installed on a machine other than the
machine running the coordinator, a copy of the LAVA Coordinator conffile
needs to be copied to that machine and modified to indicate the hostname
or IP address of the LAVA Coordinator for that dispatcher. Typically,
this can be done with tools like salt, puppet, chef etc.

Therefore, lava-coordinator does not depend on the rest of LAVA and the
setup of the coordinator is at the discretion of the LAVA lab
administrator. As long as there is one Coordinator and all dispatchers
have a working address for a coordinator, all should be well.

If a lab contains more than one Coordinator, it is recommended that each
coordinator uses a different port. This is mandatory if more than one
coordinator is installed on a single machine.

LAVA Coordinator is lightweight and has minimal dependencies, installing
on virtualised hardware is not expected to be a problem.
