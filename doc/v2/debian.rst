.. index:: developers, debian development, lava on debian

.. _lava_on_debian:

Developing LAVA on Debian
#########################

LAVA no longer supports development on Ubuntu.

Packages for LAVA are available for:

* Debian Stretch (stable) - with backports
* Debian Buster (testing)
* Debian Sid (unstable)

Packages will remain available for Debian Jessie (oldstable) with backports
until June 2018 as security support for Jessie will end. The last production
release with Jessie support was 2018.2. Developers need to use Debian Stretch
or Buster for development.

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

.. note:: The supported suite for LAVA development is now Stretch. The
   developer package build now defaults to expecting Stretch and
   therefore uses Python3 exclusively. Support for building Python2 has
   been removed, the ``master`` branch only builds Python3. See
   https://lists.lavasoftware.org/pipermail/lava-announce/2018-January/000046.html

The ``lava-dev`` package includes a helper script which is also present
in the source code in ``lava-server/share/``. The script requires a
normal Debian package build environment (i.e. ``dpkg-dev``) as well as
the build-dependencies of the package itself. The helper checks for
package dependencies using ``dpkg-checkbuilddeps`` which halts upon
failure with a message showing which packages need to be installed.

The helper needs to know the name of the package to build and to be
started from the directory containing the code for that package::

 $ /usr/share/lava-server/debian-dev-build.sh -p lava

From time to time, dependencies may need to vary between the current Debian
stable release and the unstable suite and the package building tools expect
to build for unstable. If you are building a package to update an instance
running a different suite, pass that suite using the ``-s`` option::

 $ ./share/debian-dev-build.sh -p lava -s stretch-backports

The packages will be built in a temporary directory using a version
string based on the current git tag and the time of the build. The
helper outputs the location of all the built packages at the end of a
successful build, ready for use with ``$ sudo dpkg -i
<path_to_dot_deb_file>``, repeated for every file or ``$ sudo debi -u
<path_to_lava_dot_changes_file>`` which will upgrade matching packages
which are already installed but skip ones which are not installed.
e.g.:

.. code-block:: none

 $ sudo dpkg -i /tmp/tmp.DCraOEYiPJ/lava-common_2018.7-15-g64824c402-1_all.deb
 $ sudo dpkg -i /tmp/tmp.DCraOEYiPJ/lava-dispatcher_2018.7-15-g64824c402-1_amd64.deb
 ...

or all in one command:

.. code-block:: none

 $ sudo debi -u /tmp/tmp.DCraOEYiPJ/lava_2018.7-15-g64824c402-1_amd64.changes

To install any package, including the developer build packages, the
corresponding package **must** already be installed at the current production
release version (or better), on the same machine. This ensures that all of the
runtime dependencies already exist on the system.

Use the ``-o`` option to set a build directory instead of the temporary
directory default.

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

The local version is built (using ``./version.py``) from these components:

* package name
* ``git describe``::

   $ git describe
   2018.7-35-gb022cde9

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
 $ git clone https://git.linaro.org/git/lava/lava.git
 $ cd lava
 $ /usr/share/lava-server/debian-dev-build.sh -p lava

``lava-dispatcher`` has architecture-dependent dependencies. By
default, the package is built for the native architecture and can only
be installed on that architecture. To build for a different
architecture, e.g. armhf, use::

 $ /usr/share/lava-server/debian-dev-build.sh -p lava -a armhf

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

.. index:: developer: python3 dependencies

.. _developer_python3:

Development using Python3
*************************

LAVA has moved to exclusive Python3 support as the final stage of the
migration to V2. See
<https://lists.lavasoftware.org/pipermail/lava-announce/2017-June/000032.html>`_

Both lava-server and lava-dispatcher only support running the unit tests with
Python3. **All** reviews **must** pass the unit tests when run with Python3.

Builds for Debian Jessie have ceased, support for Python2 has been dropped and
**only** Python3 is be supported.

Python3 dependencies include:

 python3-django (>= 1.8), python3-django-auth-ldap (>= 1.1.8),
 python3-django-restricted-resource (>= 2015.09),
 python3-django-tables2 (>=1.2), python3-docutils, python3-jinja2,
 python3-psycopg2, python3-simplejson,
 python3-voluptuous (>= 0.8.8), python3:any (>= 3.3.2-2~),
 python3-configobj, python3-magic, python3-netifaces (>=0.10.0),
 python3-nose, python3-pexpect (>= 4.2), python3-pyudev (>= 0.21),
 python3-requests, python3-serial, python3-setproctitle (>= 1.1.8),
 python3-tz, python3-yaml, python3-zmq, python3-guestfs (>= 1.32.7)

.. _quick_fixes:

Quick fixes and testing
***********************

The paths to execute LAVA python scripts have changed and developing LAVA based
on packages has a different workflow.

Modified files can be copied to the equivalent python path. The current LAVA
packages use python3, so the path is beneath
``/usr/lib/python3/dist-packages/`` with sudo::

 $ sudo cp <git-path> /usr/lib/python3/dist-packages/<git-path>

