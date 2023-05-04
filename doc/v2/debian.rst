.. index:: developers, debian development, lava on debian

.. _lava_on_debian:

Developing LAVA on Debian
#########################

LAVA no longer supports development on Ubuntu.

Packages for LAVA are available for:

* Debian Buster (testing)
* Debian Sid (unstable)

When using the packages to develop LAVA, there is a change to the workflow
compared to the old lava-deployment-tool buildouts.

.. note:: Changes to build dependencies between Debian versions can
   cause changes to the builds for each suite. Always ensure that you
   build packages for unstable using unstable and build packages for
   stable using a chroot or VM or other stable environment. If a
   package built on unstable does not install on stable, rebuild the
   same changes in a stable environment and re-install. Backports to
   stable in Debian are always built in a stable chroot or VM for this
   reason.

Why Debian?
***********

In the very early stages, LAVA was deployed using a custom script based
on PyPi and a lot of manual effort. This deployment tool frequently
failed in complex and unexpected ways. It become clear that this would
block successful and reliable deployment and upgrades of LAVA,
particularly in larger scale environments.

The main LAVA developer at the time was also a Debian developer with
the rights and familiarity with Debian to convert the deployment tool
into a packaged format which solved these issues.

LAVA is not inherently tied to Debian but following the route of
packaging LAVA in Debian solved many issues very easily. By using a
well supported and readily understood distribution as our base, many
users have been able to install and operate LAVA without needing direct
help from the developers. We have also gained a stable and reliable
platform for our internal CI which was an enormous aid during the V2
development cycle.

Whilst it might seem that lots of developer time is spent doing Debian
specific development, equivalent (and possibly more) work would be
needed to develop and support LAVA on any platform. Debian provides a
very large collection of packaged software, removing the need for us to
package and maintain the full stack which LAVA needs.

.. index:: lava on other distributions, distributions

.. _lava_on_other_distros:

Options for other distributions
********************************

Although LAVA is not inherently tied to the Debian distribution, there
would be some work involved to ensure that another method of
deploying LAVA would work well enough for the upstream LAVA team to
officially support that method.

On top of developing LAVA itself, full support of LAVA in Debian
includes:

#. Maintenance of packaging code, either upstream or in a public git
   repository.

#. Preparation of LAVA releases for inclusion into the distribution.

#. Rights to upload LAVA releases to the distribution and access
   within the distribution to apply local patches, upload security
   fixes and provide for backporting newer dependencies to maintain
   support for existing releases.

#. Maintenance of a LAVA lab using this distribution and running CI
   on LAVA devices. (This is to ensure that the functionality of LAVA
   is being tested on this distribution. It would be very useful, for
   example. for such a lab to participate in functional testing of LAVA
   upstream.)

#. Sufficient involvement in the distribution and familiarity with
   the distribution release process to provide full support for both
   installing new instances and smoothly upgrading established
   instances to each new release of the distribution.

   This includes planning ahead to ensure that new dependencies are
   packaged for the distribution in time for the next distribution
   release.

#. Maintenance of LAVA releases within the distribution across more
   than one distribution release cycle, at the same time.

   This is to ensure that users have continuity of support and can
   choose when to migrate the base operating system of their labs.

#. Involvement on IRC and mailing lists to promptly support users
   experiencing problems with using LAVA on the distribution.

#. Maintenance of the LAVA documentation covering how to use LAVA on
   the distribution.

#. Triage and fixing of issues in LAVA which are specific to the
   distribution.

#. Discussion with the rest of LAVA Software Community Project
   development team around issues related to this distribution.

#. Use of all available tools within the distribution to anticipate
   problems. Where possible, implementation of fixes before users are
   affected.

#. Maintenance of dependencies using ``./share/requires.py`` to enable
   automated testing. This includes testing the versions of specific
   dependencies and ensuring that the minimum version is available in
   all supported releases of the distribution.

#. Maintenance of scripts which build Docker images for and using that
   distribution, including publishing such images. These images will be
   required to support the internal CI.

#. Maintenance of upstream LAVA CI using that distribution in Docker to
   run the unit tests as well as build and test the packaging of LAVA
   for that distribution. This CI will involve, at a minimum, running
   such tests on the currently supported distribution release **and**
   the candidate for the next distribution release.

