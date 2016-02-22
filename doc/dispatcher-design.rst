.. _dispatcher_design:

Lava Dispatcher Design
######################

This is the **developer** documentation for the new dispatcher design.
See :ref:`refactoring_use_cases` for information for lab administrators
and users of the new design.

The refactoring takes place alongside the current dispatcher and existing
JSON jobs are unaffected. A migration will take place where individual
devices are configured for
:ref:`pipeline support <pipeline_device_requirements>` and individual jobs
are then re-written using the :ref:`pipeline_schema <pipeline_schema>`.
The administrator of each instance will be able to manage their own
migration and at some point after ``validation.linaro.org`` has completed
the migration of all devices to pipeline support, the support for the
current dispatcher will be removed. Detailed planning for the migration
of ``validation.linaro.org`` has not begun and details will be
announced using the `Linaro Validation mailing list`_ before the migration
itself starts on ``validation.linaro.org``.

The LAVA developers use a `playground instance <http://playground.validation.linaro.org>`_
which has already begun a migration.

Devices indicate their support for pipeline jobs in the
:ref:`detailed device information <device_owner_help>` for each device
and device type.

.. _Linaro Validation mailing list: http://lists.linaro.org/mailman/listinfo/linaro-validation

Pipeline Architecture
*********************

Compare with the :ref:`current architecture <lava_architecture>`::

   +------------------[master]-------------+
   |  +-------------+      +----------+    |
   |  |web interface| ---> | database |    |
   |  +-------------+      +----------+    |
   |                           |           |
   |  +--------------------------+         |
   |  | dispatcher-master daemon |         |
   |  +--------------------------+         |
   +-----------+---------------------------+
               |
              ZMQ
               |
   +-----------+------[worker]-------------+
   |           |                           |
   |  +-----------------+    +----------+  |
   |  |lava-slave daemon| -> |dispatcher|  |
   |  +-----------------+    +----------+  |
   |                              |        |
   +------------------------------+--------+
                                  |
                                  V
                        +-------------------+
                        | device under test |
                        +-------------------+

Principal changes
=================

#. **Database isolation** - only one daemon has a connection to the
   database, the master daemon. This simplifies the architecture and
   avoids the use of fault-intolerant database connections to remote
   workers.
#. **Drop use of SSHFS** between workers and master - this was awkward
   to configure and problematic over external connections.
#. **Move configuration onto the master** - the worker becomes a simple
   slave which receives all configuration and tasks from the master.

.. _objectives:

Objectives
**********

The new dispatcher design is intended to make it easier to adapt the
dispatcher flow to new boards, new mechanisms and new deployments. It
also shifts support to do less work on the dispatcher, make fewer
assumptions about the test in the dispatcher configuration and put more
flexibility into the hands of the test writer.

.. note:: The new code is still developing, some areas are absent,
          some areas will change substantially before it will work.
          All details here need to be seen only as examples and the
          specific code may well change independently. This documentation
          is aimed at LAVA developers - although some content covers user
          facing actions, the syntax and parameters for these actions
          are still subject to change and do not constitute an API.

From **2015.8 onwards** the sample jobs supporting the unit tests
conform to the :ref:`pipeline_schema`.

Design
******

Start with a Job which is broken up into a Deployment, a Boot and a
Test class. Results are transmitted live during any part of the job.

+-------------+--------------------+------------------+-------------------+
|     Job     |                    |                  |                   |
+=============+====================+==================+===================+
|             |     Deployment     |                  |                   |
+-------------+--------------------+------------------+-------------------+
|             |                    |   DeployAction   |                   |
+-------------+--------------------+------------------+-------------------+
|             |                    |                  |  DownloadAction   |
+-------------+--------------------+------------------+-------------------+
|             |                    |                  |  ChecksumAction   |
+-------------+--------------------+------------------+-------------------+
|             |                    |                  |  MountAction      |
+-------------+--------------------+------------------+-------------------+
|             |                    |                  |  CustomiseAction  |
+-------------+--------------------+------------------+-------------------+
|             |                    |                  |  TestDefAction    |
+-------------+--------------------+------------------+-------------------+
|             |                    |                  |  UnmountAction    |
+-------------+--------------------+------------------+-------------------+
|             |                    |   BootAction     |                   |
+-------------+--------------------+------------------+-------------------+
|             |                    |   TestAction     |                   |
+-------------+--------------------+------------------+-------------------+

The Job manages the Actions using a Pipeline structure. Actions
can specialise actions by using internal pipelines and an Action
can include support for retries and other logical functions:

+------------------------+----------------------------+
|     DownloadAction     |                            |
+========================+============================+
|                        |    HttpDownloadAction      |
+------------------------+----------------------------+
|                        |    FileDownloadAction      |
+------------------------+----------------------------+

If a Job includes one or more Test definitions, the Deployment can then
extend the Deployment to overlay the LAVA test scripts without needing
to mount the image twice:

+----------------------+------------------+---------------------------+
|     DeployAction     |                  |                           |
+======================+==================+===========================+
|                      |   OverlayAction  |                           |
+----------------------+------------------+---------------------------+
|                      |                  |   MultinodeOverlayAction  |
+----------------------+------------------+---------------------------+
|                      |                  |   LMPOverlayAction        |
+----------------------+------------------+---------------------------+

The TestDefinitionAction has a similar structure with specialist tasks
being handed off to cope with particular tools:

+--------------------------------+-----------------+-------------------+
|     TestDefinitionAction       |                 |                   |
+================================+=================+===================+
|                                |    RepoAction   |                   |
+--------------------------------+-----------------+-------------------+
|                                |                 |   GitRepoAction   |
+--------------------------------+-----------------+-------------------+
|                                |                 |   BzrRepoAction   |
+--------------------------------+-----------------+-------------------+
|                                |                 |   TarRepoAction   |
+--------------------------------+-----------------+-------------------+
|                                |                 |   UrlRepoAction   |
+--------------------------------+-----------------+-------------------+

.. _code_flow:

Following the code flow
***********************

+------------------------------------------+---------------------------------------------------+
|                Filename                  |   Role                                            |
+==========================================+===================================================+
| lava/dispatcher/commands.py              | Command line arguments, call to YAML parser       |
+------------------------------------------+---------------------------------------------------+
| lava_dispatcher/pipeline/device.py       | YAML Parser to create the Device object           |
+------------------------------------------+---------------------------------------------------+
| lava_dispatcher/pipeline/parser.py       | YAML Parser to create the Job object              |
+------------------------------------------+---------------------------------------------------+
| ....pipeline/actions/deploy/             | Handlers for different deployment strategies      |
+------------------------------------------+---------------------------------------------------+
| ....pipeline/actions/boot/               | Handlers for different boot strategies            |
+------------------------------------------+---------------------------------------------------+
| ....pipeline/actions/test/               | Handlers for different LavaTestShell strategies   |
+------------------------------------------+---------------------------------------------------+
| ....pipeline/actions/deploy/image.py     | DeployImages strategy creates DeployImagesAction  |
+------------------------------------------+---------------------------------------------------+
| ....pipeline/actions/deploy/image.py     | DeployImagesAction.populate adds deployment       |
|                                          | actions to the Job pipeline                       |
+------------------------------------------+---------------------------------------------------+
|   ***repeat for each strategy***         | each ``populate`` function adds more Actions      |
+------------------------------------------+---------------------------------------------------+
| ....pipeline/action.py                   | ``Pipeline.run_actions()`` to start               |
+------------------------------------------+---------------------------------------------------+

The deployment is determined from the device_type specified in the Job
(or the device_type of the specified target) by reading the list of
support methods from the device_types YAML configuration.

Each Action can define an internal pipeline and add sub-actions in the
``Action.populate`` function.

Particular Logic Actions (like RetryAction) require an internal pipeline
so that all actions added to that pipeline can be retried in the same
order. (Remember that actions must be idempotent.) Actions which fail
with a JobError or InfrastructureError can trigger Diagnostic actions.
See :ref:`retry_diagnostic`.

.. code-block:: yaml

 actions:
   deploy:
     allow:
       - image
   boot:
     allow:
       - image

This then matches the python class structure::

 actions/
    deploy/
        image.py

The class defines the list of Action classes needed to implement this
deployment. See also :ref:`dispatcher_actions`.

.. _pipeline_construction:

Pipeline construction and flow
******************************

