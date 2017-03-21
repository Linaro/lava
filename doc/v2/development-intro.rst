.. index:: jinja2, developer, developer guide, develop, contribute

.. _developer_guide:

LAVA developer guide
####################

.. _development_pre_requisites:

Pre-requisites to start with development
****************************************

LAVA is written in Python_, so you will need to know (or be willing to learn)
the language. Likewise, the web interface is a Django_ application so you will
need to use and debug Django if you need to modify the web interface. The
pipeline model uses YAML_ (so you'll need the `YAML Parser
<http://yaml-online-parser.appspot.com/?yaml=&type=json>`_) and Jinja2_. All
LAVA software is maintained in git_, as are many of the support scripts, test
definitions and job submissions. Some familiarity with Debian_ is going to be
useful, helper scripts are available when preparing packages based on your
modifications.

LAVA is complex and works to solve complex problems. This has implications
for how LAVA is developed, tested, deployed and used.

Other elements involved in LAVA development
===========================================

The Django backend used with LAVA is PostgreSQL_ and some
`postgres-specific support <http://www.postgresql.org/docs/9.5/static/rules-materializedviews.html>`_
is used. The LAVA UI has some use of Javascript_ and CSS_. LAVA also
uses ZMQ_ and XML-RPC_ and the LAVA documentation is written with RST_.

In addition, test jobs and device support can involve use of U-Boot_,
GuestFS_, ADB_, QEMU_, Grub_, SSH_ and a variety of other systems and tools to
access devices and debug test jobs.

.. _Python: http://www.python.org/
.. _Django: https://www.djangoproject.com/
.. _YAML: http://yaml.org/
.. _Jinja2: http://jinja.pocoo.org/docs/dev/
.. _git: http://www.git-scm.org/
.. _PostgreSQL: http://www.postgresql.org/
.. _Debian: https://www.debian.org/
.. _Javascript: https://www.javascript.com/
.. _CSS: https://www.w3.org/Style/CSS/Overview.en.html
.. _GuestFS: http://libguestfs.org/
.. _ZMQ: http://zeromq.org/
.. _XML-RPC: http://xmlrpc.scripting.com/
.. _ADB: http://developer.android.com/tools/help/adb.html
.. _QEMU: http://wiki.qemu.org/Main_Page
.. _Grub: https://www.gnu.org/software/grub/
.. _U-Boot: http://www.denx.de/wiki/U-Boot
.. _SSH: http://www.openssh.com/
.. _POSIX: http://www.opengroup.org/austin/papers/posix_faq.html

.. index:: templates as code, device-type template files

.. _developing_device_type_templates:

Developing using device-type templates
======================================

If you are an administrator, you may think the previous link sent you to the
wrong section. However, administrators need to understand how device-type
templates operate and how the template engine will use the template to be able
to make changes.

.. important:: Device type templates are more than configuration files - the
   templates are processed as source code at runtime. Anyone making changes to
   a device-type ``.jinja2`` template file **must** understand the basics of
   how to test templates using the same tools as developers.

Device type templates as code
-----------------------------

Jinja2_ provides a powerful templating engine. Templates in LAVA use several
standard programming concepts:

* Conditional Logic

* Inheritance

* Default values

In addition, LAVA templates need to **always** render to valid YAML. It is this
YAML which is sent to the worker as ``device.yaml``. The worker does not handle
the templates. All operations are done on the master.

Testing new device-type templates
---------------------------------

The simplest check is to render the new template to YAML and check that it
contains the expected commands. As with test job files, there are common YAML
errors which can block the use of new templates.

.. seealso:: :ref:`YAML syntax errors <writing_new_job_yaml>`

.. code-block:: shell

 lava-server manage device-dictionary --hostname <HOSTNAME> --review

A more rigorous test is to use the dedicated unit test which does **not**
require ``lava-server`` to be installed, i.e. it does not require a database to
be configured. This test can be run directly from a git checkout of
``lava-server`` with a few basic python packages installed (including
``python-jinja2``).

.. code-block:: shell

 $ python -m unittest -vcf lava_scheduler_app.tests.test_templates.TestTemplates.test_all_templates

Individual templates have their own unit tests to test for specific elements of
the rendered device configuration.

Most changes to device-type templates take effect **immediately** - as soon as
the file is changed in ``/etc/lava-server/dispatcher-config/device-types/`` the
next testjob for that device-type will use the output of that template. Always
test your templates locally **before** deploying the template to the master.
(Test jobs which have already started are not affected by template changes.)

Use version-control for device-type templates
---------------------------------------------

This cannot be stressed enough. **ALL admins** need to keep device-type
templates in some form of version control. The template files are code and
admins will need to be able to upgrade templates when packages are upgraded
**and** when devices need to implement new support.

Contribute device-type templates back upstream
----------------------------------------------

As code, device-type templates need to develop alongside the rest of the
codebase. The best way to maintain support is to :ref:`contribute_upstream` so
that new features can be tested against your templates and new releases can
automatically include updates to your templates.

.. _developer_workflow:

Developer workflows
===================

.. note:: LAVA is developed using Debian packaging to ensure that daemons and
   system-wide configuration is correctly updated with changes in the codebase.
   There is **no support for pypi or python virtual environments or installing
   directly from a git directory**. ``python-setuptools`` is used but only
   with ``sdist`` to create the tarballs to be used for the Debian packaging,
   not for ``install``. Some dependencies of LAVA are not available with pypi,
   for example ``python-guestfs``.

.. seealso:: :ref:`lava_on_debian` and a summary of the
  `Debian LAVA team activity <https://qa.debian.org/developer.php?email=pkg-linaro-lava-devel%40lists.alioth.debian.org>`_

Developers can update the installed code on their own systems manually (by
copying files into the system paths) and/or use symlinks where appropriate but
changes need to be tested in a system which is deployed using the
:ref:`dev_builds` before being proposed for review. All changes **must** also
pass **all** the unit tests, unless those tests are already allowed to be
skipped using unittest decorators.

Mixing the use of python code in ``/usr/local/lib`` and ``/usr/lib`` on a
single system is **known** to cause spurious errors and will only waste your
development time. Be very careful when copying files and when using symlinks.
If in doubt, remove ``/usr/local/lib/python*`` **and** ``~/.local/lib/python*``
then build a :ref:`local developer package <dev_builds>` and install it.

If your change introduces a dependency on a new python module, always ensure
that this module is available in Debian by `searching the Debian package lists
<https://www.debian.org/distrib/packages#search_packages>`_. If the module
exists but is not in the current stable release of Debian, it can be
*backported* but be aware that this will delay testing and acceptance of your
change. It is expressly **not acceptable** to add a dependency on a python
module which is only available using pypi or ``pip install``. Introducing such
a module to Debian can involve a large amount of work - :ref:`talk to us
<mailing_lists>` before spending time on code which relies on such modules or
which relies on newer versions of the modules than are currently available in
Debian testing.

.. seealso:: :ref:`quick_fixes` and :ref:`testing_pipeline_code`

.. _naming_conventions:

Naming conventions and LAVA V2 architecture
*******************************************

Certain terms used in LAVA V2 have specific meanings, please be consistent in
the use of the following terms:

**board**
  The physical hardware sitting in a rack or on a desk.

**connection**
  A means of communicating with a device, often using a serial port but can
  also be SSH_ or another way of obtaining a shell-type interactive interface.
  Connections will typically require a POSIX_ type shell.

**compatibility**
  An integer calculated by the master and separately by the worker to determine
  whether the worker is running older code than the master.

**device**
  In ``lava-server``, a device is a database object in LAVA which stores
  configuration, information and status relating to a single board. The device
  information can be represented in export formats like YAML for use when the
  database is not accessible.

  In ``lava-dispatcher``, the database is not accessible so the scheduler
  prepares a simple dictionary of values derived from the database and the
  template to provide the information about the device.

**device-type**
  A database object which collates similar devices into a group for purposes of
  scheduling. Devices of a single type are often the same vendor model but not
  all boards of the same model will necessarily be of the same device-type.

  .. seealso:: :ref:`device_types`

**dispatcher**
  The dispatcher software relates to the ``lava-dispatcher`` source package in
  git and in Debian. The dispatcher software for LAVA V2 can be installed
  without the server or the scheduler and a machine configured in this way is
  also called a *dispatcher*.

**dispatcher-master** or simply **master**
  A singleton process which starts and monitors test jobs running on one or
  more dispatchers by communicating with the slave using ZMQ.

**dynamic data** - the Action base class provides access to dynamic data stores
  which other actions can access. This provides the way for action classes to
  share information like temporary paths of downloaded and / or modified files
  and other data which is generated or calculated during the operation of the
  pipeline. Use ``self.set_common_data`` to set the namespace, key and value
  and ``self.get_common_data`` to retrieve the value using the namespace and
  the key.

**parameters**
  A static, read-only, dictionary of values and available for the job and the
  device. Parameters must not be modified by the codebase - use the
  ``common_data`` primitives of the Action base class to copy parameters and
  store the modified values as dynamic data.

**pipeline**
  The name for the design of LAVA V2, based on how the actions to be executed
  by the dispatcher are arranged in a unidirectional pipe. The contents of the
  pipe are validated before the job starts and the description of all elements
  in the pipe is retained for later reference.

  .. seealso:: :ref:`pipeline_construction`

**protocol**
  An API used by the python code inside ``lava-dispatcher`` to interact with
  external systems and daemons when a shell like environment is not supported.
  Protocols need to be supported within the python codebase and currently
  include multinode, LXC and vland.

**scheduler**
  A singleton process which is solely responsible for assigning a device to a
  test job. The scheduler is common to LAVA V1 and LAVA V2 and performs checks
  on submission restrictions, device availability, device tags and schema
  compliance.

  .. seealso:: :term:`device tag`

**server**
  The server software relates to the ``lava-server`` source package in git and
  in Debian. It includes components from LAVA V1 and LAVA V2 covering the UI
  and the scheduler daemon.

**slave**
  A daemon running on each dispatcher machine which communicates with the
  dispatcher-master using ZMQ. The slave in LAVA V2 uses whatever device
  configuration the dispatcher-master provides.

**test job**
  A database object which is created for each submission and retains the logs
  and pipeline information generated when the test job executed on the device.

Updating online documentation
*****************************

LAVA online documentation is written with RST_ format. You can use the command
below to generate html format files for LAVA V2::

 $ cd lava-server/
 $ make -C doc/v2 clean
 $ make -C doc/v2 html
 $ firefox doc/v2/_build/html/index.html
 (or whatever browser you prefer)

We welcome contributions to improve the documentation. If you are considering
adding new features to LAVA or changing current behaviour, ensure that the
changes include updates for the documentation.

Wherever possible, all new sections of documentation should come with worked
examples.

* Add a testjob submission YAML file to ``doc/v2/examples/test-jobs``

* If the change relates to or includes particular test definitions to
  demonstrate the new support, add a test definition YAML file to
  ``doc/v2/examples/test-definitions``

* Use the `include options
  <http://docutils.sourceforge.net/docs/ref/rst/directives.html#include>`_
  supported in RST to quote snippets of the test job or test definition YAML,
  following the examples of the existing examples.

* Use comments **liberally** in the examples and link to existing terms and
  sections.

* Read the comments in the ``doc/v2/index.rst`` file if you are adding new
  pages or altering section headings.

.. _RST: http://sphinx-doc.org/rest.html

.. _developer_code_locations:

Code locations
**************

The ongoing migration complicates some of the workflow when it comes to finding
all of the V2 code. When the V1 code is removed, the organisation of the code
will be tidied up.

* **lava-server** includes the ``lava_scheduler_app``, ``lava_results_app``,
  ``lava_server``, ``lava`` and ``linaro_django_xmlrpc`` components of LAVA V2.

* **lava-dispatcher** includes the ``lava_dispatcher`` and ``lava_test_shell``
  components. All LAVA V2 dispatcher code lives in
  ``lava_dispatcher/pipeline``. Some ``lava_test_shell`` scripts remain in the
  top level ``lava_test_shell`` directory with overrides in
  ``pipeline/lava_test_shell``.

There are also locations which provide device configurations to support the
unit tests. Only the Jinja2 support is used by the installed packages,

.. index:: setting compatibility

.. _compatibility_developer:

Compatibility
*************

.. seealso:: :ref:`compatibility_failures`

The compatibility mechanism allows the dispatcher-master daemon to prevent
issues that would arise if the worker is running older software. A job with a
lower compatibility may fail much, much later but this allows the job to fail
early. In future, support is to be added for re-queuing such jobs.

Developers need to take note that in the code, compatibility should reflect the
removal of support for particular elements, similar to handling a SONAME when
developing in C. When parts of the submission YAML are changed to no longer
support fields previously used, then the compatibility of the associated
strategy class must be raised to one more than the current highest
compatibility in the ``lava-dispatcher`` codebase. Compatibility does not need
to be changed when adding new classes or functionality. It remains a task for
the admins to ensure that the code is updated when new functionality is to be
used on a worker as this typically involves adding devices and other hardware.

Compatibility is calculated for each pipeline during parsing. Only if the
pipeline uses classes with the higher compatibility will the master prevent the
test job from executing. Therefore, test jobs using code which has not had a
compatibility change will continue to execute even if the worker is running
older software. Compatibility is not a guarantee that all workers are running
latest code, it exists to let jobs fail early when those specific jobs would
attempt to execute a code path which has been removed in the updated code.

.. _developer_jinja2_support:

Jinja2 support
==============

The Jinja2 templates can be found in ``lava_scheduler_app/tests/device-types``
in the ``lava-server`` codebase. The reason for this is that all template
changes are checked in the unit-tests. When the package is installed, the
``device-types`` directory is installed into
``/etc/lava-server/dispatcher-config/device-types/``. The contents of
``lava_scheduler_app/tests/devices`` is ignored by the packaging, these files
exist solely to support the unit tests.

.. seealso:: :ref:`unit_tests` and :ref:`testing_pipeline_code` for examples of
   how to run individual unit tests or all unit tests within a class or module.

Device dictionaries
===================

Individual instances will each have their own locations for the device
dictionaries of real devices. To allow the unit tests to run, some device
dictionaries are exported into ``lava_scheduler_app/tests/devices`` but there
is **no** guarantee that any of these would work with any real devices, even of
the declared :term:`device-type <device type>`.

For example, the Cambridge lab stores each :term:`device dictionary` in git at
https://git.linaro.org/lava/lava-lab.git and you can look at the configuration
of ``staging`` as a reference:
https://git.linaro.org/lava/lava-lab.git/tree/HEAD:/staging.validation.linaro.org/lava/pipeline/devices

Dispatcher device configurations
================================

The ``lava-dispatcher`` codebase also has local device configuration files in
order to support the dispatcher unit tests. These are **not** Jinja2 format,
these are YAML - the same YAML as would be sent to the dispatcher by the
relevant master after rendering the Jinja2 templates on that master. There is
**no** guarantee that any of the device-type or device configurations in the
``lava-dispatcher`` codebase would work with any real devices, even of the
declared :term:`device-type <device type>`.

.. _contribute_upstream:

Contributing Upstream
*********************

The best way to protect your investment on LAVA is to contribute your changes
back. This way you don't have to maintain the changes you need by yourself, and
you don't run the risk of LAVA changed in a way that is incompatible with your
changes.

Upstream uses Debian_, see :ref:`lava_on_debian` for more information.

.. _developer_planning:

Planning
========

The LAVA software team use Jira_ for long term planning for new features and
concepts. The JIRA instance used by LAVA is
https://projects.linaro.org/browse/LAVA and anonymous access is available for
anyone interested in LAVA to find out more about the future direction of LAVA.
Not all features are available at this stage but all LAVA issues are visible
individually. Not all issues will necesarily be delivered exactly as described,
many descriptions are written well in advance of delivery of the feature.

Many git commit messages within the LAVA codebase contain references to JIRA
issues as ``LAVA-123`` etc. All references like this can be appended to a basic
URL to find the details of that issue: ``https://projects.linaro.org/browse/``.
e.g. the addition of this section on JIRA relates to ``LAVA-735`` which can be
viewed as https://projects.linaro.org/browse/LAVA-735

Within JIRA, there is a hierarchy of issues. *EPIC* is the highest level to
group similar issues. *Stories* are each within a single EPIC and *sub-tasks*
can exist within a single Story.

This information is made available for interest and to make our development
process open to the community. If you have comments or questions about anything
visible within the LAVA project, please subscribe to one of the :ref:`mailing
lists <mailing_lists>` and ask your questions there. For bugs in the current
release, please continue to file bug reports using Bugzilla_.

Many stories contain comments linking directly to one or more gerrit reviews
related to that story. When the review is merged, the story will be marked as
resolved with a *Fix Version* matching the git tag of the release containing
the fix from the review.

.. _Jira: http://www.atlassian.com/jira-software
.. _Bugzilla: https://bugs.linaro.org/enter_bug.cgi?product=LAVA%20Framework

.. _community_contributions:

Community contributions
=======================

The LAVA software team use ``git review`` to manage contributions. Each review
is automatically tested against all the unit tests. **All reviews must pass all
unit tests** before being considered for merging into the master branch. The
contributor is responsible for making the changes necessary to allow the unit
tests to pass and to keep the review up to date with other changes in the
master branch.

To setup ``git review`` for the first time, install the package and setup the
local git configuration. (This can take a little time.)::

 $ apt -y install git-review
 $ cd lava-server/
 $ git review -s

.. important:: **All** changes need to support both Debian unstable
   **and** Debian stable - currently Jessie. This often includes multiple
   versions of django and other supporting packages. Automated unit tests are
   run on stable (with backports).

The master branch may be significantly ahead of the latest packages available
from Debian (unstable or stable backports) which are based on the release
branch. Use the :ref:`lava_repositories` and/or :ref:`developer_build_version`
to ensure that your instance is up to date with master.

.. seealso:: :ref:`lava_release_process`.

Patches, fixes and code
-----------------------

If you'd like to offer a patch (whether it is a bug fix, documentation update,
new feature or even a simple typo fix) it is best to follow this simple
check-list:

