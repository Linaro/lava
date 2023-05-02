.. _developer_guide:

Guide to development within LAVA
################################

.. index:: unit tests - dependencies

.. _unit_test_dependencies:

Dependencies required to run unit tests
***************************************

.. seealso:: :ref:`developer_preparations` and :ref:`building LAVA
   packages <testing_packaging>`.

To run the unit tests, a range of dependencies need to be installed::

 $ sudo apt -y install lava-dev

To reduce the number of unit tests which are skipped, a number of other
packages are listed as recommended by ``lava-dev`` and these should be
installed as well::

 $ sudo apt -y install lxc u-boot-tools tftpd-hpa telnet nfs-kernel-server img2simg simg2img

.. important:: For security reasons, each installation of
   ``lava-server`` sets the permissions of
   ``/etc/lava-server/instance.conf`` to only be readable by the
   ``lavaserver`` user and users in the ``lavaserver`` group.

   (Some older instances may have a different username for this user
   and group - check the value of ``LAVA_DB_USER`` in
   ``/etc/lava-server/instance.conf`` using sudo.)

   To run the unit tests, the user running the unit tests needs to be
   in the ``lavaserver`` group. For example::

    $ sudo adduser <username> lavaserver

.. index:: templates as code, device-type template files

.. _developing_device_type_templates:

Developing using device-type templates
**************************************

If you are an administrator, you may think the previous link sent you
to the wrong section. However, administrators need to understand how
device-type templates operate and how the template engine will use the
template to be able to make changes.

.. important:: Device type templates are more than configuration files
   - the templates are processed as source code at runtime. Anyone
   making changes to a device-type ``.jinja2`` template file **must**
   understand the basics of how to test templates using the same tools
   as developers.

Device type templates as code
=============================

Jinja2_ provides a powerful templating engine. Templates in LAVA use
several standard programming concepts:

.. _Jinja2: http://jinja.pocoo.org/docs/dev/

* Conditional Logic

* Inheritance

* Default values

In addition, LAVA templates need to **always** render to valid YAML. It
is this YAML which is sent to the worker as ``device.yaml``. The worker
does not handle the templates. All operations are done on the master.

.. _testing_new_devicetype_templates:

Testing new device-type templates
*********************************

The simplest check is to render the new template to YAML and check that
it contains the expected commands. As with test job files, there are
common YAML errors which can block the use of new templates.

.. seealso:: :ref:`YAML syntax errors <writing_new_job_yaml>`

.. code-block:: shell

 lava-server manage device-dictionary --hostname <HOSTNAME> --review

All templates are checked for basic syntax and output using:

.. code-block:: shell

 $ python3 -m unittest -vcf tests.lava_scheduler_app.test_base_templates.TestBaseTemplates.test_all_templates

A more rigorous test is to use the dedicated unit test which does
**not** require ``lava-server`` to be installed, i.e. it does not
require a database to be configured. This test can be run directly from
a git clone of ``lava-server`` with a few basic python packages
installed (including ``python-jinja2``).

Individual templates have their own unit tests to test for specific
elements of the rendered device configuration.

The number of unit tests and templates has increased, so there are
dedicated unit test files for particular types of template unit tests:

.. code-block:: shell

 $ python3 -m unittest -vcf tests.lava_scheduler_app.test_fastboot_templates

 $ python3 -m unittest -vcf tests.lava_scheduler_app.test_grub_templates

 $ python3 -m unittest -vcf tests.lava_scheduler_app.test_qemu_templates

 $ python3 -m unittest -vcf tests.lava_scheduler_app.test_uboot_templates

Most changes to device-type templates take effect **immediately** - as
soon as the file is changed in
``/etc/lava-server/dispatcher-config/device-types/`` the next testjob
for that device-type will use the output of that template. Always test
your templates locally **before** deploying the template to the master.
(Test jobs which have already started are not affected by template
changes.)

Use version-control for device-type templates
=============================================

This cannot be stressed enough. **ALL admins** need to keep device-type
templates in some form of version control. The template files are code
and admins will need to be able to upgrade templates when packages are
upgraded **and** when devices need to implement new support.

Contribute device-type templates back upstream
==============================================

As code, device-type templates need to develop alongside the rest of
the codebase. The best way to maintain support is to
:ref:`contribute_upstream` so that new features can be tested against
your templates and new releases can automatically include updates to
your templates.

Some individual device files exist in the codebase in
``lava_scheduler_app/tests/devices`` but these are only for use in the
existing unit tests. There is no need to contribute individual device
dictionaries unless there are new unit tests which use those device
dictionaries.

.. index:: developer workflow

.. _developer_workflow:

Developer workflows
*******************