The pipeline is a FIFO_ and has branches which are handled as a `tree walk`_. The top level
object is the job, based on the YAML definition supplied by the
**dispatcher-master**. The definition is processed by the scheduler and the
submission interface with information specific to the actual device. The
processed definition is parsed to generate the top level pipeline and
:ref:`strategy classes <using_strategy_classes>`. Each strategy class
adds a top level action to the top level pipeline. The top level action
then populates branches containing more actions.

Actions are populated, validated and executed in strict order. The next
action in any branch waits until all branches of the preceding action
have completed. Populating an action in a pipeline creates a **level**
string, e.g. all actions in level 1.2.1, including all actions in sublevel
1.2.1.2 are executed before the pipeline moves on to processing level
1.3 or 2::

    Deploy (1)
       |
       \___ 1.1
       |
       \ __ 1.2
       |     |
       |     \_ 1.2.1
       |     |   |
       |     |   \_ 1.2.1.1
       |     |   |
       |     |   \_ 1.2.1.2
       |     |         |
       |     |         \__ 1.2.1.2.1
       |     |
       |     \__1.2.2
       |
       \____1.3
       |
      Boot (2)
       |
       \_ 2.1
       |
       \_ 2.2


#. One device per job. One top level pipeline per job

   * loads only the configuration required for this one job.

#. A NewDevice is built from the target specified (commands.py)
#. A Job is generated from the YAML by the parser.
#. The top level Pipeline is constructed by the parser.
#. Strategy classes are initialised by the parser

   #. Strategy classes add the top level Action for that strategy to the
      top level pipeline.
   #. Top level pipeline calls ``populate()`` on each top level Action added.

      #. Each ``Action.populate()`` function may construct one internal
         pipeline, based on parameters.
      #. internal pipelines call ``populate()`` on each Action added.
      #. A sublevel is set for each action in the internal pipeline.
         Level 1 creates 1.1 and level 2.3.2 creates 2.3.2.1.

#. Parser waits whilst each Strategy completes branch population.
#. Parser adds the FinalizeAction to the top-level pipeline
#. Loghandlers are set up
#. Job validates the completed pipeline

   #. Dynamic data can be added to the context

#. If ``--validate`` not specified, the job runs.

   #. Each ``run()`` function can add dynamic data to the context and/or
      results to the pipeline.
   #. Pipeline walks along the branches, executing actions.

#. Job ends, check for errors
#. Completed pipeline is available.

.. _FIFO: https://en.wikipedia.org/wiki/FIFO_(computing_and_electronics)
.. _tree walk: https://en.wikipedia.org/wiki/Tree_traversal

.. _using_strategy_classes:

Using strategy classes
======================

Strategies are ways of meeting the requirements of the submitted job within
the limits of available devices and code support.

If an internal pipeline would need to allow for optional actions, those
actions still need to be idempotent. Therefore, the pipeline can include
all actions, with each action being responsible for checking whether
anything actually needs to be done. The populate function should avoid
using conditionals. An explicit select function can be used instead.

Whenever there is a need for a particular job to use a different Action
based solely on job parameters or device configuration, that decision
should occur in the Strategy selection using classmethod support.

Where a class is used in lots of different strategies, identify whether
there is a match between particular strategies always needing particular
options within the class. At this point, the class can be split and
particular strategies use a specialised class implementing the optional
behaviour and calling down to the base class for the rest.

If there is no clear match, for example in ``testdef.py`` where any
particular job could use a different VCS or URL without actually being
a different strategy, a select function is preferable. A select handler
allows the pipeline to contain only classes supporting git repositories
when only git repositories are in use for that job.

The list of available strategies can be determined in the codebase from
the module imports in the ``strategies.py`` file for each action type.

This results in more classes but a cleaner (and more predictable)
pipeline construction.

Lava test shell scripts
=======================

.. note:: See :ref:`criteria` - it is a mistake to think of the LAVA
          test support scripts as an *overlay* - the scripts are an
          **extension** to the test. Wherever possible, current
          deployments are being changed to supply the extensions
          alongside the deployment instead of overlaying, and thereby
          altering, the deployment.

The LAVA scripts are a standard addition to a LAVA test and are handled as
a single unit. Using idempotent actions, the test script extension can
support LMP or MultiNode or other custom requirements without requiring
this support to be added to all tests. The extensions are created during
the deploy strategy and specific deployments can override the
``ApplyExtensionAction`` to unpack the extension tarball alongside the
test during the deployment phase and then mount the extension inside the
image. The tarball itself remains in the output directory and becomes
part of the test records. The checksum of the overlay is added to the
test job log.

Pipeline error handling
***********************

.. _runtime_error_exception:

RuntimeError Exception
======================

Runtime errors include:

#. Parser fails to handle device configuration
#. Parser fails to handle submission YAML
#. Parser fails to locate a Strategy class for the Job.
#. Code errors in Action classes cause Pipeline to fail.
#. Errors in YAML cause errors upon pipeline validation.

Each runtime error is a bug in the code - wherever possible, implement
a unit test to prevent regressions.

.. _infrastructure_error_exception:

InfrastructureError Exception
=============================

Infrastructure errors include:

#. Missing dependencies on the dispatcher
#. Device configuration errors

.. _job_error_exception:

JobError Exception
==================

Job errors include:

#. Failed to find the specified URL.
#. Failed in an operation to create the necessary extensions.

.. _test_error_exception:

TestError Exception
===================

Test errors include:

#. Failed to handle a signal generated by the device
#. Failed to parse a test case

Result bundle identifiers
*************************

Old style result bundles are assigned a text based UUID during submission.
This has several issues:

* The UUID is not sequential or predictable, so finding this one, the
  next one or the previous one requires a database lookup for each. The
  new dispatcher model will not have a persistent database connection.
* The UUID is not available to the dispatcher whilst running the job, so
  cannot be cross-referenced to logs inside the job.
* The UUID makes the final URL of individual test results overly long,
  unmemorable and complex, especially as the test run is also given
  a separate UUID in the old dispatcher model.

The new dispatcher creates a pipeline where every action within the
pipeline is guaranteed to have a unique *level* string which is strictly
sequential, related directly to the type of action and shorter than a
UUID. To make a pipeline result unique on a per instance basis, the only
requirement is that the result includes the JobID which is a sequential
number, passed to the job in the submission YAML. This could also have
been a UUID but the JobID is already a unique ID **for this instance**.

When bundles are downloaded, the database query will need to assign a
UUID to that downloaded file but the file will also include the job
number and the query can also insert the source of the bundle in a
comment in the YAML. This will allow bundles to be uploaded to a different
instance using :ref:`lava-tool <lava_tool>` without the risk of collisions.
It is also possible that the results could provide a link back to the
original job log file and other data - if the original server is visible
to users of the server to which the bundle was later uploaded.

.. _criteria:

Refactoring review criteria
***************************

The refactored dispatcher has different objectives to the original and
any assumptions in the old code must be thrown out. It is very easy to
fall into the old way of writing dispatcher code, so these criteria are
to help developers control the development of new code. Any of these
criteria can be cited in a code review as reasons for a review to be
improved.

.. _keep_dispatcher_dumb:

Keep the dispatcher dumb
========================

There is a temptation to make the dispatcher clever but this only
restricts the test writer from doing their own clever tests by hard
coding commands into the dispatcher codebase. If the dispatcher needs
some information about the test image, that information **must** be
retrieved from the job submission parameters, **not** by calculating
in the dispatcher or running commands inside the test image. Exceptions
to this are the metrics already calculated during download, like file
size and checksums. Any information about the test image which is
permanent within that image, e.g. the partition UUID strings or the
network interface list, can be identified by the process creating that
image or by a script which is run before the image is compressed and
made available for testing. If a test uses a tarball instead of an image,
the test **must** be explicit about the filesystem to use when
unpacking that tarball for use in the test as well as the size and
location of the partition to use.

LAVA will need to implement some safeguards for tests which still need
to deploy any test data to the media hosting the bootloader (e.g. fastboot,
SD card or UEFI) in order to avoid overwriting the bootloader itself.
Therefore, although SD card partitions remain available for LAVA tests
where no other media are supportable by the device, those tests can
**only** use tarballs and pre-defined partitions on the SD card. The
filesystem to use on those partitions needs to be specified by the test
writer.

.. _defaults:

Avoid defaults in dispatcher code
=================================