#. Maintenance of upstream CI using ``gitlab-runner`` on a machine
   running the relevant distribution so that CI jobs on the new
   distribution run in parallel to the CI jobs running on Debian.

#. Maintenance of LAVA tools and support scripts for running a LAVA lab
   using the distribution.

#. Consideration that support for the distribution may involve
   supporting more than one system architecture.

As an example from LAVA's history, support for migrations between
releases was the main problem for LAVA support of Ubuntu. It became
impossible to provide a smooth upgrade path from one Ubuntu LTS release
(14.04 Trusty) to the next LTS release (16.04 Xenial). LAVA needs to
provide long term stability to provide reliable CI whilst keeping up
with changes across supported distributions and tools. For the sake of
lab admin workload, support needs to concentrate on LTS or server level
releases rather than developer releases or interim updates. Even though
Ubuntu is closely related to Debian, the timing of Ubuntu releases made
it very difficult to manage complex transitions like the change from
Django 1.4 to 1.8 and this was also a concern for the transition to
Python3.

You may find that more than one person will be required to meet all
these criteria and to maintain that support across several releases of
the distribution. The current LAVA Software Community Project team does
not have enough resources to do this work for any distribution other
than Debian.

:ref:`Talk to us <mailing_lists>` before spending time on such work.

.. index:: developer: preparation, lava-dev

.. _developer_preparations:

Preparing for LAVA development
******************************

LAVA provides a ``lava-dev`` package which supplies all the dependencies which
are required :ref:`to build local LAVA packages <dev_builds>`. This package is
intended primarily for developers working on laptops and other systems where
a full desktop environment is already installed::

  $ sudo apt install lava-dev

If you want to build local packages on a headless box or a system with limited
space, you can trim the set of dependencies by pre-installing
``pinentry-curses`` instead of the default ``pinentry-gtk2``. QEMU is still
required and will bring in some X11 dependencies but these are minimal compared
to the full dependencies of ``pinentry-gtk2`` which is brought in via
``gnupg2``::

  $ sudo apt install pinentry-curses
  $ sudo apt-get --purge remove pinentry-gtk2
  $ sudo apt-get --purge autoremove
  $ sudo apt install lava-dev

.. seealso:: :ref:`unit_test_dependencies`

.. index:: developer-builds

.. _dev_builds:

Developer package build
***********************

.. seealso:: :ref:`developer_preparations` and
   :ref:`development_pre_requisites`

.. note:: The supported suite for LAVA development is now Buster. The
   developer package build now defaults to expecting Buster and
   therefore uses Python3 exclusively. Support for building Python2 has
   been removed, the ``master`` branch only builds Python3. See
   https://lists.lavasoftware.org/archives/list/lava-announce@lists.lavasoftware.org/thread/KWEPRA5P2LGVZ6WPIBWCYLC3G6TD5SN6/

The ``lava-dev`` package includes a helper script which is also present
in the source code in ``lava-server/share/``. The script requires a
normal Debian package build environment (i.e. ``dpkg-dev``), the
``git-buildpackage`` helper and the build-dependencies of the package
itself. The helper checks for package dependencies using
``dpkg-checkbuilddeps`` which halts upon failure with a message showing
which packages need to be installed.

Changes from 2018.10 onwards
============================

* the Debian packaging files are now included upstream, so merge
  requests can include changes to the packaging directly. The helper
  script converts the package to a "native" package to allow for
  unreleased changes.

* **ALL** local changes must be committed to a local branch before
  attempting a build - the helper will fail with an error if
  ``git ls-files -m -o --exclude-standard`` reports any output.

* Builds are executed in a temporary scratch branch called
  ``lavadevscratch`` which is based on the current local branch and
  which is deleted at the end of the operation. This is required so
  that the packaging can be temporarily switched to a developer build.

* The helper script no longer accepts the ``-p`` option, the name
  of the package is determined from the upstream Debian packaging.

* The helper script not longer accepts the ``-b`` option to change
  the packaging branch as the packaging is now part of the same
  branch as the build.

.. code-block:: none

 $ /usr/share/lava-server/debian-dev-build.sh

From time to time, dependencies may need to vary between the current Debian
stable release and the unstable suite and the package building tools expect
to build for unstable. If you are building a package to update an instance
running a different suite, pass that suite using the ``-s`` option::

 $ ./share/debian-dev-build.sh -s buster