.. warning:: To fix failures in the Python3 unit tests, the **same** change
   will also need to be copied to ``/usr/lib/python3/dist-packages/``.

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
 Upgrading database lavapdu...
 Analyzing database lavapdu...
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
used to output the preferred format, depending on the arguments.

The dependencies **MUST** be installed in the specified suite of the
specified distribution for LAVA to work, so take care before pushing a
merge request to add package names to the support. Make sure your merge
request includes a change to the relevant requirement YAML files for
**all** supported distributions or the CI will fail.

Some distributions support ``Recommends`` level dependencies. These are
typically intended to be installed by ~90% of installations but give
flexibility for other use cases. ``Recommends`` are **not** handled by
``requires.py`` at all. The packages must be listed explicitly by the
maintainer of the packaging for the distribution. ``requires.py``
exists so that automated processes, like CI, can have a reliable but
minimal set of packages which must be installed for the specified
package to be installable.

.. note:: extra dependencies to enable unit tests and other CI actions
   are not covered by this support. However, these tend to change less
   often than the dependencies of the main source code.

``requires.py`` does not currently support dependencies based on the
architecture of the installation. (Currently, only ``Recommends``
includes architecture-sensitive packages.)

Outputting the requirements.txt format
======================================

Processes which need the version string can use the original output
format which mimics ``requirements.txt``::

    $ ./share/requires.py --package lava-server --distribution debian --suite stretch
    django-auth-ldap>=1.2.12
    PyYAML
    dateutil
    django-restricted-resource>=2016.8
    django-tables2>=1.14.2
    django>=1.10
    docutils>=0.6
    jinja2
    nose
    psycopg2
    pytz
    pyzmq
    requests
    simplejson
    voluptuous>=0.8.8

Outputting a list of binary package names
=========================================

::

    $ ./share/requires.py --package lava-server --distribution debian --suite stretch --names
    python3-django-auth-ldap
    python3-yaml
    python3-dateutil
    python3-django-restricted-resource
    python3-django-tables2
    python3-django
    python3-docutils
    python3-jinja2
    python3-nose
    python3-psycopg2
    python3-tz
    python3-zmq
    python3-requests
    python3-simplejson
    python3-voluptuous
    apache2
    adduser
    gunicorn3
    iproute2
    python3-setuptools
    libjs-excanvas
    libjs-jquery-cookie
    libjs-jquery
    libjs-jquery-ui
    libjs-jquery-watermark
    libjs-jquery-flot
    libjs-jquery-typeahead
    systemd-sysv
    postgresql
    postgresql-client
    postgresql-common
    lava-common

Outputting a single line of binary package names
================================================

This is intended to be passed directly to a package installer like
``apt-get`` together with the other required commands and options.

The caller determines the ``suite``, so to use with stretch-backports,
the ``-t stretch-backports`` option would also be added to the
other ``apt-get`` commands before appending the list of packages.

(Line breaks are added for readability only)::

    $ ./share/requires.py --package lava-server --distribution debian --suite stretch --names --inline
    lava-common postgresql-common postgresql-client postgresql systemd-sysv libjs-jquery-typeahead libjs-jquery-flot \
    libjs-jquery-watermark libjs-jquery-ui libjs-jquery libjs-jquery-cookie libjs-excanvas python3-setuptools iproute2 \
    gunicorn3 adduser apache2 python3-django-auth-ldap python3-yaml python3-dateutil python3-django-restricted-resource \
    python3-django-tables2 python3-django python3-docutils python3-jinja2 python3-nose python3-psycopg2 \
    python3-tz python3-zmq python3-requests python3-simplejson python3-voluptuous

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
repository, changes to the packaging can be tested by pushing to a public
branch and passing the ``-b`` option to :file:`debian-dev-build-sh`::

 $ /usr/share/lava-server/debian-dev-build.sh -p lava-server -b docs

.. _architecture_builds:

Building for other architectures
================================

``lava-server`` is the same for all architectures but ``lava-dispatcher`` has a
different set of dependencies depending on the build architecture. To build an
``armhf`` package of lava-dispatcher using the developer scripts, use::

 $ /usr/share/lava-server/debian-dev-build.sh -p lava-dispatcher -a armhf

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
<https://docs.djangoproject.com/en/1.9/ref/settings/#internal-ips>`_. Local
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

Keep in mind that django-debug-toolbar has some overhead on the webpage
generation and should only be used while debugging.

Django-debug-toolbar can be disabled, while not debugging, by changing the
value of ``USE_DEBUG_TOOLBAR`` in ``/etc/lava-server/settings.conf`` to
``false`` or by changing the ``̀DEBUG`` level in
``/etc/lava-server/settings.conf`` to ``DEBUG: false``.

Ensure the settings are reloaded by restarting both apache2 and django::

 sudo service lava-server-gunicorn restart
 sudo apache2ctl restart
