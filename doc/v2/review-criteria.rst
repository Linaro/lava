.. index:: developer: review criteria

.. _criteria:

LAVA review criteria
********************

These criteria are to help developers control the development of new
code. Any of these criteria can be cited in a code review as reasons
for a review to be improved.

.. _keep_dispatcher_dumb:

Keep the dispatcher dumb
========================

There is a temptation to make the dispatcher clever but this only
restricts the test writer from doing their own clever tests by hard
coding commands into the dispatcher codebase. If the dispatcher needs
some information about the test image, that information **must** be
retrieved from the job submission parameters, **not** by calculating in
the dispatcher or running commands inside the test image. Exceptions to
this are the metrics already calculated during download, like file size
and checksums. Any information about the test image which is permanent
within that image, e.g. the partition UUID strings or the network
interface list, can be identified by the process creating that image or
by a script which is run before the image is compressed and made
available for testing. If a test uses a tarball instead of an image,
the test **must** be explicit about the filesystem to use when
unpacking that tarball for use in the test as well as the size and
location of the partition to use.

LAVA will need to implement some safeguards for tests which still need
to deploy any test data to the media hosting the bootloader (e.g.
fastboot, SD card or UEFI) in order to avoid overwriting the bootloader
itself. Therefore, although SD card partitions remain available for
LAVA tests where no other media are supportable by the device, those
tests can **only** use tarballs and pre-defined partitions on the SD
card. The filesystem to use on those partitions needs to be specified
by the test writer.

.. _defaults:

Avoid defaults in dispatcher code
=================================

All constants and defaults are going to need an override somewhere for
some device or test, eventually. Code defensively and put constants
into the ``lava_common`` module to support modification or into one of
the base Jinja2 templates. Put defaults into the YAML, not the python
code. It is better to have an extra line in the device_type than a
string in the python code as this can later be extended to a device or
a job submission.

.. _fail_early:

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
AutoLogin is the *de facto* default for all images.

Another example is the assumption in various parts of LAVA that the
test image will raise a network interface and repeatedly calling
``ping`` on the assumption that the interface will appear, somehow,
eventually.

.. _black_box_deploy:

Treat the deployment as a black box
===================================

LAVA has claimed to do this for a long time but the dispatcher is now
pushing this further. Do not think of the LAVA scripts as an *overlay*,
despite the class names, the LAVA scripts are **extensions**. When a
test wants an image deployed, the LAVA extensions should be deployed
alongside the image and then mounted to create a ``/lava-$hostname/``
directory. Images for testing within LAVA are no longer broken up or
redeployed but **must** be deployed **intact**. This avoids LAVA
needing to know anything about issues like SELinux or specific
filesystems but may involve multiple images for systems like Android
where data may exist on different physical devices.

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
commands to be executed by the dispatcher are hardcoded into the
dispatcher python code with only limited support for overriding
parameters or specifying *tainted* user data.

Tests are prevented from requiring new software to be installed on any
dispatcher which is not already a dependency of ``lava-dispatcher``.
Issues arising from this need to be resolved using MultiNode.

Until such time as there is a general and reliable method of deploying
and testing new bootloaders within LAVA tests, the bootloader /
firmware installed by the lab admin is deemed sacrosanct and must not
be altered or replaced in a test job. However, bootloaders are
generally resilient to errors in the commands, so the commands given to
the bootloader remain accessible to test writers.

It is not practical to scan all test definitions for potentially
harmful commands. If a test inadvertently corrupts the SD card in such
a way that the bootloader is corrupted, that is an issue for the lab
admins to take up with the test submitter. If it is possible to detect
such events through the dispatcher code, an InfrastructureError
Exception should be raised so that a health check is triggered in
case the device needs to go offline for the problem to be fixed.

.. _give_test_writer_rope:

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

#. VM devices running on a :term:`DUT` do **not** need the command line
   to be coded within LAVA. There have already been bug reports on this
   issue.

:ref:`diagnostic_actions` report on the state of the device after some
kind of error. This reporting can include:

* The presence or absence of expected files (like ``/dev/disk/by-id/``
  or ``/proc/net/pnp``).

* Data about running processes or interfaces, e.g. ``ifconfig``

It is a mistake to attempt to calculate data about a test image -
instead, require that the information is provided and **diagnose** the
actual information if the attempt to use the specified information
fails.

.. _criteria_guidance:

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
   If ``/usr/bin/git`` does not exist, this is a validation error.
   There should be no circumstances where a tool required on the
   dispatcher cannot be identified during validation of the pipeline.

#. An error from running the command on the dispatcher with
   user-specified parameters is a JobError.

#. Where it is safe to do so, offer **overrides** for supportable
   commandline options.

The codebase itself will help identify how much control is handed over
to the test writer. ``self.run_command()`` is a dispatcher call and
needs to be protected. ``connection.sendline()`` is a deployment call
and does not need to be protected.
