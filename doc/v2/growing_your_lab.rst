.. _growing_your_lab:

Growing your lab
****************

Now expected to have a simple lab setup with some virtual devices and
some simple test boards. Next things to consider:

* how to lay things out
  * physically and logically
* making things multi-user
* health checks


Remote workers can be added to any V2 master. To do so, use the
:ref:`django_admin_interface` to add new devices and device types, allocate
devices to the newly created remote worker and optionally configure
:ref:`encrpytion on the master <zmq_master_encryption>` and :ref:`on the worker
<zmq_slave_encryption>`.