.. note:: LAVA is developed using Debian packaging to ensure that
   daemons and system-wide configuration is correctly updated with
   changes in the codebase. There is **no official support for pypi or python
   virtual environments or installing directly from a git directory**.
   ``python-setuptools`` is used but only with ``sdist`` to create the
   tarballs to be used for the Debian packaging, not for ``install``.
   Some dependencies of LAVA are not available with pypi, for example
   ``python-guestfs`` would need installing using another method.

.. seealso:: :ref:`lava_on_debian` and a summary of the
  `Debian LAVA team activity <https://qa.debian.org/developer.php?email=pkg-linaro-lava-devel%40lists.alioth.debian.org>`_

Developers can update the installed code on their own systems manually
(by copying files into the system paths) and/or use symlinks where
appropriate but changes need to be tested in a system which is deployed
using the :ref:`dev_builds` before being proposed for review. All
changes **must** also pass **all** the unit tests, unless those tests
are already allowed to be skipped using unittest decorators.

Mixing the use of python code in ``/usr/local/lib`` and ``/usr/lib`` on
a single system is **known** to cause spurious errors and will only
waste your development time. Be very careful when copying files and
when using symlinks. If in doubt, remove ``/usr/local/lib/python*``
**and** ``~/.local/lib/python*`` then build a :ref:`local developer
package <dev_builds>` and install it.

If your change introduces a dependency on a new python module, always
ensure that this module is available in Debian by `searching the Debian
package lists
<https://www.debian.org/distrib/packages#search_packages>`_. If the
module exists but is not in the current stable release of Debian, it
can be *backported* but be aware that this will delay testing and
acceptance of your change. It is expressly **not acceptable** to add a
dependency on a python module which is only available using pypi or
``pip install``. Introducing such a module to Debian can involve a
large amount of work - :ref:`talk to us <mailing_lists>` before
spending time on code which relies on such modules or which relies on
newer versions of the modules than are currently available in Debian
testing.

The dependencies required by LAVA are tracked using the
``./share/requires.py`` script which is also available in the
``lava-dev`` package as ``/usr/share/lava-server/requires.py``.
Merge requests which need extra modules which already exist in Debian
can add the relevant information to the ``share/requirements/debian``
files.

.. note:: For the CI to pass, the extra module(s) **must** be available for
   stable and testing. Pay particular attention to the version available in
   buster and buster-backports. If a minimum version is required, this can be
   specified in the requirements, as long as that version or newer is available
   in buster-backports. :ref:`talk to us <mailing_lists>` if your change
   involves new files that may need changes in the packaging code. All CI tests
   must pass before any new code can be merged, including building working
   packages containing the new support.

.. seealso:: :ref:`developer_python3`, :ref:`quick_fixes` and
   :ref:`testing_pipeline_code`

.. index:: code locations

.. _developer_code_locations:

Code locations
**************

All the code for the ``lava-server`` and ``lava-dispatcher`` support
exists in the single LAVA repository:

https://git.lavasoftware.org/lava/lava

Includes:

* ``lava_scheduler_app``
* ``lava_results_app``
* ``lava_server``
* ``lava``
* ``lava_common``
* ``linaro_django_xmlrpc``
* ``lava_dispatcher``
* ``lava_test_shell``
* ``debian``

  .. seealso:: :ref:`developing_new_classes`

.. index:: setting compatibility

.. _compatibility_developer:

Compatibility
*************

.. seealso:: :ref:`compatibility_failures`

The compatibility mechanism allows the lava-master daemon to prevent
issues that would arise if the worker is running older software. A job
with a lower compatibility may fail much, much later but this allows
the job to fail early. In future, support is to be added for re-queuing
such jobs.

Developers need to take note that in the code, compatibility should
reflect the removal of support for particular elements, similar to
handling a SONAME when developing in C. When parts of the submission
YAML are changed to no longer support fields previously used, then the
compatibility of the associated strategy class must be raised to one
more than the current highest compatibility in the ``lava-dispatcher``
codebase. Compatibility does not need to be changed when adding new
classes or functionality. It remains a task for the admins to ensure
that the code is updated when new functionality is to be used on a
worker as this typically involves adding devices and other hardware.

Compatibility is calculated for each pipeline during parsing. Only if
the pipeline uses classes with the higher compatibility will the master
prevent the test job from executing. Therefore, test jobs using code
which has not had a compatibility change will continue to execute even
if the worker is running older software. Compatibility is not a
guarantee that all workers are running latest code, it exists to let
jobs fail early when those specific jobs would attempt to execute a
code path which has been removed in the updated code.

.. _developer_jinja2_support:

Jinja2 support
==============