By default, the packages will be built in the ``../build-area/``
directory, this can be changed with the ``-o`` option. Packages are
build using a version string based on the output of ``./lava_common/version.py``,
except that hyphens ``-`` are replaced with period ``.`` to comply with
the rules for a native Debian package. The helper script outputs the
relative location of all the files generated by the build at the end of
a successful build, ready for use with ``$ sudo dpkg -i
<path_to_dot_deb_file>``, repeated for every file or ``$ sudo debi -u
<path_to_lava_dot_changes_file>`` which will upgrade matching packages
which are already installed but skip ones which are not installed.
e.g.:

.. code-block:: none

 $ sudo dpkg -i ../build-area/lava-common_2018.7-15-g64824c402-1_all.deb
 $ sudo dpkg -i ../build-area/lava-dispatcher_2018.7-15-g64824c402-1_amd64.deb
 ...

or all in one command:

.. code-block:: none

 $ sudo debi -u ../build-area/lava_2018.7-15-g64824c402-1_amd64.changes

To install any package, including the developer build packages, the
corresponding package **must** already be installed at the current production
release version (or better), on the same machine. This ensures that all of the
runtime dependencies already exist on the system.

.. _devel_branches:

Which branch to use for changes
===============================

Any and all changes for inclusion into a future release need to be based on the
current git master branch and will need rebasing from time to time as master
moves ahead.

All testing of the LAVA source code is based on the relevant master branch
which is then merged into the staging branch for testing as a release
candidate. The final release involves merging staging into the release branch.
Git tags are based on the release branch.

When using existing git tags or the release branch, create a new local branch
and commit your changes to ensure that a :ref:`local version string
<local_version_strings>` is used.

There can also be new dependencies added by changes in master and
staging before those changes are merged into release or uploaded as
a production release. When these changes are merged into master, the
packaging will also be updated.

.. _local_version_strings:

Local version strings
=====================

The local version is built (using ``./lava_common/version.py``) from these components:

* package name
* ``git describe`` - (dashes replaced by dots)::

   $ ./lava_common/version.py
   2018.7.35.gb022cde9

The latest git hash is a reference to the latest commit. If you have
not committed local changes (e.g. you are on a local branch based on a
tag) then the short hash can be used to lookup the commit in the master
branch, omitting the ``g`` prefix, e.g.::

  https://git.lavasoftware.org/lava/lava/commit/b022cde9

.. _distribution_differences:

Distribution differences
========================

**Always** build packages on the suite you expect to use for installation.

Packages available from the :ref:`lava_repositories` are built on
the correct suite (using sbuild) using the `lava-buildd scripts
<https://git.linaro.org/lava/lava-buildd.git>`_.

.. _pep440: https://www.python.org/dev/peps/pep-0440/
.. _python-setuptools: https://tracker.debian.org/pkg/python-setuptools

Example
=======

The helper supports ``lava``::

 $ sudo apt install lava-dev
 $ git clone https://git.lavasoftware.org/lava/lava.git
 $ cd lava
 $ ./share/debian-dev-build.sh

``lava-dispatcher`` has architecture-dependent dependencies. By
default, the package is built for the native architecture and can only
be installed on that architecture. To build for a different
architecture, e.g. arm64, use::

 $ /usr/share/lava-server/debian-dev-build.sh -a arm64 -B

This does a *binary build*, so the source is not included, which allows
these builds to be included in a local repository, e.g. using
``reprepro``.

Helpers for other distributions may be added in due course. Patches
welcome.

.. _developer_build_version:

Developer build versions
========================

LAVA uses git tags and the developer build adds a suffix to the tag for
each local build - the suffix is formed from the output of ``git
describe``

.. seealso:: :ref:`local_version_strings` for information on how to
   look up the commit information from the version string.

From August 2015, LAVA uses git tags without a leading zero on the
month number, in accordance with PEP440, so the git tag will be
``2015.8`` instead of ``2015.07`` used for the previous release tag.

.. index:: developer: python3 dependencies, developer: requirements

.. _developer_python3:

Development using Python3
*************************