Constants and defaults are going to need an override somewhere for some
device or test, eventually. Code defensively and put constants into
the utilities module to support modification. Put defaults into the
YAML, not the python code. It is better to have an extra line in the
device_type than a string in the python code as this can later be
extended to a device or a job submission.

Let the test fail and diagnose later
====================================

**Avoid guessing** in LAVA code. If any operation in the dispatcher
could go in multiple paths, those paths must be made explicit to the
test writer. Report the available data, proceed according to the job
definition and diagnose the state of the device afterwards, where
appropriate.

**Avoid trying to be helpful in the test image**. Anticipating an error
and trying to code around it is a mistake. Possible solutions include
but are not limited to:

* Provide an optional, idempotent, class which only acts if a specific
  option is passed in the job definition. e.g. AutoLoginAction.
* Provide a diagnostic class which triggers if the expected problem
  arises. Report on the actual device state and document how to improve
  the job submission to avoid the problem in future.
* Split the deployment strategy to explicitly code for each possible
  path.

AutoLogin is a good example of the problem here. For too long, LAVA has
made assumptions about the incoming image, requiring hacks like
``linaro-overlay`` packages to be added to basic bootstrap images or
disabling passwords for the root user. These *helpful* steps act to
make it harder to use unchanged third party images in LAVA tests.
AutoLogin is the *de facto* default for non-Linaro images.

Another example is the assumption in various parts of LAVA that the
test image will raise a network interface and repeatedly calling ``ping``
on the assumption that the interface will appear, somehow, eventually.

.. _black_box_deploy:

Treat the deployment as a black box
===================================

LAVA has claimed to do this for a long time but the refactored
dispatcher is pushing this further. Do not think of the LAVA scripts
as an *overlay*, the LAVA scripts are **extensions**. When a test wants
an image deployed, the LAVA extensions should be deployed alongside the
image and then mounted to create a ``/lava-$hostname/`` directory. Images
for testing within LAVA are no longer broken up or redeployed but **must**
be deployed **intact**. This avoids LAVA needing to know anything about
issues like SELinux or specific filesystems but may involve multiple
images for systems like Android where data may exist on different physical
devices.

.. _essential_components:

Only protect the essential components
=====================================

LAVA has had a tendency to hardcode commands and operations and there
are critical areas which must still be protected from changes in the
test but these critical areas are restricted to:

#. The dispatcher.
#. Unbricking devices.

**Any** process which has to run on the dispatcher itself **must** be
fully protected from mistakes within tests. This means that **all**
commands to be executed by the dispatcher are hardcoded into the dispatcher
python code with only limited support for overriding parameters or
specifying *tainted* user data.

Tests are prevented from requiring new software to be installed on any
dispatcher which is not already a dependency of ``lava-dispatcher``.
Issues arising from this need to be resolved using MultiNode.

Until such time as there is a general and reliable method of deploying
and testing new bootloaders within LAVA tests, the bootloader / firmware
installed by the lab admin is deemed sacrosanct and must not be altered
or replaced in a test job. However, bootloaders are generally resilient
to errors in the commands, so the commands given to the bootloader remain
accessible to test writers.

It is not practical to scan all test definitions for potentially harmful
commands. If a test inadvertently corrupts the SD card in such a way that
the bootloader is corrupted, that is an issue for the lab admins to
take up with the test submitter.

Give the test writer enough rope
================================

Within the provisos of :ref:`essential_components`, the test writer
needs to be given enough rope and then let LAVA **diagnose** issues
after the event.

There is no reason to restrict the test writer to using LAVA commands
inside the test image - as long as the essential components remain
protected.

Examples:

#. KVM devices need to protect the QEMU command line because these
   commands run on the dispatcher
#. VM devices running on an arndale do **not** need the command line
   to be coded within LAVA. There have already been bug reports on this
   issue.

:ref:`diagnostic_actions` report on the state of the device after some
kind of error. This reporting can include:

* The presence or absence of expected files (like ``/dev/disk/by-id/``
  or ``/proc/net/pnp``).
* Data about running processes or interfaces, e.g. ``ifconfig``

It is a mistake to attempt to calculate data about a test image - instead,
require that the information is provided and **diagnose** the actual
information if the attempt to use the specified information fails.

Guidance
========

#. If the command is to run inside a deployment, **require** that the
   **full** command line can be specified by the test writer. Remember:
   :ref:`defaults`. It is recommended to have default commands where
   appropriate but these defaults need to support overrides in the job
   submission. This includes using a locally built binary instead of an
   executable installed in ``/usr/bin`` or similar.
#. If the command is run on a dispatcher, **require** that the binary
   to be run on the dispatcher is actually installed on the dispatcher.
   If ``/usr/bin/git`` does not exist, this is a validation error. There
   should be no circumstances where a tool required on the dispatcher
   cannot be identified during validation of the pipeline.
#. An error from running the command on the dispatcher with user-specified
   parameters is a JobError.
#. Where it is safe to do so, offer **overrides** for supportable
   commandline options.

The codebase itself will help identify how much control is handed over
to the test writer. ``self.run_command()`` is a dispatcher call and
needs to be protected. ``connection.sendline()`` is a deployment
call and does not need to be protected.

Providing gold standard images
==============================

Test writers are strongly recommended to only use a known working
setup for their job. A set of gold standard jobs will be defined in
association with the QA team. These jobs will provide a known baseline
for test definition writers, in a similar manner as the existing QA test
definitions provide a base for more elaborate testing.

There will be a series of images provided for as many device types as
practical, covering the basic deployments. Test definitions will be
required to be run against these images before the LAVA team will spend
time investigating bugs arising from tests. These images will provide a
measure of reassurance around the following issues:

* Kernel fails to load NFS or ramdisk.
* Kernel panics when asked to use secondary media.
* Image containing a different kernel to the gold standard fails
  to deploy.

.. note:: It is imperative that test writers understand that a gold
          standard deployment for one device type is not necessarily
          supported for a second device type. Some devices will
          never be able to support all deployment methods due to
          hardware constraints or the lack of kernel support. This is
          **not** a bug in LAVA.
          If a particular deployment is supported but not stable on a
          device type, there will not be a gold standard image for that
          deployment. Any issues in the images using such deployments
          on that type are entirely down to the test writer to fix.

The refactoring will provide :ref:`diagnostic_actions` which point at
these issues and recommend that the test is retried using the standard
kernel, dtb, initramfs, rootfs and other components.

The reason to give developers enough rope is precisely so that kernel
developers are able to fix issues in the test images before problems
show up in the gold standard images. Test writers need to work with the
QA team, using the gold standard images.

Creating a gold standard image
------------------------------

Part of the benefit of a standard image is that the methods for building
the image - and therefore the methods for updating it, modifying it and
preparing custom images based upon it - must be documented clearly.

Where possible, standard tools familiar to developers of the OS concerned
should be used, e.g. debootstrap for Debian based images. The image can
also be a standard OS install. Gold standard images are not "Linaro"
images and should not require Linaro tools. Use AutoLogin support where
required instead of modifying existing images to add Linaro-specific
tools.

All gold standard images need to be kept up to date with the base OS as
many tests will want to install extra software on top and it will waste
time during the test if a lot of other packages need to be updated at
the same time. An update of a gold standard image still needs to be
tested for equivalent or improved performance compared to the current
image before replacing it.

The documentation for building and updating the image needs to be
provided alongside the image itself as a README. This text file should
also be reproduced on a wiki page and contain a link to that page. Any
wiki can be used - if a suitable page does not already exist elsewhere,
use wiki.linaro.org.

Other gold standard components
------------------------------

The standard does not have to be a complete OS image - a kernel with a
DTB (and possibly an initrd) can also count as a standard ramdisk image.
Similarly, a combination of kernel and rootfs can count as a standard
NFS configuration.

The same requirement exists for documenting how to build, modify and
update all components of the "image" and the set of components need to
be tested as a whole to represent a test using the standard.

In addition, information about the prompts within the image needs to be
exposed. LAVA no longer has a list of potential prompts and each job must
specify a list of prompts to use for the job.

Other information should also be provided, for example, memory requirements or
CPU core requirements for images to be used with QEMU or dependencies on other
components (like firmware or kernel support).

Test writers need to have enough information to submit a job without
needing to resubmit after identifying and providing missing data.

One or more sample test jobs is one way of providing this information but
it is still recommended to provide the prompts and other information explicitly.

.. _secondary_media:

Secondary media
***************

