.. _deploy_action:

Deploy Action Reference
#######################

In general, the deployments do not modify the downloaded files. Where the LAVA
scripts and test definitions need to be added, these are first prepared as a
standalone tarball. Exceptions are described where relevant in each section.

Deploy action roles
*******************

* Download files required by the job to the dispatcher, decompressing only if
  requested.

* Prepare a LAVA overlay tarball containing the test definitions and LAVA API
  scripts, only if a :ref:`test_action` action is defined.

* Depending on the deployment, apply the LAVA overlay tarball to the
  deployment.

* Deploy does not support :ref:`repeat <repeats>` blocks but does support
  :ref:`failure_retry`.

.. _deploy_parameters:

Required parameters
*******************

Every deployment **must** specify a ``to`` parameter. This value is then used
to select the appropriate strategy class for the deployment which, in turn,
will require other parameters to provide the data on how to deploy to the
requested location. Additionally, all the required parameters are marked with
a *****

.. # comment - WARNING: respect the capitalization (or lack of such) in all the
   following sections as these are intended to exactly match the examples.
   Also, ignore the repetition - this is a *reference* guide like the glossary,
   it is not meant to be readable from top to bottom. Each section needs to
   standalone as a complete reference. Refer to other sections in other pages
   but avoid referring to other links in this document except when a direct
   relationship already exists through inheritance. There is a need for some
   custom CSS here, possibly using .. container:: RST syntax to assist with the
   sub-division of elements, possibly indenting.
   Also, watch for nesting levels. The links to sections are indented by
   **meaning**, even if the actual element is at a different level. This is to
   keep the guide consistent.
   Keep the docs for each element short and refer to the main body of docs for
   explanations. Ensure all information on options and possible values is in the
   reference guide.

Overlays
********

LAVA can insert user provided overlays into your images right after the download step.

In the url block, you can add a dictionary called `overlays` that will list the
overlays to add to the given resource.

.. code-block:: yaml

  - deploy:
      images:
        rootfs:
          url: http://example.com/rootfs.ext4.xz
          compression: xz
          format: ext4
          overlays:
            modules:
              url: http://example.com/modules.tar.xz
              compression: xz
              format: tar
              path: /

In order to insert overlay into an image, you should specify the image format.
Currently LAVA supports cpio (newc format) and ext4 images.

The overlays should be archived using tar. The path is relative to the root of
the image to update. This path is required.

Parameter List
**************

.. contents::
   :backlinks: top

.. include:: actions-deploy-to-docker.rsti
.. include:: actions-deploy-to-download.rsti
.. include:: actions-deploy-to-fastboot.rsti
.. include:: actions-deploy-to-fvp.rsti
.. include:: actions-deploy-to-isoinstaller.rsti
.. include:: actions-deploy-to-lxc.rsti
.. include:: actions-deploy-to-musca.rsti
.. include:: actions-deploy-to-nbd.rsti
.. include:: actions-deploy-to-recovery.rsti
.. include:: actions-deploy-to-sata.rsti
.. include:: actions-deploy-to-ssh.rsti
.. include:: actions-deploy-to-tftp.rsti
.. include:: actions-deploy-to-usb.rsti
.. include:: actions-deploy-to-vemsd.rsti
.. include:: actions-deploy-to-uuu.rsti

.. index:: deploy os

.. _deploy_os:

os *
****

The operating system of the image may be specified if the LAVA scripts
need to use the LAVA install helpers to install packages or identify
other defaults in the deployment data. However, this support is
**deprecated** for most use cases.

If ``os`` is used, the value does not have to be exact. A similar
operating system can be specified, based on how the test job operates.
If the test shell definition uses the deprecated LAVA install helpers
(by defining ``install:`` steps), then any ``os`` value which provides
the same installation tools will work. For example, operating systems
which are derivatives of Debian can use ``os: debian`` without needing
explicit support for each derivative because both will use ``apt`` and
``dpkg``.

.. seealso:: :ref:`less_reliance_on_install`

Test jobs which execute operating system installers **will** require
the deployment data for that installer, so ``os`` will need to be
specified in those test jobs. When the Lava install helpers are
removed, the elements of deployment data which are required for
installers will be retained.

Portable test definitions do not need to specify ``os`` at all, as long
as the test definition is not expected to run on a DUT running Android.

.. important:: Please read the notes on
   :ref:`test_definition_portability` - all test writers are strongly
   encouraged to drop all use of the LAVA install helpers as this
   support is **deprecated** and is expected to be removed by moving to
   support for an updated Lava-Test Test Definition.

* **Not all deployment methods support all types of operating system.**
* **Not all devices can support all operating systems.**

.. topic:: Allowed values

 * ``android`` : If your android test job executes a Lava Test Shell
   **on the DUT** then ``os: android`` will be needed so that the
   Android shell is used instead of ``/bin/sh``. Many AOSP images do
   not include ``busybox`` or other support for a shell on the DUT, so
   test jobs using those images drive the test from the LXC by using
   ``adb``. The deployment to the LXC does not need to specify ``os``
   as long as the test shell is **portable**.

 * ``ubuntu`` : **deprecated** - compatible with ``debian``.

 * ``debian``

 * ``lede``

 * ``fedora``

 * ``centos`` : **deprecated** - compatible with ``fedora``.

 * ``debian_installer``

 * ``centos_installer``

 * ``oe``