LAVA has moved to exclusive Python3 support as the final stage of the
migration to V2. See
https://lists.lavasoftware.org/archives/list/lava-announce@lists.lavasoftware.org/thread/6QEDKDIQ2GFEPK5SRIE36RV234NSLSB6/

Both lava-server and lava-dispatcher only support running the unit tests with
Python3. **All** reviews **must** pass the unit tests when run with Python3.

Builds for Debian Jessie have ceased, support for Python2 has been dropped and
**only** Python3 is be supported.

Python3 and other dependencies are tracked using files in
``share/requirements`` using the ``./share/requires.py`` script.
Required arguments are:

.. code-block:: none

  -d, --distribution    Name of a distribution directory in ./share/requirements
  -s, --suite           Name of a suite in the specified distribution directory
  -p, --package         A LAVA package name in the distribution and suite

Optional arguments are:

.. code-block:: none

  -n, --names           List the distribution package names
  -u, --unittests       Distribution package names for unittest support -
                        requires --names

.. code-block:: none

 ./share/requires.py --distribution debian --suite buster --package lava-dispatcher --names
 python3-configobj python3-guestfs python3-jinja2 python3-magic 
 python3-netifaces python3-pexpect python3-pyudev
 python3-requests python3-setproctitle python3-tz python3-yaml
 python3-zmq

.. seealso:: :ref:`developer_workflow` and :ref:`running_black`

.. _quick_fixes:

Quick fixes and testing
***********************

The paths to execute LAVA python scripts and run unit tests have
changed and developing LAVA based on packages has a different workflow.

Modified files can be copied to the equivalent python path. The current LAVA
packages use python3, so the path is beneath
``/usr/lib/python3/dist-packages/`` with sudo::

 $ sudo cp <git-path> /usr/lib/python3/dist-packages/<git-path>

Viewing changes
***************

Different actions are needed for local changes to take effect, depending on the
type of file(s) updated:

====================== ==============================================
templates/\*/\*.html     next browser refresh (F5/Ctrl-R)
device-types/\*.jinja2   next testjob submission
devices/\*.jinja2        next testjob submission
\*_app/\*.py             ``$ sudo apache2ctl restart``
====================== ==============================================

.. index:: postgres migration, migrate postgres

.. _migrating_postgresql_versions:

Migrating postgresql versions
*****************************

LAVA installs the ``postgresql`` package which installs the current default
version of postgresql. When this default changes in Debian, a second package
will be added to your system which will start with no actual data.

.. caution:: ``postgresql`` **will disable database access** during the
   migration and this will interfere with the running instance. There is
   typically no rush to do the migration, so this is usually a task for a
   scheduled maintenance window. Declare a time when all devices can be taken
   offline and put a replacement site in place of the apache configuration to
   prevent database access during the migration.

Determining the active cluster
==============================

The output of ``pg_lsclusters`` includes the port number of each cluster.
To ensure that the correct cluster is upgraded, check the ``LAVA_DB_PORT``
setting in ``/etc/lava-server/instance.conf`` for the current instance. If
multiple clusters are shown, ``postgresql`` will upgrade to the latest version,
so ensure that any intermediate clusters are also stopped before starting the
migration.

Performing the migration
========================

Debian gives a notice similar to this when a new version of postgres is
installed:

.. code-block:: none

 Default clusters and upgrading
 ------------------------------
 When installing a postgresql-X.Y package from scratch, a default
 cluster 'main' will automatically be created. This operation is
 equivalent to doing 'pg_createcluster X.Y main --start'.

 Due to this default cluster, an immediate attempt to upgrade an
 earlier 'main' cluster to a new version will fail and you need to
 remove the newer default cluster first. E. g., if you have
 postgresql-8.2 installed and want to upgrade to 8.3, you first install
 postgresql-8.3:

  apt install postgresql-8.3

 Then drop the default 8.3 cluster:

  pg_dropcluster 8.3 main --stop

 And then upgrade the 8.2 cluster to 8.3:

  pg_upgradecluster 8.2 main

.. note:: Upgrading a cluster combines ``pg_dump`` and ``pg_restore`` (making
          two copies of the database at one point). Ensure that you have enough
          available space on the disc, especially with a large database. If
          ``pg_upgradecluster`` is interrupted by the lack of disc space it will
          not harm the system and full rollback will be applied automatically.