With the migration from master images on an SD card to dynamic master
images over NFS, other possibilities arise from the refactoring.

* Deploy a ramdisk, boot and deploy an entire image to a USB key, boot
  and direct bootloader at USB filesystem, including kernel and initrd.
* Deploy an NFS system, boot and bootstrap an image to SATA, boot and
  direct bootloader at SATA filesystem, including kernel and initrd.
* Deploy using a script written by the test author (e.g. debootstrap)
  which is installed in the initial deployment. Parameters for the
  script need to be contained within the test image.

Secondary deployments are done by the device under test, using actions
defined by LAVA and tools provided by the initial deployment. Test writers
need to ensure that the initial deployment has enough support to complete
the second deployment. See :ref:`uuid_device_node`.

Images on remote servers are downloaded to the dispatcher (and decompressed
where relevant) so that the device does not need to do the decompression
or need lots of storage in the initial deployment.

By keeping the downloaded image intact, it becomes possible to put the
LAVA extensions alongside the image instead of inside.

To make this work, several requirements must be met:

* The initial deployment must provide or support installation of all
  tools necessary to complete the second deployment - it is a TestError
  if there is insufficient space or the deployment cannot complete
  this step.
* The initial deployment does not need enough space for the decompressed
  image, however, the initial deployment is responsible for writing the
  decompressed image to the secondary media from ``stdin``, so the amount
  of memory taken up by the initial deployment can have an impact on the
  speed or success of the write.
* The operation of the second deployment is an action which
  **precedes** the second boot. There is no provision for getting
  data back from this test shell into the boot arguments for the next
  boot. Any data which is genuinely persistent needs to be specified
  in advance.
* LAVA manages the path to which the second deployment is written, based
  on the media supported by the device and the ID of that media. Where
  a device supports multiple options for secondary media, the job specifies
  which media is to be used.
* LAVA will need to support instructions in the job definition which
  determine whether a failed test shell should allow or skip the
  boot action following.
* LAVA will declare available media using the **kernel interface** as
  the label. A SATA drive which can only be attached to devices of a
  particular :term:`device type` using USB is still a USB device as it
  is constrained by the USB interface being present in the test image
  kernel. A SATA drive attached to a SATA connector on the board is a
  SATA device in LAVA (irrespective of how the board actually delivers
  the SATA interface on that connector).
* If a device has multiple media of the same type, it is up to the test
  writer to determine how to ensure that the correct image is booted.
  The ``blkid`` of a partition within an image is a permanent UUID within
  that image and needs to be determined in advance if this is to be used
  in arguments to the bootloader as the root filesystem.
* The manufacturer ID and serial number of the hardware to be used for
  the secondary deployment must be set in the device configuration. This
  makes it possible for test images to use such support as is available
  (e.g. ``udev``) to boot the correct device.
* The job definition needs to specify which hardware to use for the
  second deployment - if this label is based on a device node, it is a
  TestError if the use of this label does not result in a successful
  boot.
* The job definition also needs to specify the path to the kernel, dtb
  and the partition containing the rootfs within the deployed image.
* The job definition needs to include the bootloader commands, although
  defaults can be provided in some cases.

.. _uuid_device_node:

UUID vs device node support
===========================

A deployment to secondary media must be done by a running kernel, not
by the bootloader, so restrictions apply to that kernel:

#. Device types with more than one media device sharing the same device
   interface must be identifiable in the device_type configuration.
   These would be devices where, if all slots were populated, a full
   udev kernel would find explicitly more than one ``/dev/sd*`` top
   level device. It does not matter if these are physically different
   types of device (cubietruck has usb and sata) or the same type
   (d01 has three sata). The device_type declares the flag:
   ``UUID-required: True`` for each relevant interface. For cubietruck::

    media:  # two USB slots, one SATA connector
      usb:
        UUID-required: True
      sata:
        UUID-required: False

#. It is important to remember that there are five different identifiers
   involved across the device configuration and job submission:

   #. The ID of the device as it appears to the kernel running the deploy,
      provided by the device configuration: ``uuid``. This is found in
      ``/dev/disk/by-id/`` on a booted system.
   #. The ID of the device as it appears to the bootloader when reading
      deployed files into memory, provided by the device configuration:
      ``device_id``. This can be confirmed by interrupting the bootloader
      and listing the filesystem contents on the specified interface.
   #. The ID of the partition to specify as ``root`` on the kernel
      command line of the deployed kernel when booting the kernel inside
      the image, set by the job submission ``root_uuid``. Must be specified
      if the device has UUID-required set to True.
   #. The ``boot_part`` specified in the job submission which is the
      partition number inside the deployed image where the files can be
      found for the bootloader to execute. Files in this partition will
      be accessed directly through the bootloader, not via any mountpoint
      specified inside the image.
   #. The ``root_part`` specified in the job submission which is the
      partition number inside the deployed image where the root filesystem
      files can be found by the depoyed kernel, once booted. ``root_part``
      cannot be used with ``root_uuid`` - to do so causes a JobError.

Device configuration
====================

Media settings are per-device, based on the capability of the device type.
An individual devices of a specified type *may* have exactly one of the
available slots populated on any one interface. These individual devices
would set UUID-required: False for that interface. e.g. A panda has two
USB host slots. For each panda, if both slots are occupied, specify
``UUID-required: True`` in the device configuration. If only one is
occupied, specify ``UUID-required: False``. If none are occupied, comment
out or remove the entire ``usb`` interface section in the configuration
for that one device. List each specific device which is available as
media on that interface using a humand-usable string, e.g. a Sandisk
Ultra usb stick with a UUID of ``usb-SanDisk_Ultra_20060775320F43006019-0:0``
could simply be called ``SanDisk_Ultra``. Ensure that this label is
unique for each device on the same interface. Jobs will specify this label
in order to look up the actual UUID, allowing physical media to be
replaced with an equivalent device without changing the job submission data.

The device configuration should always include the UUID for all media on
each supported interface, even if ``UUID-required`` is False. The UUID is
the recommended way to specify the media, even when not strictly required.
Record the symlink name (without the path) for the top level device in
``/dev/disk/by-id/`` for the media concerned, i.e. the symlink pointing
at ``../sda`` not the symlink(s) pointing at individual partitions. The
UUID should be **quoted** to ensure that the YAML can be parsed correctly.
Also include the ``device_id`` which is the bootloader view of the same
device on this interface.

.. code-block:: yaml

 device_type: cubietruck
 commands:
  connect: telnet localhost 6000
 media:
   usb:  # bootloader interface name
     UUID-required: True  # cubie1 is pretending to have two usb media attached
     SanDisk_Ultra:
       uuid: "usb-SanDisk_Ultra_20060775320F43006019-0:0"  # /dev/disk/by-id/
       device_id: 0  # the bootloader device id for this media on the 'usb' interface

There is no reasonable way for the device configuration to specify the
device node as it may depend on how the deployed kernel or image is configured.
When this is used, the job submission must contain this data.

Deploy commands
---------------

This is an example block - the actual data values here are known not to
work as the ``deploy`` step is for a panda but the ``boot`` step in the
next example comes from a working cubietruck job.

This example uses a device configuration where ``UUID-required`` is True.

For simplicity, this example also omits the initial deployment and boot,
at the start of this block, the device is already running a kernel with
a ramdisk or rootfs which provides enough support to complete this second
deployment.

.. code-block:: yaml

    # secondary media - use the first deploy to get to a system which can deploy the next
    # in testing, assumed to already be deployed
    - deploy:
        timeout:
          minutes: 10
        to: usb
        os: debian
        # not a real job, just used for unit tests
        compression: gz
        image: http://releases.linaro.org/12.02/ubuntu/leb-panda/panda-ubuntu-desktop.img.gz
        device: SanDisk_Ultra # needs to be exposed in the device-specific UI
        download: /usr/bin/wget


#. Ensure that the ``deploy`` action has sufficient time to download the
   **decompressed** image **and** write that image directly to the media
   using STDOUT. In the example, the deploy timeout has been set to ten
   minutes - in a test on the panda, the actual time required to write
   the specified image to a USB device was around 6 minutes.
#. Note the deployment strategy - ``to: usb``. This is a direct mapping
   to the kernel interface used to deploy and boot this image. The
   bootloader must also support reading files over this interface.
#. The compression method used by the specified image is explicitly set.
#. The image is downloaded and decompressed by the dispatcher, then made
   available to the device to retrieve and write to the specified media.
