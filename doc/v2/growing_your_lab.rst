.. index:: growing your lab, micro-instance

.. _growing_your_lab:

Growing your lab
################

Assumptions
***********

At this point, it is expected that you will have a simple lab setup with some
virtual devices and some simple test boards, each regularly passing
:ref:`health checks <health_checks>`. It is generally a good idea to allow time
for your lab to settle. Run a number of test jobs and understand the
administrative burden before trying to expand your setup.

Once you are happy that things are working and you know how to run that simple
lab, here are suggested steps to follow to grow it.

Requirements
************

When planning your lab, keep in mind the basic requirements of automation and
LAVA:

* Instances need high reliability.

* Devices under test may often be prototypes or developer editions of hardware.
  This can lead to reliability and stability issues.

* Extra hardware may be needed for automation which is not commonly found in
  generic hosting locations like data centres.

* Depending on the type of hardware in use, it may have significant problems
  with automation. Some devices may need security measures disabling, for
  example.

* Test jobs need to run quickly to provide useful results to developers.

* Lab infrastructure needs to remain secure (some resources may not be open to
  the public).

.. contents::
   :backlinks: top

Logical layouts
***************

The simplest LAVA instance is a single master with a single worker on the same
machine. Adding more devices to such an instance may quickly cause problems
with load. Test jobs may time out on downloads or decompression and devices
will go offline.

The first step in growing a LAVA lab is to add a remote worker. Remote workers
can be added to any V2 master. To do so, use the :ref:`django_admin_interface`
to add new devices and device types, allocate some or all devices to the newly
created remote worker and optionally configure :ref:`encrpytion on the master
<zmq_master_encryption>` and :ref:`on the worker <zmq_slave_encryption>` for
secure communication between them.

As load increases, the master will typically benefit from having fewer and
fewer devices directly attached to the worker running on the master machine.
Complex labs will typically only have devices attached to remote workers.

Depending on the workload and admin preferences, there are several lab layouts
that can make sense:

.. _single_master_single_worker:

Single master, single worker
============================

.. figure:: images/simple-lab.svg
   :width: 60%
   :align: center
   :alt: single master, single worker

This is the starting layout for a fresh installation. Depending on the
capability of the master, this layout can support a small variety of devices
and a small number of users. This layout does not scale well. Adding too many
devices or users to this setup can lead to the highest overall maintenance
burden, per test job, of all the layouts here.

.. seealso:: :ref:`lab_scaling`

In all of these example diagrams, **Infrastructure** represents the extra
equipment that might be used alongside the LAVA master and workers, such as
mirrors, caching proxies etc.

.. _single_master_multiple_workers:

Single master, multiple workers
===============================

.. figure:: images/worker-lab.svg
   :width: 60%
   :align: center
   :alt: single master, multiple workers

A medium to large lab can operate well with a single master controlling
multiple workers, especially if the master is a dedicated server running only
``lava-server``.

.. _multiple_masters_multiple_workers:

Multiple masters, multiple workers
==================================

.. figure:: images/frontend-lab.svg
   :width: 60%
   :align: center
   :alt: multiple masters, multiple workers

A custom :term:`frontend` can use :ref:`custom result handling
<custom_result_handling>` to aggregate data from multiple separate masters into
a single data set. The different masters can be geographically separated and
run by different admins. This is the system used to great effect by
:ref:`kernelci_org`.

.. _micro_instances:

Micro-instances
===============

.. figure:: images/micro-instance-lab.svg
   :width: 60%
   :align: center
   :alt: micro-instance layout

When different teams need different sets of device types and
configurations and where there is little overlap between the result sets for
each team, a micro-instance layout may make sense.

The original single lab is split into separate networks, each with a separate
complete instance of a LAVA master and one or more workers. This will give each
team their own dedicated micro-instance, but the administrators of the lab can
use common infrastructure just like a single lab in a single location. Each
micro-instance can be grown in a similar way to any other instance, by adding
more devices and more workers.

Which layout is best?
=====================

The optimum configuration will depend massively on the devices and test jobs
that you expect to run. Use the :ref:`multiple masters, multiple
workers<multiple_masters_multiple_workers>` option where all test jobs feed
into a single data set. Use micro-instances where teams have discrete sets of
results. Any combination of micro-instances can still be aggregated behind one
or more custom frontends to get different overviews of the results.

As an example, the Linaro LAVA lab in Cambridge is a hybrid setup. It operates
using a set of micro-instances, some of which provide results to frontends like
:ref:`kernelci_org`.

Recommendations
***************

* Some labs have found it beneficial to have identical machines serving as the
  workers, in identical racks. This makes administration of a large lab much
  easier. It can also be beneficial to take this one stage further and have a
  similar, if not identical, set of devices on each worker. If your lab has a
  wide range of test job submissions which cover most device types, you may
  find that a similar layout helps balance the load.