#. Clone the master branch of the correct project.
#. Create a new, clean, local branch based on master::

    $ git checkout -b fixupbranch

#. Add your code, change any existing files as needed.
#. Commit your changes on the local branch.
#. Checkout the master branch and ``git pull``
#. Checkout your existing local branch::

    $ git checkout fixupbranch

#. *rebase* your local branch against updated master::

    $ git rebase master

#. Fix any merge conficts. #. Send the patch to the `Linaro Code Review
   <https://review.linaro.org>`_ system (gerrit)::

    $ git review

#. If successful, you will get a link to a review.
#. Login to gerrit and add the ``lava-team`` as reviewers.
#. The unit tests will automatically start and you will be notified by email
   of the results and a link to the output which is useful if the tests fail.

.. seealso:: :ref:`development_workflow` for detailed information.

Contributing via your distribution
----------------------------------

You are welcome to use the bug tracker of your chosen distribution. The
maintainer for the packages in that distribution should :ref:`register` with
Linaro (or already be part of Linaro) to be able to forward bug reports and
patches into the upstream LAVA systems.

.. seealso:: https://www.debian.org/Bugs/Reporting

.. _register:

Register with Linaro as a Community contributor
-----------------------------------------------

If you, or anyone on your team, would like to register with Linaro directly,
this will allow you to file an upstream bug, submit code for review by the LAVA
team, etc. Register at the following url:

https://register.linaro.org/

If you are considering large changes, it is best to register and also to
subscribe to the :ref:`lava_devel` mailing list and talk to us on IRC::

 irc.freenode.net
 #linaro-lava

Contributing via GitHub
-----------------------

You can use GitHub to fork the LAVA packages and make pull requests

https://github.com/Linaro

It is worth sending an email to the :ref:`lava_devel` mailing list, so
that someone can migrate the pull request to a review.

.. note:: You will need to respond to comments on the review and the
   process of updating the review is **not** linked to the github pull request
   process.