#. The device is specified as a label so that the correct UUID can be
   constructed from the device configuration data.
#. The download tool is specified as a full path which must exist inside
   the currently deployed system. This tool will be used to retrieve the
   decompressed image from the dispatcher and pass STDOUT to ``dd``. If
   the download tool is the default ``/usr/bin/wget``, LAVA will add the
   following options:
   ``--no-check-certificate --no-proxy --connect-timeout=30 -S --progress=dot:giga -O -``
   If different download tools are required for particular images, these
   can be specified, however, if those tools require options, the writer
   can either ensure that a script exists in the image which wraps those
   options or file a bug to have the alternative tool options supported.

The kernel inside the initial deployment **MUST** support UUID when
deployed on a device where UUID is required, as it is this kernel which
needs to make ``/dev/disk/by-id/$path`` exist for ``dd`` to use.

Boot commands
-------------

.. code-block:: yaml

    - boot:
        method: u-boot
        commands: usb
        parameters:
          shutdown-message: "reboot: Restarting system"
        # these files are part of the image already deployed and are known to the test writer
        kernel: /boot/vmlinuz-3.16.0-4-armmp-lpae
        ramdisk: /boot/initrd.img-3.16.0-4-armmp-lpae.u-boot
        dtb: /boot/dtb-3.16.0-4-armmp-lpae'
        root_uuid: UUID=159d17cc-697c-4125-95a0-a3775e1deabe  # comes from the supplied image.
        boot_part: 1  # the partition on the media from which the bootloader can read the kernel, ramdisk & dtb
        type: bootz
        prompts:
          - 'linaro-test'
          - 'root@debian:~#'

The ``kernel`` and (if specified) the ``ramdisk`` and ``dtb`` paths are
the paths used by the bootloader to load the files in order to boot the
image deployed onto the secondary media. These are **not necessarily**
the same as the paths to the same files as they would appear inside the
image after booting, depending on whether any boot partition is mounted
at a particular mountpoint.

The ``root_uuid`` is the full option for the ``root=`` command to the
kernel, including the ``UUID=`` prefix.

The ``boot_part`` is the number of the partition from which the bootloader
can read the files to boot the image. This will be combined with the
device configuration interface name and device_id to create the command
to the bootloader, e.g.::

 "setenv loadfdt 'load usb 0:1 ${fdt_addr_r} /boot/dtb-3.16.0-4-armmp-lpae''",

The dispatcher does NOT analyze the incoming image - internal UUIDs
inside an image do not change as the refactored dispatcher does **not**
break up or relay the partitions. Therefore, the UUIDs of partitions inside
the image **MUST** be declared by the job submissions.

Connections
***********

A Connection is approximately equivalent to an automated login session
on the device or within a virtual machine hosted by a device.

Each connection needs to be supported by a TestJob, the output of each
connection is viewed as the output of that TestJob.

Typically, LAVA provides a serial connection to the board but other
connections can be supported, including SSH or USB. Each connection
method needs to be supported by software in LAVA, services within the
software running on the device and other infrastructure, e.g. a serial
console server.

.. note:: :ref:`defaults` - although ``serial`` is the traditional and
          previously default way of connecting to LAVA devices, it must be
          specified in the test job YAML.

The action which is responsible for creating the connection must
specify the connection method.

.. code-block:: yaml

    - boot:
        method: qemu
        media: tmpfs
        connection: serial
        failure_retry: 2
        prompts:
          - 'linaro-test'
          - 'root@debian:~#'

Support for particular connection methods needs to be implemented at a
device level, so the device also declares support for particular
connection methods.

.. code-block:: yaml

  deploy:
    methods:
      tftp
      ssh

  boot:
    connections:
      - serial
      - ssh
    methods:
      qemu:
    prompts:
      - 'linaro-test'
      - 'root@debian:~#'

Most devices are capable of supporting SSH connections, as long as:

* the device can be configured to raise a usable network interface
* the device is booted into a suitable software environment

.. note:: A failure to connect to a :ref:`primary_connection` would
   be an :ref:`infrastructure_error_exception`. A failure to connect
   to a :ref:`secondary_connection` is a :ref:`test_error_exception`.

USB connections are planned for Android support but are not yet
implemented.

Primary and Secondary connections
=================================

.. _primary_connection:

Primary connection
------------------

A Primary Connection is roughly equivalent to having a **root** SSH login
on a running machine. The device needs to be powered on, running an appropriate
daemon and with appropriate keys enabled for access. The TestJob for
a primary connection then skips the deploy stage and uses a boot method
to establish the connection. A device providing a primary connection
in LAVA only provides access to that connection via a single submitted
TestJob at a time - a Multinode job can make multiple connections but
other jobs will see the device as busy and not be able to start their
connections.

.. warning:: Primary connections can raise issues of
   :ref:`persistence` - the test writer is solely responsible for
   deleting any sensitive data copied, prepared or downloaded using a
   primary connection. Do not leave sensitive data for the next TestJob
   to find. Wherever possible, use primary connections with ``schroot``
   support so that each job is kept within a
   :ref:`temporary chroot <disposable_chroot>`, thereby also allowing
   more than one primary (schroot) connection on a single machine.

It is not necessarily required that a device offering a primary
connection is permanently powered on as the only connections being
made to the device are done via the scheduler which ensures that only
one TestJob can use any one device at a time. Depending on the amount
of time required to boot the device, it is supported to have a device
offering primary connections which is powered down between jobs.

A Primary Connection is established by the dispatcher and is therefore
constrained in the options which are available to the client requesting
the connection and the TestJob has **no** control over the arguments
passed to the daemon.

Primary connections also enable the authorization via the deployment
action and the overlay, where the connection method requires this.

Both Primary and Secondary connections are affected by :ref:`security`
issues due to the requirements of automation.

.. _secondary_connection:

Secondary connection
--------------------

Secondary connections are a way to have two simultaneous connections
to the same physical device, equivalent to two logins. Each connection
needs to be supported by a TestJob, so a Multinode group needs to be
created so that the output of each connection can be viewed as the output
of a single TestJob, just as if you had two terminals. The second
connection does not have to use the same connection method as the current
connection and many devices can only support secondary connections over
a network interface, for example SSH or telnet.

A Secondary Connection has a deploy step and the device is already
providing output over the primary connection, typically serial, before
the secondary connection is established. This is closer to having the
machine on your desk. The TestJob supplies the kernel and rootfs or
image to boot the device and can optionally use the secondary connection
to push other files to the device (for example, an ``ssh`` secondary
connection would use ``scp``).

A Secondary Connection can have control over the daemon via the deployment
using the primary connection. The client connection is still made by the
dispatcher.

Secondary connections require authorization to be configured, so the
deployment must specify the authorization method. This allows the
overlay for this deployment to contain a token (e.g. the ssh public key)
which will allow the connection to be made. The token will be added to
the overlay tarball alongside the directories containing the test
definitions.

.. code-block:: yaml

    - deploy:
        to: tmpfs
        authorize: ssh
        kernel: http://....
        nfsrootfs: http://...
        dtb: http://....

Certain deployment Actions (like SSH) will also copy the token to a
particular location (e.g. ``/root/.ssh/authorized_keys``) but test
writers can also add a run step which enables authorization for a
different user, if the test requires this.

.. note:: The ``/root/.ssh/authorized_keys`` file will be replaced
   when the LAVA overlay is unpacked, if it exists in the test image
   already. This is a security precaution (so that test images
   can be shared easily without allowing unexpected access). Hacking
   sessions append to this file after the overlay has been unpacked.

Deployment can also include delivering the LAVA overlay files, including
the LAVA test shell support scripts and the test definitions specified
by the submitter, to the **host** device to be executed over the
secondary connection. So for SSH, the secondary connection typically
has a test action defined and uses :file:`scp` to put the overlay into
place before connecting using :file:`ssh` and executing the tests. The
creation of the overlay is part of the deployment, the delivery of the
overlay is part of the boot process of the secondary connection, i.e.
deploy is passive, boot is active. To support this, use the Multinode
protocol on the host to declare the IP address of the host and communicate
that to the guest as part of the guest deployment. Then the guest
uses the data to copy the files and make the connection as part of the
boot action. See :ref:`writing_secondary_connection_jobs`.

.. _host_role:

Considerations with a secondary connection
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

#. The number of host devices
#. Which secondary connections connect to which host device