See also
https://askubuntu.com/questions/66194/how-do-i-migrate-my-postgres-data-from-8-4-to-9-1

Check your existing clusters::

 $ sudo pg_lsclusters

Stop postgresql (stops both versions)::

 $ sudo service postgresql stop

Drop the **main** cluster of the **NEW** postgres as this is empty::

 $ sudo pg_dropcluster 9.4 main --stop

Postgresql knows which version is the current default, so just tell postgresql
which is the old version to migrate the data into the (empty) new one::

 $ sudo pg_upgradecluster 9.3 main
 Disabling connections to the old cluster during upgrade...
 Restarting old cluster with restricted connections...
 Creating new cluster 9.4/main ...
  config /etc/postgresql/9.4/main
  data   /var/lib/postgresql/9.4/main
  locale en_GB.UTF-8
  port   5433
 Disabling connections to the new cluster during upgrade...
 Roles, databases, schemas, ACLs...
 Fixing hardcoded library paths for stored procedures...
 Upgrading database postgres...
 Analyzing database postgres...
 Fixing hardcoded library paths for stored procedures...
 Upgrading database lavaserver...
 Analyzing database lavaserver...
 Fixing hardcoded library paths for stored procedures...
 Upgrading database devel...
 Analyzing database devel...
 Fixing hardcoded library paths for stored procedures...
 Upgrading database template1...
 Analyzing database template1...
 Re-enabling connections to the old cluster...
 Re-enabling connections to the new cluster...
 Copying old configuration files...
 Copying old start.conf...
 Copying old pg_ctl.conf...
 Stopping target cluster...
 Stopping old cluster...
 Disabling automatic startup of old cluster...
 Configuring old cluster to use a different port (5433)...
 Starting target cluster on the original port...
 Success. Please check that the upgraded cluster works. If it does,
 you can remove the old cluster with

  pg_dropcluster 9.3 main

Check that the instance is still running. Note that the port of the new
postgresql server will have been upgraded to the port used for the old
postgresql server automatically. Check that this is the case::

 $ grep port /etc/postgresql/9.4/main/postgresql.conf
 port = 5432

Drop the old cluster::

 $ sudo pg_dropcluster 9.3 main

Now the old database package can be removed::

 $ sudo apt remove postgresql-9.3

.. index:: dependency requirements

.. _dependency_requirements:

Dependency Requirements
***********************

LAVA needs to control and output the list of dependencies in a variety
of formats. Building Docker images and running unit tests in an LXC
need an updated list of binary package names suitable for the
distribution and suite of the LXC. Each needs to cope with dependencies
outside the specified suite, e.g. stable releases which need backports.
Building the LAVA Debian packages themselves also requires a properly
up to date list of dependencies - including minimum versions. Each set
of dependencies needs to be specific to each LAVA binary package -
``lava-server`` has different dependencies to ``lava-dispatcher`` and
``lava-common``.

LAVA has several dependencies which are not available via PyPi or pip
and the ``requirements.txt`` file is therefore misleading. However, the
format of this file is still useful in building the LAVA packages.

Therefore, LAVA has the ``./share/requires.py`` script which can be
used to output the preferred format, depending on the arguments. The
script is also included in the ``lava-dev`` package as
``/usr/share/lava-server/requires.py``.

The dependencies **MUST** be installed in the specified release of the
specified distribution for LAVA to work, so take care before pushing a
merge request to add package names to the support. Make sure your merge
request includes a change to the relevant requirement YAML files for
**all** supported distributions or the CI will fail.

.. seealso:: :ref:`developer_workflow`