The Jinja2 templates can be found in
``lava_scheduler_app/tests/device-types`` in the ``lava-server``
codebase. The reason for this is that all template changes are checked
in the unit-tests. When the package is installed, the ``device-types``
directory is installed into
``/etc/lava-server/dispatcher-config/device-types/``. The contents of
``lava_scheduler_app/tests/devices`` is ignored by the packaging, these
files exist solely to support the unit tests.

.. seealso:: :ref:`unit_tests` and :ref:`testing_pipeline_code` for
   examples of how to run individual unit tests or all unit tests
   within a class or module.

Device dictionaries
===================

Individual instances will each have their own locations for the device
dictionaries of real devices. To allow the unit tests to run, some
device dictionaries are exported into
``lava_scheduler_app/tests/devices`` but there is **no** guarantee that
any of these would work with any real devices, even of the declared
:term:`device-type <device type>`.

For example, the Cambridge lab stores each :term:`device dictionary` in
git at https://git.linaro.org/lava/lava-lab.git and you can look at the
configuration of ``staging`` as a reference:
https://git.linaro.org/lava/lava-lab.git/tree/staging.validation.linaro.org/master-configs/staging-master.lavalab/lava-server/dispatcher-config/devices

Device dictionaries can also be downloaded from any LAVA instance
using the :ref:`xml_rpc` call, without needing authentication:

.. code-block:: python

    server.scheduler.devices.get_dictionary(hostname)

Dispatcher device configurations
================================

The ``lava-dispatcher`` codebase also has local device configuration
files in order to support the dispatcher unit tests. These are **not**
Jinja2 format, these are YAML - the same YAML as would be sent to the
dispatcher by the relevant master after rendering the Jinja2 templates
on that master. There is **no** guarantee that any of the device-type
or device configurations in the ``lava-dispatcher`` codebase would work
with any real devices, even of the declared :term:`device-type <device
type>`.

.. index:: contribute upstream

.. _contribute_upstream:

Contributing Upstream
*********************

The best way to protect your investment on LAVA is to contribute your
changes back. This way you don't have to maintain the changes you need
by yourself, and you don't run the risk of LAVA changed in a way that
is incompatible with your changes.

Upstream uses Debian_, see :ref:`lava_on_debian` for more information.

.. _Debian: https://www.debian.org/

.. index:: development planning

.. _developer_planning:

Planning
========

The LAVA Software Community Project uses GitLab_ for all development
and planning for new features and concepts. Discussion happens on the
:ref:`mailing_lists`.

.. _GitLab: https://git.lavasoftware.org/

Many older git commit messages within the LAVA codebase contain
references to JIRA issues as ``LAVA-123`` etc., as the LAVA project
used to use Linaro's JIRA instance to track issues. All references
like this can be appended to a basic URL to find the details of that
issue: ``https://projects.linaro.org/browse/``. e.g. the addition of
this section on JIRA relates to ``LAVA-735`` which can be viewed as
https://projects.linaro.org/browse/LAVA-735

If you have comments or questions about anything visible within the
LAVA project, please subscribe to one of the :ref:`mailing lists
<mailing_lists>` and ask your questions there.

.. index:: bug reporting

.. _bug_reporting:

Report a Bug
============

The LAVA Software Community Project uses GitLab_ for all bugs, issues,
feature requests, enhancements and problem reports. For more general
questions and discussion, use the :ref:`mailing_lists`. It is often
useful to discuss the full details of the problem on the lava-users_
mailing list before creating an issue in GitLab.

.. note:: The old Bugzilla and JIRA systems are both deprecated and
          reporting bugs in the old Bugzilla system will not be tracked
          by the LAVA team.

.. _lava-users: https://lists.lavasoftware.org/mailman3/lists/lava-users.lists.lavasoftware.org/

.. index:: community contributions

.. _community_contributions:

Community contributions
=======================

The LAVA software team use GitLab_ to manage contributions. For
details, please read the :ref:`contribution_guide`

.. seealso:: :ref:`lava_release_process` and :ref:`lava_development`
   and :ref:`contribution_guide` for detailed information on running
   the unit tests and other static code analysis tools before
   submitting the review.

Contributing via your distribution
----------------------------------

You are welcome to use the bug tracker of your chosen distribution. The
maintainer for the packages in that distribution should have an account
on https://git.lavasoftware.org/lava/lava to be able to forward bug
reports and patches into the upstream LAVA systems.

.. seealso:: https://www.debian.org/Bugs/Reporting

Contributing via GitHub
-----------------------

GitHub has mirrors of the GitLab repository but merge requests need to
be run through the GitLab CI tests. This can be done by changing the
git remote of the GitHub branch and pushing to GitLab. GitHub users can
create GitLab accounts on https://git.lavasoftware.org using their
GitHub credentials.

.. seealso:: :ref:`lava_development`.