In LAVA, this is handled using the Multinode :term:`role` using the
following rules:

#. All connections declare a ``host_role`` which is the ``role`` label
   for the host device for that connection. e.g. if the connection has
   a declared role of ``client`` and declares a ``host_role`` of ``host``,
   then every ``client`` connection will be expected to be able to connect
   to the ``host`` device.
#. The TestJob for each connection with the same ``role`` will be started
   on a single dispatcher which is local to the device with the
   ``role`` matching the specified ``host_role``.
#. There is no guarantee that a connection will be possible to any other
   device in the multinode group other than devices assigned to a ``role``
   which matches the ``host_role`` requirement of the connection.

.. note:: The ``count`` of any ``role`` acting as the ``host_role``
   **must** be set to 1. Multiple roles can be defined, each set as a ``host_role``
   by at least one of the other roles, if more than one device in the Multinode group
   needs to host secondary connections in the one submission. Multiple connections
   can be made to devices of any one ``host_role``.

This allows for devices to be hosted in private networks where only a
local dispatcher can access the device, without requiring that all devices
are accessible (as root) from all dispatchers as that would require all
devices to be publicly accessible.

Both Primary and Secondary connections are affected by :ref:`security`
issues due to the requirements of automation.

The device providing a Secondary Connection is running a TestJob and
the deployment will be erased when the job completes.

.. note:: Avoid confusing ``host_role`` with
   :ref:`expect_role <lava_start>`. ``host_role`` is used by the
   scheduler to ensure that the job assignment operates correctly and
   does not affect the dispatcher or delayed start support. The two
   values may often have the same value with secondary connections but
   do not mean the same thing.

.. note:: Avoid using constrained resources (like ``dpkg`` or ``apt``)
   from multiple tests (unless you take care with synchronisation calls
   to ensure that each operation happens independently). Check through the
   test definitions for installation steps or direct calls to ``apt`` and
   change the test definitions.

Connections and hacking sessions
--------------------------------

A hacking session using a :ref:`secondary_connection` is the only
situation where the client is configurable by the user **and** the
daemon can be controlled by the test image. It is possible to adjust
the hacking session test definitions to use different commands and
options - as long as both daemon and client use compatible options.
As such, a hacking session user retains security over their private
keys at the cost of the loss of automation.

Hacking sessions can be used with primary or secondary connections,
depending on the use case.

.. warning:: Remember that in addition to issues related to the
             :ref:`persistence` of a primary connection device, hacking
             sessions on primary connections also have all of the issues
             of a shared access device - do not copy, prepare or download
             sensitive data when using a shared access device.

.. _primary_connection_devices:

Devices supporting Primary Connections
======================================

A device offering a primary connection needs a particular configuration
in the device dictionary table:

#. Only primary connection deployment methods defined in the
   ``deploy_methods`` parameter, e,g, ``ssh``.
#. Support in the device_type template to replace the list of deployment
   methods with the list supplied in the ``deploy_methods`` parameter.
#. No ``serial`` connection support in the ``boot`` connections list.
#. No ``methods`` in the boot parameters.

This prevents other jobs being submitted which would cause the device
to be rebooted or have a different deployment prepared. This can be
further enhanced with :term:`device tag` support.

.. _secondary_connection_devices:

Devices supporting Secondary Connections
========================================

There are fewer requirements of a device supporting secondary
connections:

#. Primary and Secondary connections are mutually exclusive, so one
   device should not serve primary and secondary. (This can be done for
   testing but the secondary connection then has the same
   :ref:`persistence` issues as the primary.)
#. The physical device must support the connection hardware requirements.
#. The test image deployed needs to install and run the software
   requirements of the connection, this would be a
   :ref:`job_error_exception`
#. The **options** supplied for the primary connection template are
   also used for secondary connections, with the exception that the
   destination of the connection is obtained at runtime via the
   lava-multinode protocol. These options can be changed by the admin
   and specify the identity file to use for the connection and turn
   off password authentication on the connection, for example.

SSH as the primary connection
-----------------------------

Certain devices can support SSH as the primary connection - the
filesystems on such devices are not erased at the end of a TestJob and
provide :ref:`persistence` for certain tasks. (This is the equivalent
of the dummy-ssh device in the old dispatcher.) These devices declare
this support in the device configuration:

.. code-block:: yaml

  deploy:
    # primary connection device has only connections as deployment methods
    methods:
      ssh
  boot:
    connections:  # not serial
      - ssh

TestJobs then use SSH as a boot method which simply acts as a login to
establish a connection:

.. code-block:: yaml

    - deploy:
        to: ssh
        os: debian

    - boot:
        method: ssh
        connection: ssh
        failure_retry: 2
        prompts:
          - 'linaro-test'
          - 'root@debian:~#'

The ``deploy`` action in this case simply prepares the LAVA overlay
containing the test shell definitions and copies those to a
pre-determined location on the device. This location will be removed
at the end of the TestJob. The ``os`` parameter is specified so that
any LAVA overlay scripts are able to pick up the correct shell,
package manager and other deployment data items in order to run the
lava test shell definitions.

.. _security:

Security
--------

A primary SSH connection from the dispatcher needs to be controlled through
the device configuration, allowing the use of a private SSH key which
is at least hidden from test writers. (:ref:`essential_components`).

