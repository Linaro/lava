.. _glossary:

..
   Please add new terms in alphabetical order and feel free to
   relocate existing terms to match. Also, add a direct link to
   the item in the contents list. All terms are automatically
   added to the Sphinx index.

FIXME - need to add many more terms here

Glossary of terms
=================

[ :term:`action level` ]
[ :term:`device dictionary` ]
[ :term:`device group` ] [ :term:`device owner` ] [:term:`device status transition` ]
[ :term:`device tag` ][ :term:`device type` ] [ :term:`dispatcher` ]
[ :term:`distributed deployment`] [ :term:`DUT` ]
[ :term:`exclusive` ]
[ :term:`frontend` ]
[ :term:`health check` ] [:term:`hidden device type` ] [ :term:`hostname` ]
[ :term:`interface tag` ]
[ :term:`messageID` ]
[ :term:`MultiNode` ]
[ :term:`job definition` ]
[ :term:`offline` ]
[ :term:`pipeline` ]
[ :term:`PDU` ][ :term:`physical access` ] [ :term:`priority` ]
[ :term:`refactoring` ] [ :term:`results` ]
[ :term:`remote worker`] [ :term:`restricted device` ]
[ :term:`retired` ]
[ :term:`role` ] [ :term:`rootfs` ] [ :term:`rootfstype` ]
[ :term:`VLANd` ]
[ :term:`ZMQ` ]


