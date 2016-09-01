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

Options
*******

Options can be passed by editing /etc/lava-dispatcher/lava-slave

Encryption
**********

Some LAVA instances require the ZMQ connection to the master to be
encrypted. For more information on configuring lava-slave to use
encryption support, see the lava-server documentation on your
local instance or at:
https://validation.linaro.org/static/docs/v2/pipeline-server.html#zmq-curve

You will need to contact the admin of the instance to obtain the
certificate of the master to which this slave should connect.

Systemd support
###############

The default install uses systemd translation of the sysvinit script
but a systemd service file is available, if desired::

 /usr/share/lava-dispatcher/lava-slave.service

This file can be copied to ``/lib/systemd/system/``.