The key is declared as a path on the dispatcher, so is device-specific.
Devices on the same dispatcher can share the same key or may have a
unique key - all keys still need to not have any passphrase - as long
as all devices supported by the SSH host have the relevant keys
configured as authorized for login as root. [#admin1]_

.. [#admin1] Securing such private keys when the admin process is managed
   in a public VCS is left as an exercise for the admin teams.

LAVA provides a default (completely insecure) private key which can be
used for these connections. This key is installed within lava-dispatcher
and is readable by anyone inspecting the lava-dispatcher codebase in git.
(This has not been changed in the refactoring.)

It is conceivable that a test image could be suitably configured before
being submitted to LAVA, with a private key included inside a second job
which deploys normally and executes the connection **instead** of
running a test definition. However, anyone with access to the test image
would still be able to obtain the private key. Keys generated on a per
job basis would still be open for the lifetime of the test job itself,
up to the job timeout specified. Whilst this could provide test writers
with the ability to control the options and commands used to create the
connection, any additional security is minimal and support for this has
not been implemented, yet.

See also the :ref:`host_role` for information on how access to devices
is managed.

.. _persistence:

Persistence
-----------

Devices supporting primary SSH connections have persistent deployments
and this has implications, some positive, some negative - depending on
your use case.

#. **Fixed OS** - the operating system (OS) you get is the OS of the
   device and this **must not** be changed or upgraded.
#. **Package interference** - if another user installs a conflicting
   package, your test can **fail**.
#. **Process interference** - another process could restart (or crash)
   a daemon upon which your test relies, so your test will **fail**.
#. **Contention** - another job could obtain a lock on a constrained
   resource, e.g. ``dpkg`` or ``apt``, causing your test to **fail**.
#. **Reusable scripts** - scripts and utilities your test leaves behind
   can be reused (or can interfere) with subsequent tests.
#. **Lack of reproducibility** - an artifact from a previous test can
   make it impossible to rely on the results of a subsquent test, leading
   to wasted effort with false positives and false negatives.
#. **Maintenance** - using persistent filesystems in a test action
   results in the overlay files being left in that filesystem. Depending
   on the size of the test definition repositories, this could result in
   an inevitable increase in used storage becoming a problem on the machine
   hosting the persistent location. Changes made by the test action can also
   require intermittent maintenance of the persistent location.

Only use persistent deployments when essential and **always** take
great care to avoid interfering with other tests. Users who deliberately
or frequently interfere with other tests can have their submit privilege
revoked.

See :ref:`disposable_chroot` for a solution to some of these issues but
the choice of operating system (and the versions of that OS available)
within the chroot is down to the lab admins, not the test writer. The
principal way to get full control over the deployment is to use a
:ref:`secondary_connection`.

.. _disposable_chroot:

Disposable chroot deployments
=============================

Some devices can support mechanisms like `LVM snapshots`_ which allow
for a self-contained environment to be unpacked for a single session
and then discarded at the end of the session. These deployments do not
suffer the same entanglement issues as simple SSH deployments and can
provide multiple environments, not just the OS installed on the SSH
host system.

This support is similar to how distributions can offer "porter boxes"
which allow upstream teams and community developers to debug platform
issues in a native environment. It also allows tests to be run on a
different operating system or different release of an operating system.
Unlike distribution "porter boxes", however, LAVA does not allow more
than one TestJob to have access to any one device at the same time.

A device supporting disposable chroots will typically follow the
configuration of :ref:`primary_connection_devices`. The device
will show as busy whenever a job is active, but although it **is**
possible to use a secondary connection as well, the deployment
methods of the device would have to disallow access to the media upon
which the chroots are installed or deployed or upon which the software
to manage the chroots is installed. e.g. a device offering disposable
chroots on SATA could offer ramdisk or NFS tests.

LAVA support for disposable chroots is implemented via ``schroot``
(forming the replacement for the dummy-schroot device in the old
dispatcher).

Typical device configuration:

.. code-block:: yaml

  deploy:
    # list of deployment methods which this device supports
    methods:
      ssh:
      schroot:
        - unstable
        - trusty
        - jessie
  boot:
    connections:
      - ssh

Optional device configuration allowing secondary connections:

.. code-block:: yaml

  deploy:
    # list of deployment methods which this device supports
    methods:
      tftp:
      ssh:
      schroot:
        - unstable
        - trusty
        - jessie
  boot:
    connections:
      - serial
      - ssh

The test job YAML would simply specify:

.. code-block:: yaml

    - deploy:
        to: ssh
        chroot: unstable
        os: debian

    - boot:
        method: ssh
        connection: ssh
        failure_retry: 2
        prompts:
          - 'linaro-test'
          - 'root@debian:~#'

.. note:: The OS still needs to be specified, LAVA
          :ref:`does not guess <keep_dispatcher_dumb>` based
          on the chroot name. There is nothing to stop an schroot
          being `named` ``testing`` but actually being upgraded or
          replaced with something else.

The deployment of an schroot involves unpacking the schroot into a
logical volume with LVM. It is an :ref:`infrastructure_error_exception`
if this step fails, for example if the volume group has insufficient
available space.

``schroot`` also supports directories and tarballs but LVM is recommended
as it avoids problems of :ref:`persistence`. See
the `schroot manpage <http://manpages.debian.org/cgi-bin/man.cgi?query=schroot&apropos=0&sektion=0&manpath=Debian+unstable+sid&format=html&locale=en>`_
for more information on ``schroot``.
A common way to create an ``schroot`` is to use tools packaged with
`sbuild`_ or you can `use debootstrap <https://wiki.debian.org/Schroot>`_.

.. _LVM Snapshots: https://www.debian-administration.org/article/410/A_simple_introduction_to_working_with_LVM
.. _schroot: https://tracker.debian.org/pkg/schroot
.. _sbuild: https://tracker.debian.org/pkg/sbuild

.. _using_secondary_connections:

Using secondary connections with VM groups
==========================================

One example of the use of a secondary connection is to launch a VM on
a device already running a test image. This allows the test writer to
control both the kernel on the bare metal and the kernel in the VM as
well as having a connection on the host machine and the guest virtual
machine.

The implementation of VMGroups created a role for a delayed start
Multinode job. This would allow one job to operate over serial, publish
the IP address, start an SSH server and signal the second job that a
connection is ready to be established. This may be useful for situations
where a debugging shell needs to be opened around a virtualisation
boundary.

There is an option for downloading or preparing the guest VM image on the
host device within a test shell, prior to the VM delayed start. Alternatively,
a deploy stage can be used which would copy a downloaded image from the
dispatcher to the host device.

Each connection is a different job in a multinode group so that the output
of each connection is tracked separately and can be monitored separately.

Sequence
--------
#. The host device is deployed with a test image and booted.
#. LAVA then manages the download of the files necessary to create
   the secondary connection.

     * e.g. for QEMU, this would be a bootable image file
#. LAVA also creates a suitable overlay containing the test definitions
   to be run inside the virtual machine.
#. The test image **must** start whatever servers are required to
   provide the secondary connections, e.g. ssh. It does not matter
   whether this is done using install steps in the test definition or
   pre-existing packages in the test image or manual setup. The server
   **must** be configured to allow the (insecure) LAVA automation SSH
   private key to login as authorized - this key is available in the
   ``/usr/lib/python2.7/dist-packages/lava_dispatcher/device/dynamic_vm_keys``
   directory when lava-dispatcher is installed or in the lava-dispatcher
   `git tree <https://git.linaro.org/lava/lava-dispatcher.git/tree/HEAD:/lava_dispatcher/device/dynamic_vm_keys>`_.
#. The test image on the host device starts a test definition over the
   existing (typically serial) connection. At this point, the image file
   and overlay for the guest VM are available **on the host** for the
   host device test definition to inspect, although only the image
   file should actually be modified.
#. The test definition includes a signal to the LAVA :ref:`multinode_api`
   which allows the VM to start. The signal includes an identifier for
   which VM to start, if there is more than one.
#. The second job in the multinode group waits until the signal is
   received from the coordinator. Upon receipt of the signal, the
   ``lava dispatch`` process running the second job will initiate the
   secondary connection to the host device, e.g. over SSH, using the
   specified private key. The connection is used to run a set of
   commands in the test image running on the host device. It is a
   TestError if any of these commands fail. The last of these commands
   **must** hold the connection open for as long as the test writer
   needs to execute the task inside the VM. Once those tasks are
   complete, the test definition running in the test image on the host
   device signals that the VM has completed.

The test writer is given full control over the commands issued inside the
test image on the host device, including those commands which are responsible
for launching the VM. The test writer is also responsible for making the
**overlay** available inside the VM. This could be by passing arguments
to the commands to mount the overlay alongside the VM or by unpacking
the overlay inside the VM image before calling QEMU. If set in the job
definition, the test writer can ask LAVA to unpack the overlay inside the
image file for the VM and this will be done on the host device before
the host device boots the test image - however, this will require an
extra boot of the host device, e.g. using the dynamic master support.

Basic use cases
---------------

Prebuilt files can be downloaded, kernel, ramdisk, dtb, rootfs or
complete image. These will be downloaded to the host device and the
paths to these files substituted into the commands issued to start the
VM, in the same way as with bootloader like u-boot. This provides support
for tests within the VM using standard, packaged tools. To simplify
these tests further, it is recommended to use NFS for the root
filesystem of the host device boot - it leads to a quicker deployment
as the files for the VM can be downloaded directly to the NFS share
by the dispatcher. Deployments of the host device system to secondary
media, e.g. SATA, require additional steps and the job will take
longer to get to a point where the VM can be started.

The final launch of the VM will occur using a shell script (which will
then be preserved in the results alongside the overlay), containing the
parsed commands.

Advanced use cases
------------------

It is possible to use a test shell to build files to be used when
launching the VM. This allows for a test shell to operate on the
host device, building, downloading or compiling whatever files are
necessary for the operation of the VM, directly controlled by the
test shell.

To avoid confusion and duplication, LAVA does not support downloading
some files via the dispatcher and some via the test shell. If there
are files needed for the test job which are not to be built or generated
within the test shell, the test shell will need to use ``wget`` or
``curl`` or some other tool present in the test image to obtain the
files. This also means that LAVA is not able to verify that such
URLs are correct during the validation of the job, so test writers need
to be aware that LAVA will not be able to fail a job early if the URL
is incorrect as would happen in the basic use case.

Any overlay containing the test definitions and LAVA test scripts which
are to be executed inside the VM after the VM has booted still needs to
be downloaded from the dispatcher. The URL of this overlay (a single
tarball containing all files in a self-contained directory) will be
injected into the test shell files on the host device, in a similar
way to how the :ref:`multinode_api` provides dynamic data from other
devices in the group.

The test writer is responsible for extracting this tarball so that it
is present or is bind mounted into the root directory of the VM so that
the scripts can be launched immediately after login.

The test shell needs to create the final shell script, just as the
basic use case does. This allows the dispatcher running the VM to connect
to the host device and use a common interface to launch the VM in each
use case.

LAVA initiates and controls the connection to the VM, using this script,
so that all output is tracked in the multinode job assigned to the VM.

Sample job definition for the VM job
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: yaml

 # second half of a new-style VM group job
 # each connection is a different job
 # even if only one physical device is actually powered up.
 device_type: kvm-arm
 job_name: wandboard-qemu
 timeouts:
   job:
     minutes: 15
   action:
     minutes: 5
 priority: medium
 target_group: asd243fdgdfhgf-45645hgf
 group_size: 2
 parameters:
   # the test definition on the host device manages how
   # the overlay is applied to the VM image.
   overlay: manual  # use automatic for LAVA to do the overlay
 # An ID appended to the signal to start this VM to distinguish
 # it from any other VMs which may start later or when this one
 # completes.
 vm_id: gdb_session

 actions:

  - boot:
     # as kvm-arm, this happens in a test image via
     # the other half of this multinode job
     timeout:
       minutes: 3
     # alternative to u-boot
     connection: ssh
     method: vm
     # any way to launch a vm
     commands:
       # full access to the commands to run on the other device
       - qemu-system-arm -hda {IMAGE}
     type: qemu
     prompts:
       - 'linaro-test'
       - 'root@debian:~#'

  - test:
     name: kvm-basic-singlenode
     timeout:
       minutes: 5
     definitions:
         - repository: git://git.linaro.org/qa/test.git
           from: git
           path: ubuntu/smoke-tests-basic.yaml
           name: smoke-tests


Device configuration design
***************************

Device configuration, as received by ``lava_dispatch`` has moved to YAML
and the database device configuration has moved to `Jinja2`_ templates.
This method has a much larger scope of possible methods, related to the
pipeline strategies as well as allowing simple overrides and reuse of
common device configuration stanzas.

There is no need for the device configuration to include the
hostname in the YAML as there is nothing on the dispatcher to check
against - the dispatcher uses the command line arguments and the
supplied device configuration. The configuration includes all the data
the dispatcher needs to be able to run the job on the device attached
to the specified ports.

The device type configuration on the dispatcher is replaced by a
device type template on the server which is used to generate the
YAML device configuration sent to the dispatcher.

Device Dictionary
=================

The normal admin flow for individual devices will be to make changes
to the :term:`device dictionary` of that device. In time, an editable
interface will exist within the admin interface. Initially, changes
to the dictionary are made from the command line with details being
available in a read-only view in the admin interface.

The device dictionary acts as a set of variables inside the template,
in a very similar manner to how Django handles HTML templates. In turn,
a device type template will extend a base template.

It is a bug in the template if a missing value causes a broken device
configuration to be generated. Values which are not included in the
specified template will be ignored.

Once the device dictionary has been populated, the scheduler can be
told that the device is a ``pipeline device`` in the admin interface.

.. note:: Several parts of this process still need helpers and tools
          or may give unexpected errors - there is a lot of ongoing
          work in this area.

Exporting an existing device dictionary
---------------------------------------

If the local instance has a working pipeline device called ``mypanda``,
the device dictionary can be exported as a `Jinja2 child template`_
which *extends* a device type jinja template::

 $ sudo lava-server manage device-dictionary --hostname mypanda --export
 {% extends 'panda.jinja2' %}
 {% set power_off_command = '/usr/bin/pduclient --daemon tweetypie --hostname pdu --command off --port 08' %}
 {% set hard_reset_command = '/usr/bin/pduclient --daemon tweetypie --hostname pdu --command reboot --port 08' %}
 {% set connection_command = 'telnet droopy 4001' %}
 {% set power_on_command = '/usr/bin/pduclient --daemon tweetypie --hostname pdu --command on --port 08' %}

This dictionary declares that the device inherits the rest of the device
configuration from the ``panda`` device type. Settings specific to this
one device are then specified.

.. _Jinja2 child template: http://jinja.pocoo.org/docs/dev/templates/#child-template

Reviewing an existing device dictionary
---------------------------------------

To populate the full configuration using the device dictionary and the
associated templates, use the ``review`` option::

 $ sudo lava-server manage device-dictionary --hostname mypanda --review

.. _Jinja2: http://jinja.pocoo.org/docs/dev/

Example device configuration review
-----------------------------------

.. code-block:: yaml

 device_type: beaglebone-black
 commands:
   connect: telnet localhost 6000
   hard_reset: /usr/bin/pduclient --daemon localhost --hostname pdu --command reboot --port 08
   power_off: /usr/bin/pduclient --daemon localhost --hostname pdu --command off --port 08
   power_on: /usr/bin/pduclient --daemon localhost --hostname pdu --command on --port 08

 parameters:
  bootm:
   kernel: '0x80200000'
   ramdisk: '0x81600000'
   dtb: '0x815f0000'
  bootz:
   kernel: '0x81000000'
   ramdisk: '0x82000000'
   dtb: '0x81f00000'

 actions:
  deploy:
    # list of deployment methods which this device supports
    methods:
      # - image # not ready yet
      - tftp

  boot:
    # list of boot methods which this device supports.
    methods:
      - u-boot:
          parameters:
            bootloader_prompt: U-Boot
            boot_message: Booting Linux
            send_char: False
            # interrupt: # character needed to interrupt u-boot, single whitespace by default
          # method specific stanza
          oe:
            commands:
            - setenv initrd_high '0xffffffff'
            - setenv fdt_high '0xffffffff'
            - setenv bootcmd 'fatload mmc 0:3 0x80200000 uImage; fatload mmc 0:3 0x815f0000 board.dtb;
              bootm 0x80200000 - 0x815f0000'
            - setenv bootargs 'console=ttyO0,115200n8 root=/dev/mmcblk0p5 rootwait ro'
            - boot
          nfs:
            commands:
            - setenv autoload no
            - setenv initrd_high '0xffffffff'
            - setenv fdt_high '0xffffffff'
            - setenv kernel_addr_r '{KERNEL_ADDR}'
            - setenv initrd_addr_r '{RAMDISK_ADDR}'
            - setenv fdt_addr_r '{DTB_ADDR}'
            - setenv loadkernel 'tftp ${kernel_addr_r} {KERNEL}'
            - setenv loadinitrd 'tftp ${initrd_addr_r} {RAMDISK}; setenv initrd_size ${filesize}'
            - setenv loadfdt 'tftp ${fdt_addr_r} {DTB}'
            # this could be a pycharm bug or a YAML problem with colons. Use &#58; for now.
            # alternatively, construct the nfsroot argument from values.
            - setenv nfsargs 'setenv bootargs console=ttyO0,115200n8 root=/dev/nfs rw nfsroot={SERVER_IP}&#58;{NFSROOTFS},tcp,hard,intr ip=dhcp'
            - setenv bootcmd 'dhcp; setenv serverip {SERVER_IP}; run loadkernel; run loadinitrd; run loadfdt; run nfsargs; {BOOTX}'
            - boot
          ramdisk:
            commands:
            - setenv autoload no
            - setenv initrd_high '0xffffffff'
            - setenv fdt_high '0xffffffff'
            - setenv kernel_addr_r '{KERNEL_ADDR}'
            - setenv initrd_addr_r '{RAMDISK_ADDR}'
            - setenv fdt_addr_r '{DTB_ADDR}'
            - setenv loadkernel 'tftp ${kernel_addr_r} {KERNEL}'
            - setenv loadinitrd 'tftp ${initrd_addr_r} {RAMDISK}; setenv initrd_size ${filesize}'
            - setenv loadfdt 'tftp ${fdt_addr_r} {DTB}'
            - setenv bootargs 'console=ttyO0,115200n8 root=/dev/ram0 ip=dhcp'
            - setenv bootcmd 'dhcp; setenv serverip {SERVER_IP}; run loadkernel; run loadinitrd; run loadfdt; {BOOTX}'
            - boot

Importing configuration using a known template
----------------------------------------------

To add or update the device dictionary, a file using the same syntax as
the ``export`` content can be imported into the database::

 $ sudo lava-server manage device-dictionary --hostname mypanda --import mypanda.yaml

(The file extension is unnecessary and the content is not actually YAML
but will be rendered as YAML when the templates are used.)

Creating a new template
-----------------------

Start with the ``base.yaml`` template and use the structure of that
template to ensure that your template remains valid YAML.

Start with a complete device configuration (in YAML) which works on the
``lava-dispatch`` command line, then iterate over changes in the template
to produce the same output.

.. note:: A helper is being planned for this step.

Running lava-dispatch directly
==============================

``lava-dispatch`` only accepts a YAML file for pipeline jobs - the old
behaviour of looking up the file based on the device hostname has been
dropped. The absolute or relative path to the YAML file must be
specified to the ``--target`` option. ``--output-dir`` must also be
specified::

 sudo lava-dispatch --target devices/fred.conf panda-ramdisk.yaml --output-dir=/tmp/test

