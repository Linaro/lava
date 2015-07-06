Description
###########

Summary
*******

``lava-slave`` runs the connection to the lava master over ZMQ to
manage LAVA test jobs running on the reserved device, sending log
messages back to the master. ``lava-slave`` runs as a daemon.

Usage
*****

lava-slave [--master tcp://localhost:5556]
[--socket-addr tcp://localhost:5555] [--level=DEBUG]


Systemd support
###############

The default install uses systemd translation of the sysvinit script
but a systemd service file is available, if desired::

 /usr/share/lava-dispatcher/lava-slave.service

This file can be copied to ``/lib/systemd/system/``.
