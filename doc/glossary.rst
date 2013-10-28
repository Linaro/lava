.. _glossary:

Glossary of terms
=================

.. glossary::

  health check
    A test job for one specific :term:`device type` which is automatically
    run at regular intervals to ensure that the physical device is capable
    of performing the minimum range of tasks. If the health check fails on
    a particular device of the specified device type, LAVA will automatically
    put that device :term:`Offline`.

  device type
    The common type of a number of devices in LAVA. The device type may
    have a :term:`health check` defined. Devices with the same device
    type will run the same health check at regular intervals.

  offline
    A status of a device which allows jobs to be submitted and reserved for
    the device but where the jobs will not start to run until the device is
    online. Devices enter the offline state when a health check fails on
    that device or the administrator puts the device offline.

  logging level
    Various commands within the LAVA test shell operations can be more
    verbose. The default logging level is ``INFO`` and the amount of
    logging can be increased by setting ``DEBUG``.

  dispatcher
    A server to which multiple devices are connected. The dispatcher has
    ``lava-dispatcher`` installed and passes the commands to the device
    and other processes involved in running the LAVA test. A dispatcher
    does not need to be at the same location as the server which runs
    the scheduler.

  device group
    A set of devices, defined in the JSON of an individual test job,
    which will run as a single group of tests within LAVA. Only devices
    within the group will be able to use the :ref:`multinode_api` to
    communicate between devices.

  role
    An arbitrary label used in MultiNode tests to determine which tests
    are run on the devices and inside the YAML to determine how the
    devices communicate.

  messageID
    Each message sent using the :ref:`multinode_api` uses a ``messageID``
    which is a string, unique within the group. It is recommended to
    make these strings descriptive using underscores instead of spaces.
    The messageID will be included the the log files of the test.

  stream
    Shorthand for a :term:`bundle stream` used in the ``submit_results``
    action in the JSON.

  bundle stream
    A way of organizing the :term:`result bundle`. A bundle stream could be
    imagined as a folder within which all related result bundles will be
    stored. A bundle stream could be private or anonymous. The shorthand
    ``stream`` is used in job definition to instruct where the results
    from the job should be submitted.

  result bundle
    A set of results submitted after a testing session. It contains
    multiple test runs, as well as other information about the system
    where the testing was performed.

  test run
    The result from a single test definition execution. The individual
    id and result of a single test within a test run is called the 
    Test Case.

  hwpack
     Linaro style hardware pack. Usually contains a boot loader(s),
     kernel, device tree blob and ramdisk.

  rootfs
     A tarball for the root file system.

  rootfstype
     Filesystem type for the root filesystem, e.g. ext2, ext3, ext4.