.. glossary::

  action level
    The :term:`pipeline` is organised into sections and levels. The first
    section of the pipeline is given level 1. Sub tasks of that section start
    with level 1.1 and so on. Log files and job definitions will refer to
    actions using the level, e.g. to download the boot log of a job, the link
    will include the job ID, the action name and action level.
    e.g. ``job/8360/download/2.4.5-auto-login-action.log`` - job ID 8360, action
    level 2.4.5, action name auto-login-action.
    (The keyword ``download`` is used to separate the jobID from the action level.)
    Details of the action can then be accessed as: ``job/8360/definition#2.4.5``
    See also :ref:`pipeline_construction`

  device dictionary
    A key:value store within the LAVA server database which admins can
    modify to set configuration values for specific devices, specific
    to the :term:`pipeline` design. See :ref:`create_device_dictionary`
    and :ref:`viewing_device_dictionary_content`.

  device group
    A set of devices, defined in the JSON of an individual test job,
    which will run as a single group of tests within LAVA. Only devices
    within the group will be able to use the :ref:`multinode_api` to
    communicate between devices.

  device owner
    A device owner has permission to change the status of a particular
    device and update the free text description of a device. Note that
    superusers of the LAVA instance are always able to submit jobs to
    and administer any devices on that instance. See also :ref:`device_owner_help`
    and :ref:`owner_actions`.

  device status transition
    A record of when a device changed :ref:`device_status`, who caused
    the transition, when the transition took place as well as any message
    assigned to the transition. Individual transitions can be viewed in
    LAVA at ``<server>scheduler/transition/<ID>`` where the ID is a
    sequential integer. If the transition was caused by a job, this view
    will link to that job.

  device tag
    A tag is a device specific label which describes specific hardware
    capabilities of this specific device. Test jobs using tags will fail
    if no suitable devices exist matching the requested device tag or
    tags. Tags are typically used when only a proportion of the devices
    of the specified type have hardware support for a particular feature,
    possibly because those devices have peripheral hardware connected or
    enabled. A device tag can only be created or assigned to a particular
    device by a lab admin. When requesting tags, remember to include a
    description of what the tagged device can provide to a Test Job.

  device type
    The common type of a number of devices in LAVA. The device type may
    have a :term:`health check` defined. Devices with the same device
    type will run the same health check at regular intervals. See
    :ref:`device_types`.

  dispatcher
    A server to which multiple devices are connected. The dispatcher has
    ``lava-dispatcher`` installed and passes the commands to the device
    and other processes involved in running the LAVA test. A dispatcher
    does not need to be at the same location as the server which runs
    the scheduler. [#replacement]_

  distributed deployment
    A method of installing LAVA such that the load of running tests on
    devices is spread across multiple machines (dispatchers) which each act
    as a :term:`remote worker` with a single machine providing the web
    frontend, master scheduler and database connection. The design of
    the worker is changing drastically in the :term:`refactoring`.
    [#replacement]_

  DUT
    Device Under Test - a quick way to refer to the device in LAVA.

  exclusive
    The :term:`refactoring` and the consequent migration means that
    devices can have **three** states:

    * JSON only - current dispatcher jobs, pipeline jobs rejected.
    * JSON and Pipeline support - both models supported.
    * Pipeline only - JSON submissions would be rejected.

    If the device is marked as ``pipeline`` in the admin interface and
    has a :term:`device dictionary`, that device can support pipeline
    submissions.
    If the device dictionary marks the device as **exclusive**, then the
    device can only support pipeline submissions::

     {% set exclusive = "True" %}

    The state of the device is indicated in the device type and device
    detail pages. Accepted submissions are marked with a tick, rejected
    submissions marked with a cross. See also :ref:`device_owner_help`.

    Exclusive devices are intended to allow admins and developers to make
    changes in the refactoring without being limited by having to retain
    compatibility with the current dispatcher, e.g. to update the
    bootloader, to support new devices not supported by the current
    dispatcher at all or to indicate that the devices have completed a
    migration to the pipeline and prevent users mistakenly submitting
    old jobs.

    It is recommended to have pipeline support for all devices of the
    relevant device type before enabling exclusive pipeline support,
    especially if the device type has a :ref:`yaml_health_checks`

  frontend
    ``lava-server`` provides a generic `frontend` consisting of the Results,
    Queries, Job tables, Device tables and Charts. Many projects will need
    to customise this data to make it directly relevant to the developers.
    This is supported using the :ref:`xml_rpc` and REST API support.

    .. seealso:: :ref:`what_is_lava_not`

  hacking session
    A test job which uses a particular type of test definition to allow users to
    connect to a test device and interact with the test environment directly.
    Normally implemented by installing and enabling an SSH daemon inside the
    test image. Not all devices can support hacking sessions.
    See :ref:`hacking_session`.

  health check
    A test job for one specific :term:`device type` which is automatically
    run at regular intervals to ensure that the physical device is capable
    of performing the minimum range of tasks. If the health check fails on
    a particular device of the specified device type, LAVA will automatically
    put that device :term:`Offline`. See :ref:`health_checks`. Health checks
    have higher :term:`priority` than any other jobs.

  hidden device type
    A device type can be hidden by the LAVA administrators. Devices of
    a :ref:`v2_hidden_device_type` will only be visible to owners of at
    least once device of this type. Other users will not be able to
    access the job output, device status transition pages or bundle streams
    of devices of a hidden type. Devices of a hidden type will be shown
    as ``Unavailable`` in tables of test jobs and omitted from tables
    of devices and device types if the user viewing the table does not
    own any devices of the hidden type.

  hostname
    The unique name of this device in this LAVA instance, used to link all
    jobs, results and device information to a specific device configuration.

  interface tag
     An interface tag is similar to :term:`device tag` but operate **solely** within
     the :term:`VLANd` support. An interface tag may be related to the link
     speed which is achievable on a particular switch and port - it may also
     embed information about that link. See :ref:`vland_device_tags`.

  job definition
    The original JSON submitted to create a job in LAVA is retained in
    the database and can be viewed directly from the job log. Although
    the JSON is the same, the YAML may well have changed since the job
    was submitted, so some care is required when modifying job definitions
    from old jobs to make a new submission. If the job was a :term:`MultiNode`
    job, the MultiNode definition will be the unchanged JSON from the
    original submission; the job definition will be the parsed JSON for
    this particular device within the MultiNode job. [#replacement]_

  messageID
    Each message sent using the :ref:`multinode_api` uses a ``messageID``
    which is a string, unique within the group. It is recommended to
    make these strings descriptive using underscores instead of spaces.
    The messageID will be included the the log files of the test.

  MultiNode
     A single test job which runs across multiple devices. See
     :ref:`multinode_api` and :ref:`multinode_use_cases`.

  offline
    A status of a device which allows jobs to be submitted and reserved for
    the device but where the jobs will not start to run until the device is
    online. Devices enter the offline state when a health check fails on
    that device or the administrator puts the device offline.

  PDU
    Power Distribution Unit - a network-controlled set of relays which
    allow the power to the devices to be turned off and on remotely.
    Certain PDUs are supported by ``lavapdu-daemon`` to be able to
    hard reset devices in LAVA.

  physical access
    The user or group with physical access to the device, for example
    to fix a broken SD card or check for possible problems with physical
    connections. The user or group with physical access is recommended
    to be one of the superusers.

  pipeline
    Within LAVA, the ``pipeline`` is the new model for the dispatcher
    code as part of the :term:`refactoring` where submitted jobs are
    converted to a pipeline of discrete actions - each pipeline is
    specific to the structure of that submission and the entire pipeline
    is validated before the job starts. The model integrates concepts
    like fail-early, error identification, avoid defaults, fail and
    diagnose later, as well as giving test writers more rope to make
    LAVA more transparent. See :ref:`dispatcher_design` and
    :ref:`pipeline_use_cases`.

  priority
    A job has a default priority of ``Medium``. This means that the job
    will be scheduled according to the submit time of the job, in a list
    of jobs of the same priority. Every :term:`health check` has a higher
    priority than any submitted job and if a health check is required, it
    will **always** run before any other jobs. Priority only has any
    effect while the job is queued as ``Submitted``.

  remote worker
    A dispatcher with devices attached which does not have a web frontend
    but which uses a connection to a remote lava-server to retrieve the
    list of jobs for supported boards. [#replacement]_

  refactoring
    Within LAVA, the process of developing the :term:`pipeline` code
    in parallel with the existing code, resulting in new elements
    alongside old code - possibly disabled on some instances.
    See :ref:`dispatcher_design` and :ref:`pipeline_use_cases`.

  restricted device
    A restricted device can only accept job submissions from the device
    owner. If the device owner is a group, all users in that group can
    submit jobs to the device.

  results
    Within the :term:`pipeline` changes, a new ``lava_results_app``
    replaces `result bundle` and `stream` and provides
    ``Query`` to replace `filter`. This code is in ongoing
    development but includes support for:

    * viewing results so far while the test job is still running
    * retaining results from earlier actions even if the test job
      fails later
    * allowing any action in the pipeline to generate results
    * linking results with metadata from the test job
    * all results are referenced solely using the test job ID, not
      hashes or dates.

    Queries will provide replacement functionality for the deprecated
    `filter` support, allowing queries to mix results and metadata.

  retired
    A device is retired when it can no longer be used by LAVA. A retired
    device allows historical data to be retained in the database, including
    log files, result bundles and state transitions. Devices can also be
    retired when the device is moved from one instance to another.

  role
    An arbitrary label used in MultiNode tests to determine which tests
    are run on the devices and inside the YAML to determine how the
    devices communicate.

  rootfs
     A tarball for the root file system.

  rootfstype
     Filesystem type for the root filesystem, e.g. ext2, ext3, ext4.

  test run
    The result from a single test definition execution. The individual
    id and result of a single test within a test run is called the
    Test Case. [#replacement]_

  tftp
    Trivial File Transfer Protocol (TFTP) is a file transfer protocol,
    mainly to serve boot images over the network to other machines (PXE).
    The protocol is managed by the
    `tftpd-hpa package <https://tracker.debian.org/pkg/tftp-hpa>`_ and
    **not** by LAVA directly. See :ref:`tftp_support`.

  VLANd
    VLANd is a daemon to support virtual local area networks in LAVA. This
    support is specialised and requires careful configuration of the
    entire LAVA instance, including the physical layout of the switches
    and the devices of that instance. See :ref:`vland_in_lava` or
    :ref:`admin_vland_lava`.

  ZMQ
    Zero MQ (or `0MQ <http://en.wikipedia.org/wiki/%C3%98MQ>`_) is
    the basis of the :term:`refactoring` to solve a lot of the problems
    inherent in the `distributed_instance`. The detail of this
    change is only relevant to developers but it allows LAVA to remove
    the need for ``postgresql`` and ``sshfs`` connections between the
    master and remote workers. It allows remote workers to no longer
    need ``lava-server`` to be installed on the worker. Developers can
    find more information in the :ref:`dispatcher_design` documentation.

.. [#deprecated] These terms reflect objects and methods which will be
   removed after the migration to the new :ref:`dispatcher_design`.

.. [#replacement] These items will be replaced in meaning or detail
   after the migration to the new :ref:`dispatcher_design`.