* Consider local mirroring or caching of resources such as NFS rootfs tarballs,
  kernel images, compressed images and git repositories. It is valuable to make
  downloads to the worker as quick as possible - slow downloads will inflate
  the run time of every test.

  * One of the administrative problems of :abbr:`CI (continuous
    integration)` is that these images change frequently, so a caching proxy
    may be more effective than a direct mirror of the build system storage.

  * Conversely, the use of ``https://`` URLs inside test jobs typically will
    make caches and proxies much less effective. Not supporting ``https://``
    access to git repositories or build system storage can have implications
    for the physical layout of the lab, depending on local policy.

  * Depending on the lab, local mirroring of one or more distribution package
    archives can also be useful.

    .. note:: This may rely on the build system for NFS rootfs and other
       deployments being configured to always use the local mirror in those
       images. This can then have implications for test writers trying to debug
       failed test jobs without access to the mirror.

* Consider the implications of persistence. LAVA does not (currently) archive
  old test jobs, log files or results. The longer a single master is collating
  the results from multiple workers, the larger the dataset on that master
  becomes. This can have implications for the time required to perform backups,
  extract results or run database migrations during upgrades.

* Consider reliability concerns - each site should have :abbr:`UPS
  (Uninterruptible Power Supply)` support. Some sites may need generators as
  well. This is not just needed for the master and workers: it will also be
  required for all the devices, the network switches and and all your other lab
  infrastructure.

* Devices in LAVA always need to remain in a state which can be automated. This
  may add lots of extra requirements: custom hardware, extra cabling and other
  support devices not commonly found in general hosting locations. This also
  means that LAVA is **not** suitable for customer-facing testing, debugging or
  triage.

Physical layouts
****************

.. important:: If the master and one or more of the workers are to be connected
   across the internet instead of within a locally managed subnet,
   :ref:`encrpytion on the master <zmq_master_encryption>` and :ref:`on all
   workers <zmq_slave_encryption>` is **strongly recommended**.

LAVA V2 supports geographically separate masters and workers. Workers can be
protected behind a firewall or even using a NAT internet connection, without
the need to use dynamic DNS or other services. Connections are made from the
worker to the master, so the only requirement is that the :term:`ZMQ` ports
configured on the master are open to the internet and therefore use
**encryption**.

Physically separating different workers is also possible but has implications:

* Resources need to be mirrored, cached or proxied to multiple locations.

* The administrative burden of a LAVA lab is frequently based around the
  devices themselves. LAVA devices frequently require a range of support tasks
  which are unsuitable for generic hosting locations. It is common that a
  trained admin will need physical access to test device hardware to fix
  problems. The latency involved in getting someone to the location of the
  device to change a microSD card, press buttons on a problematic device,
  investigate :term:`PDU` failures and other admin tasks will have a large
  impact on the performance of the LAVA lab itself.

* Physical separation across different sites can mean that test writers may see
  varying performance according to which worker has idle devices at the time.
  If one worker has a slower connection to the build system storage, test
  writers will need to allow for this in the job submission timeouts, possibly
  causing jobs on faster workers to spend longer waiting for the timeout to
  expire.

* Each location still needs :abbr:`UPS (Uninterruptible Power Supply)`
  support, backup support and other common lab infrastructure as laid out
  previously.

Resources
*********

The Linaro lab in Cambridge has provided most of the real-world experience used
to construct this guide. If you are looking for guidance about how to grow your
lab, please talk to us on the :ref:`lava_devel` mailing list.

.. index:: scaling

.. _lab_scaling:

How many devices is too many for one worker?
============================================

* Consider the possible rate at which the devices may fail as well as the
  simple number of units. Most devices used in LAVA are prototypes or developer
  kits. The failure rate will vary enormously between labs according to the
  number and types of devices as well as the kind of test jobs being run but is
  likely to be much higher than any other machines in the same location not
  used in LAVA.

* The number of remote workers is typically determined by physical connectivity
  and I/O. Adding extra USB connectivity can be a particular problem. Most
  powered commodity USB hubs will fail in subtle ways under load. If the worker
  has limited USB connectivity, this could impact on how many devices can be
  supported on that worker.

* The number of remote workers per master (and therefore the number of masters
  per frontend) is typically determined by latency on the master when serving
  HTTP and API requests alongside the work of scheduling the testjobs and
  processing the logs. A frontend can dramatically improve performance by
  offloading the result analysis workload from the master.

* Be conservative and allow your lab to continue growing, slowly. Compare your
  plans with existing instances and :ref:`talk to us <getting_support>` about
  your plans before making commitments.

* If a worker starts struggling when test jobs start close together, it is time
  to provide at least one more worker. Watch for workers which need to use swap
  or other indications of high load. In the short term, admins may choose to take
  devices offline to manage spikes in load on workers but every such incident
  should raise the priority of adding more workers to the instance. LAVA test
  jobs can involve a lot of I/O, particularly in the deploy stage. A worker
  with devices which typically run lots of small, fast test jobs will be
  beneficial for CI but will run at a higher load than a worker with devices
  which run fewer, longer test jobs. Consider which devices are attached to which
  worker when balancing the load across the instance.

