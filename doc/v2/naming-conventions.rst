.. index:: naming conventions

.. _naming_conventions:

Naming conventions and LAVA architecture
****************************************

Certain terms used in LAVA have specific meanings. Please be
consistent in the use of the following terms:

.. seealso:: :ref:`glossary`

**board**
  The physical hardware sitting in a rack or on a desk. The difference
  between a *board* and a *device* is that a board can be replaced if
  it fails completely, yet the device remains unchanged in the database
  and the replacement board can pick up running LAVA test jobs as soon
  as the device is set back to "good health". For example, a board can
  suffer an electrical short or connectors being sheared off. A device
  only changes state (Idle and Running) or health (Good, Bad,
  Maintenance, Retired).

  Integrating new types of board into LAVA can be a difficult and
  protracted process. CI requires high levels of reliability from
  boards, including when stressed at high load. Not all boards can be
  integrated into LAVA.

  .. seealso:: :ref:`adding_new_device_types` and :term:`health check`.

**connection**
  A means of communicating with a device. This will often involve
  using a serial port, but can also be SSH_ or another way of obtaining
  a shell-type interactive interface. Connections will typically
  require a POSIX_ type shell.

  .. _SSH: http://www.openssh.com/
  .. _POSIX: http://www.opengroup.org/austin/papers/posix_faq.html

  .. seealso:: :ref:`connections`

**device**
  In ``lava-server``, a :term:`device` is a database object in LAVA
  which stores configuration, information and status relating to a
  single board. The device information can be represented in export
  formats like YAML for use when the database is not accessible.

  In ``lava-dispatcher``, the database is not accessible so the
  scheduler prepares a simple dictionary of values derived from the
  database and the template to provide the information about the
  device.

  Devices are typically expected to persist long enough to provide long
  term comparative data, for example to support LTS teams.

**device tag**
  If specified boards have peripherals added (USB flash storage, SATA,
  HDMI etc.) then admins can choose to create a :term:`device tag` so
  that test writers can write test jobs which use those peripherals and
  the scheduler will assign the device according to the required device
  tags.

  A device tag is not meant to be a method of running specific test
  jobs on specific boards. LAVA is not a board farm and a board can be
  replaced at any time without affecting ongoing CI. There is no
  support in LAVA for allocating specific boards to specific test
  jobs, the two models are incompatible.

  Device tags frequently apply to multiple devices. This allows the
  queue of test jobs to be optimized and get results back to the
  developers as quickly as possible without compromising reliability.

  .. seealso:: :term:`device tag`

**device-type**
  A database object which collates similar devices into a group for
  purposes of scheduling. Devices of a single type are often the same
  vendor model but not all boards of the same model will necessarily be
  of the same :term:`device-type <device type>`.

  .. seealso:: :ref:`device_types`

**dispatcher**
  The dispatcher software relates to the ``lava_dispatcher`` module in
  git and the ``lava-dispatcher`` binary package in Debian. The
  dispatcher software for LAVA can be installed without the server or
  the scheduler and a machine configured in this way is also called a
  :term:`dispatcher`. Such machines are typically expensive, especially
  in a busy instance, which can have a big impact on how a LAVA lab is
  built.

**dynamic data**
  The Action base class provides access to dynamic data stores which
  other actions can access. This provides the way for action classes to
  share information like temporary paths of downloaded and / or
  modified files and other data which is generated or calculated during
  the operation of the pipeline. Use ``self.set_common_data`` to set
  the namespace, key and value and ``self.get_common_data`` to retrieve
  the value using the namespace and the key.

**parameters**
  A static, read-only, dictionary of values which are available for the job
  and the device. :term:`Parameters <parameters>` must not be modified
  by the codebase - use the ``common_data`` primitives of the Action
  base class to copy parameters and store the modified values as
  dynamic data.

**pipeline**
  The internal name for the design of LAVA V2, based on how the actions
  to be executed by the dispatcher are arranged in a unidirectional
  pipeline object. The contents of the pipe are validated before the
  job starts and the description of all elements in the pipe is
  retained for later reference.

  .. seealso:: :ref:`pipeline_construction` and :term:`pipeline` in the
     Glossary.

**protocol**
  An API used by the python code inside ``lava_dispatcher`` to interact
  with external systems and daemons when a shell like environment is
  not supported. :term:`Protocols <protocol>` need to be supported
  within the python codebase and currently include multinode, LXC and
  vland.

**server software**
  The server software relates to the ``lava_server``,
  ``lava_scheduler_app`` and ``lava_results_app`` source code in git
  and the ``lava-server`` binary package in Debian. It includes LAVA
  components covering the UI and the scheduler daemon.

**worker**
  A daemon running on each dispatcher machine which communicates with
  the lava-server-gunicorn using HTTP. The worker in LAVA uses whatever device
  configuration the server provides. Commands in the device
  configuration often use scripts and utilities which are only
  installed on that dispatcher.

  The objective of the worker is to run the specified jobs as reliably
  as possible. Each worker spawns one process for each job, executing
  the code in ``lava_dispatcher``.

**test job**
  A database object which is created for each submission and retains
  the logs and pipeline information generated when the slave executes
  the job on the device.

  Test jobs are not intended to test devices or boards. Test jobs exist
  to test software on multiple devices as part of continuous
  development of software, e.g. the Linux kernel. Each test
  job is used to test one software build using the first available
  device of the requested device-type. LAVA is not best suited to
  QA operations at the end of a production line.

**worker**
  A database object providing a connection to a **slave** daemon on a
  dispatcher. Each device must be assigned to a :term:`worker` to run a
  test job. One device can only be assigned to one worker at any one
  time. A single dispatcher can operate more than one worker, typically
  by hosting one or more slaves inside a docker container.

  Admins need to balance the number of devices on each worker according
  to the load caused when all devices on that worker are running test
  jobs simultaneously.

  .. note:: It is common to find that all devices on a worker could
     be executing at high load at precisely the same time. For example,
     decompressing downloaded files (causing high CPU load / RAM usage)
     or writing large files (high I/O load). Some test jobs may also
     cause high network load. Admins need to monitor and balance the
     load on each worker according to the specific workload of each
     instance.

  .. seealso:: :ref:`lab_scaling`.
