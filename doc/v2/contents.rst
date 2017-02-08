Contents
########

The LAVA documentation is continually expanding and improving. This is the
overview to help you know where to look for particular help.

* :ref:`contents_first_steps_using` - if you are a new user of LAVA V2
  and looking to submit tests an an existing instance, start here.
* :ref:`contents_first_steps_installing` - if you are starting with a
  fresh installation or running your own instance, start here.
* :ref:`contents_lava_ci` - this section explains the design goals
  of LAVA and how to use it best as part of a complete CI system.
* :ref:`contents_writing_tests` - this guide takes you through how to
  design, write and debug the tests to be run using LAVA. Worked
  examples are included for a range of deployments and test methods.
* :ref:`contents_results` - LAVA provides a generic view of test
  results. This guide covers how to use those results directly, and
  also how to export results data from LAVA to make it more useful.
* :ref:`contents_admin_guide` - this guide steps through the complex
  task of administering a LAVA instance, from a single emulated device
  to a large test lab with dozens of devices.
* :ref:`contents_migration` - documentation to help users migrating a
  lab and its devices from LAVA V1 to V2.
* :ref:`contents_developer_guide` - LAVA is developed in the open, and
  contributions are welcome from the community. This guide introduces
  the code structure and design requirements as well as how to
  contribute patches for review.
* :ref:`contents_context_help` - some pages in the UI have a ``Help``
  link in the context-menu section at the top of the page. These pages
  are listed in this section for reference and easier navigation.
* :ref:`glossary` - descriptions of terms which have particular meanings inside
  LAVA.

.. toctree::
   :maxdepth: 1
   :hidden:

   glossary
   support
   self

.. _contents_first_steps_using:

First steps using LAVA V2
=========================

.. # Keep this toctree in line with the hidden one in index.rst
     - index.rst determines the Next Prev links, not this one.

.. toctree::
   :maxdepth: 1

   first_steps
   first-job
   explain_first_job
   lava-tool
   standard-test-jobs
   standard-qemu-jessie
   standard-qemu-kernel
   standard-armmp-ramdisk-bbb

.. _contents_first_steps_installing:

First steps installing LAVA V2
==============================

.. # Keep this toctree in line with the hidden one in index.rst
     - index.rst determines the Next Prev links, not this one.

.. toctree::
   :maxdepth: 1

   first-installation
   installing_on_debian
   authentication
   first-devices

.. _contents_lava_ci:

CI with LAVA
============

.. # Keep this toctree in line with the hidden one in index.rst
     - index.rst determines the Next Prev links, not this one.

.. toctree::
   :maxdepth: 1

   lava_ci

.. _contents_writing_tests:

Writing tests for LAVA
======================

.. # Keep this toctree in line with the hidden one in index.rst
     - index.rst determines the Next Prev links, not this one.

.. toctree::
   :maxdepth: 1

   developing-tests
   writing-tests
   timeouts
   test-repositories
   lava_test_shell
   publishing-artifacts
   healthchecks
   hacking-session
   qemu_options
   dispatcher-actions
   deploy-lxc
   multinode
   writing-multinode
   multinodeapi
   vland
   debugging
   pipeline-usecases

.. _contents_results:

Results in LAVA
===============

.. # Keep this toctree in line with the hidden one in index.rst
     - index.rst determines the Next Prev links, not this one.

.. toctree::
   :maxdepth: 1

   results-intro
   lava-queries-charts
   data-export
   user-notifications
   custom-result-handling
   tables

.. _contents_admin_guide:

LAVA administration guide
=========================

.. # Keep this toctree in line with the hidden one in index.rst
     - index.rst determines the Next Prev links, not this one.

.. toctree::
   :maxdepth: 1

   simple-admin
   admin-backups
   advanced-installation
   growing_your_lab
   pipeline-server
   pipeline-admin
   devicetypes
   device-capabilities
   hiddentypes
   bootimages
   pdudaemon
   admin-lxc-deploy
   nexus-deploy
   ipmi-pxe-deploy
   ipxe
   proxy
   hijack-user
   migrate-lava
   vland-admin
   pipeline-debug
   lava-tool-issues

.. _contents_developer_guide:

LAVA developer guide
====================

.. # Keep this toctree in line with the hidden one in index.rst
     - index.rst determines the Next Prev links, not this one.

.. toctree::
   :maxdepth: 1

   development-intro
   process
   development
   pipeline-design
   dispatcher-design
   dispatcher-format
   pipeline-schema
   dispatcher-testing
   debian
   packaging
   developer-example

.. _contents_migration:

Migrating to V2
===============

.. # Keep this toctree in line with the hidden one in index.rst
     - index.rst determines the Next Prev links, not this one.

.. toctree::
   :maxdepth: 1

   migration
   pipeline-writer
   migrating-admin-example

.. _contents_context_help:

Context help
============

.. # Keep this toctree in line with the hidden one in index.rst
     - index.rst determines the Next Prev links, not this one.

.. toctree::
   :maxdepth: 1

   other