* Consider the types of devices on the worker. Some deployment methods have
  much larger I/O requirements than others. This can have a direct impact on
  how many devices of a particular type should be assigned to workers.

  .. seealso:: :ref:`bootloader_differences`

.. index:: geographic locations

.. _geography_and_workers:

Workers in different locations
******************************

Many labs have a separate master and multiple workers with the physical
machines co-located in the same or adjacent racks. This makes it easier to
administer the lab. Sometimes, admins may choose to have the master and one or
more workers in different geographical locations. There are some additional
considerations with such a layout.

.. note:: One or more LAVA V2 :term:`workers <worker>` will be required in the
   remote location. Each worker will need to be permanently connected to all
   devices to be supported by that worker. Devices cannot be used in LAVA
   without a worker managing the test jobs.

Before considering installing LAVA workers in remote locations, it is
**strongly** recommended that read and apply the following sections:

* :ref:`advanced_installation`, with particular emphasis on
  :ref:`infrastructure_requirements` and :ref:`more_installation_types`
* :ref:`growing_your_lab`
* :ref:`lab_scaling`

.. _remote_lab_infrastructure:

Remote Infrastructure
=====================

Remember that devices need additional, often highly specialised, infrastructure
support alongside the devices. Some of this hardware is used outside the
expected design limits. For example, a typical :term:`PDU` may be designed to
switch mains AC once or twice a month on each port. In LAVA, that unit will be
expected to switch the same load dozens, maybe hundreds of times per day for
each port. Monitoring and replacing this infrastructure before it fails can
have a significant impact on the ongoing cost of your proposed layout as well
as your expected scheduled downtime.

.. caution:: A typical datacentre will not have the infrastructure to handle
   LAVA devices and is unlikely to provide the kind of prompt physical access
   which will be needed by the admins.

.. _bootloader_differences:

Differences between bootloader types
====================================

The bootloader types used by the devices attached to a worker can have a major
impact on how many devices that worker can support. Some bootloaders are
comparatively lightweight, as they depend on the device **pulling** files from
the dispatcher during boot via a protocol like TFTP. This type of protocol
tends to be quite forgiving on timing while transferring files. Other
bootloaders (e.g. fastboot) work by **pushing** files to the device, which is
often much more demanding. Sometimes the data needs to be modified as it is
pushed *and* it is common that the device receiving the data cares about the
timing of the incoming data. A small delay at an inconvenient point may cause
an unexpected failure. When running multiple tests in parallel, the software
pushing the files may cause problems - it is designed to maximise the speed of
the first transfer at the expense of anything else. This "greedy" model means
that later requests running concurrently may block, thereby causing test jobs
to fail.

For this reason, we recommend that ``fastboot`` type devices are restricted to
**one device, one CPU core** (not a hyperthread, a real silicon core). This may
well apply to other bootloaders which require files to be pushed to devices but
has been most clearly shown with ``fastboot``.

Take particular care if the worker is a virtual machine and ensure that the
VM has as many cores as it has fastboot devices.

Also be careful if running the **master** and worker(s) on the same physical
hardware (e.g. running as VMs on the same server). The master also has CPU
requirements: users pulling results over the API or viewing test jobs in a
browser will cause load on the master, and the database can also add more load
as the number of test jobs increases. Try to avoid putting all the workers and
the master onto the same physical hardware. Even if this setup works initially,
unexpected failures can occur later as load increases.

Pay attention to the types of failures observed. If a previously working device
starts to fail in intermittent and unexpected ways, this could be a sign that
the infrastructure supporting that worker is suffering from excess load.

.. _maintenance_windows_remote:

Maintenance windows across remote locations
===========================================

All labs will need scheduled downtime. The layout of your lab will have a
direct impact on how those windows are managed across remote locations.
Maintenance will need to be announced in advance with enough time to allow test
jobs to finish running on the affected worker(s). Individual workers can have
all devices on that worker taken offline without affecting jobs on other
workers or the master. Adding a :term:`frontend` adds further granularity,
allowing maintenance to occur with less visible interruption.

Networking to remote locations
==============================

Encryption and authentication
-----------------------------

The :term:`ZMQ` connections between the master and the worker should always use
**authentication and encryption** if the connection goes across the internet
rather than a local subnet.

.. seealso:: :ref:`zmq_curve`

Firewalls
---------

The worker initiates the ZMQ connection to the master, so a worker will work
when behind a NAT connection. Only the address of the master needs to be
resolvable using public DNS. There is no need for the master or any other
service to be able to initiate a connection to the worker from outside the
firewall. This means that a public master can work with :term:`DUTs <DUT>` in a
remote location by connecting the boards to one or more worker(s) in the same
location.

If the master is behind a firewall, the ZMQ ports will need to be open.

.. seealso:: :ref:`publishing_events`

Using a frontend with remote labs
=================================

It is also worth considering if it will be easier to administer the various
devices by having a master alongside the worker(s) and then collating the
results from a number of different masters using a :term:`frontend`.

.. seealso:: :ref:`multiple_masters_multiple_workers`, :ref:`what_is_lava_not`
   and :ref:`custom_result_handling`.