Some distributions support ``Recommends`` level dependencies. These are
typically intended to be installed by ~90% of installations but give
flexibility for other use cases. ``Recommends`` are **not** handled by
``requires.py`` at all. The packages must be listed explicitly by the
maintainer of the packaging for the distribution. ``requires.py``
exists so that automated processes, like CI, can have a reliable but
minimal set of packages which must be installed for the specified
package to be installable. To use a minimal installation, each package
listed by `./share/requires.py`` can be installed without its
recommended packages using the ``apt install --no-install-recommends
<packages>`` syntax.

``requires.py`` does not currently support dependencies based on the
architecture of the installation. (Currently, only ``Recommends``
includes architecture-sensitive packages.)

Outputting the requirements.txt format
======================================

Processes which need the version string can use the original output
format which mimics ``requirements.txt``::

    $ ./share/requires.py --package lava-server --distribution debian --suite buster
    django>=1.10
    PyYAML
    docutils>=0.6
    jinja2
    psycopg2
    pytz
    pyzmq
    requests
    voluptuous>=0.8.8

Outputting a list of binary package names
=========================================

This is intended to be passed directly to a package installer like
``apt-get`` together with the other required commands and options.

The caller determines the ``suite``, so to use with buster-backports,
the ``-t buster-backports`` option would also be added to the
other ``apt-get`` commands before appending the list of packages.

(Line breaks are added for readability only):

.. code-block:: none

    $ ./share/requires.py --package lava-server --distribution debian --suite buster --names
    python3-django python3-yaml python3-docutils \
    python3-jinja2 python3-psycopg2 python3-tz python3-zmq python3-requests \
    python3-voluptuous

Adding packages needed for the unittests
========================================

Some packages are only required to allow the unittests to pass. To add
these packages, use the ``--unittest`` option, in combination with
``--names``. These packages need to be added to the installation as
well as the base list of packages using ``--names``.

::

 $ ./share/requires.py --package lava-server --distribution debian --suite unstable --names --unittest
 python3-pytest-django python3-pytest python3-pytest-cov

::

 $ ./share/requires.py --package lava-dispatcher --distribution debian --suite unstable --names --unittest
 pyocd-flashtool gdb-multiarch git schroot lxc img2simg simg2img u-boot-tools docker.io xnbd-server telnet qemu-system-x86 qemu-system-arm

.. index:: javascript

.. _javascript_handling:

Javascript handling
*******************

Javascript has particular issues in distributions, often the version of a
Javascript file is out of step with the version available in the distribution
or not packaged at all. ``lava-server`` embeds javascript files in the
``static/js`` directories and maintains a list of files which are replaced with
symlinks during a Debian package build. The list is in
:file:`share/javascript.yaml` and the replacement of matching files is done
using :file:`share/javascript.py`. Other distribution builds are invited to use
the same script or provide patches if the paths within the script need
modification.

After 2015.12 release, all of the .min.js files in the package are removed from
VCS and minified files are created at build time. Templates in the system use
only minified versions of the javascript files so after the release package
rebuild will be mandatory.

.. _javascript_security:

Javascript and security
=======================

The primary concern is security fixes. Distributions release with a particular
release of LAVA and may need to fix security problems in that release. If the
file is replaced by a symlink to an external package in the distribution, then
the security problem and fix migrate to that package. LAVA tracks these files
in :file:`share/javascript.yaml`. Files which only exist in LAVA or exist at a
different version to the one available in the distribution, need to be patched
within LAVA. Javascript files created by LAVA are packaged as editable source
code and patches to these files will take effect in LAVA after a simple restart
of apache and a clearing of any browser cache. Problems arise when the
javascript files in the LAVA source code have been minified_, resulting in a
:file:`.min.js` file which is **not** suitable for editing or patching.

The source code for the minified JS used in LAVA is provided in the LAVA source
code, alongside the minified version. **However**, there is a lack of suitable
tools to convert changes to the source file into a comparable minified file. If
these files need changes, the correct fix would be to patch the unminified
javascript and copy the modified file over the top of the minified version.
This loses the advantages of minification but gains the benefit of a known
security fix.

.. _javascript_maintenance:

Javascript maintenance
======================

Work is ongoing upstream to resolve the remaining minified javascript
files:

#. **Identify** the upstream location of all javascript not listed in
   :file:`share/javascript.yaml` and not written by LAVA, specify this location
   in a :file:`README` in the relevant :file:`js/` directory along with
   details, if any, of how a modified file can be minified or whether a
   modified file should simply replace the minified file.

#. **Replace** the use of the remaining minified JS where the change to
   unminified has a negligible or acceptable performance change. If no upstream
   can be identified, LAVA will need to take over maintenance of the javascript
   itself, at which point minified files will be dropped until other LAVA
   javascript can also be minified.

#. **Monitor** availability of packages for all javascript files not written by
   LAVA and add to the listing in :file:`share/javascript.yaml` when packages
   become available.

#. **Maintain** - only minify javascript written by LAVA **if** a suitable
   minify tool is available to be used during the build of the packages and to
   add such support to :file:`share/javascript.py` so that minification happens
   at the same point as replacement of embedded javascript with symlinks to
   externally provided files.

.. _minified: https://en.wikipedia.org/wiki/Minification_(programming)

.. _testing_packaging:

Packaging changes
=================

From time to time, there can be packaging changes required to handle changes in
the LAVA upstream codebase. If you have write access to the packaging
repository, changes to the packaging can be tested by pushing to your
fork of lava.git and making a local commit. Then build as normal::

 $ /usr/share/lava-server/debian-dev-build.sh

.. _architecture_builds:

Building for other architectures
================================

``lava-server`` is the same for all architectures but ``lava-dispatcher`` has a
different set of dependencies depending on the build architecture. To build an
``arm64`` package of lava-dispatcher using the developer scripts, use::

 $ /usr/share/lava-server/debian-dev-build.sh -a arm64 -B

.. _django_debug_toolbar:

Debugging Django issues
***********************

When trying to investigate LAVA web pages generation we advise you to use
`django-debug-toolbar <https://django-debug-toolbar.readthedocs.org>`_. This is
a Django application that provide more information on how the page was
rendered, including:

* SQL queries
* templates involved
* HTTP headers

For instance, the toolbar is a really helpful resource to debug the Django
:abbr:`ORM (Object Relational Model)`.

Installing
==========

On a Debian system, just run::

  $ apt-get install python-django-debug-toolbar

Configuration
=============

Once the ``python-django-debug-toolbar`` package is installed, the toolbar
needs to be enabled in the instance. Two settings are required in
``/etc/lava-server/settings.conf``

* ``"DEBUG": true,``
* ``"USE_DEBUG_TOOLBAR": true,``

.. note:: ``settings.conf`` is JSON syntax, so ensure that the previous
   line ends with a comma and that the resulting file validates as JSON.
   Use `JSONLINT <https://jsonlint.com>`_

The toolbar can be disabled without disabling django debug but django must be
in debug mode for the toolbar to be loaded at all.

Restart the ``django`` related services to complete the installation of the
toolbar::

 sudo service lava-server-gunicorn restart
 sudo apache2ctl restart

Installation can be checked using ``lava-server manage shell``::

 >>> from django.conf import settings
 >>> 'debug_toolbar' in settings.INSTALLED_APPS
 True

.. seealso:: :ref:`developer_access_to_django_shell`

In order to see the toolbar, you should also check the value of `INTERNAL_IPS
<https://docs.djangoproject.com/en/3.2/ref/settings/#internal-ips>`_. Local
addresses ``127.0.0.1`` and ``::1`` are enabled by default.

To add more addresses, set ``INTERNAL_IPS`` to a list of addresses in
``/etc/lava-server/settings.conf``, (JSON syntax) for example::

  "INTERNAL_IPS": ["192.168.0.5", "10.0.0.6"],

These value depends on your setup. But if you don't see the toolbar that's the
first think to look at.

Apache then needs access to django-debug-toolbar CSS and JS files::

  sudo su -
  cd /usr/share/lava-server/static/
  ln -s /usr/lib/python3/dist-packages/debug_toolbar/static/debug_toolbar .

In ``/etc/lava-server/settings.conf`` remove the reference to htdocs in
``STATICFILES_DIRS``. Django-debug-toolbar does check that all directories
listed in ``STATICFILES_DIRS`` exists. While this is only a leftover from
previous versions of LAVA installer that is not needed anymore.

Once the changes are complete, ensure the settings are loaded by restarting
both apache2 and django::

 sudo service lava-server-gunicorn restart
 sudo apache2ctl restart

Performance overhead
====================

Keep in mind that django-debug-toolbar has some overhead on the web page
generation and should only be used while debugging.

Django-debug-toolbar can be disabled, while not debugging, by changing the
value of ``USE_DEBUG_TOOLBAR`` in ``/etc/lava-server/settings.conf`` to
``false`` or by changing the ``̀DEBUG`` level in
``/etc/lava-server/settings.conf`` to ``DEBUG: false``.

Ensure the settings are reloaded by restarting both apache2 and django::

 sudo service lava-server-gunicorn restart
 sudo apache2ctl restart
