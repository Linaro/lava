.. index:: developers

.. _lava_on_debian:

Developing LAVA on Debian
#########################

LAVA no longer supports development on Ubuntu.
See :ref:`ubuntu_install`.

Packages for LAVA are available for:

* Debian Jessie (stable) - with backports
* Debian Stretch (testing)
* Debian Sid (unstable)

When using the packages to develop LAVA, there is a change to
the workflow compared to the old lava-deployment-tool buildouts.

.. note:: Changes to build dependencies between Debian unstable and
   Debian stable can cause changes to the builds for each suite. Always
   ensure that you build packages for unstable using unstable and build
   packages for stable using a chroot or VM or other stable environment.
   If a package built on unstable does not install on stable, rebuild
   the same changes in a stable environment and re-install. Backports to
   stable in Debian are always built in a stable chroot or VM for this
   reason.

.. index:: developer-builds

.. _dev_builds:

Developer package build
***********************

The ``lava-dev`` package includes a helper script which is also present
in the source code in ``lava-server/share/``. The script requires a normal
Debian package build environment (i.e. ``dpkg-dev``) as well as the
build-dependencies of the package itself. The helper checks for package
dependencies using ``dpkg-checkbuilddeps`` which halts upon failure with
a message showing which packages need to be installed.

The helper needs to know the name of the package to build and to be
started from the directory containing the code for that package::

 $ /usr/share/lava-server/debian-dev-build.sh -p lava-server

If you are building a package to be installed on Jessie, ensure that the
``backports`` packaging branch is used so that the packaging scripts
can allow for differences between unstable and jessie::

 $ /usr/share/lava-server/debian-dev-build.sh -p lava-server -b backports

The packages will be built in a temporary directory using a version string
based on the current git tag and the time of the build. The helper
outputs the location of all the built packages at the end of a successful
build, ready for use with ``$ sudo dpkg -i``.

.. note:: the helper does **not** install the packages for you, neither
          do the packages restart apache, although the ``lava-server``
          service will be restarted each time ``lava-server`` is
          installed or updated.

.. _local_version_strings:

Local version strings
=====================

The local version is built (using ``./version.py``) from these components:

* package name
* latest git tag name::

   $ git tag --sort -v:refname|head -n1
   2015.12

* incremental revision list count::

   $ git rev-list --count HEAD
   5451

* latest git hash::

   $ git rev-parse --short HEAD
   f9304da

The latest git hash is a reference to the latest commit. If you have
not committed local changes (e.g. you are on a local branch based on a tag)
then the short hash can be used to lookup the commit in the master
branch, e.g.::

  https://git.linaro.org/lava/lava-server.git/f9304da

.. _distribution_differences:

Distribution differences
========================

LAVA uses a date-based release scheme and PEP440_ imposes constraints
on how local versions can be named and still work reliably with
python-setuptools_, yet these constraints differ between jessie and
unstable::

 jessie:   lava-server-2015.12-5451.f9304da
 unstable: lava-server-2015.12+5451.f9304da

There are also changes internally in the *egg* information used by
setuptools when built on jessie and when built on unstable. Binary
packages built on unstable will fail to install on jessie.

**Always** build packages on the suite you expect to use for
installation.

Packages available from the :ref:`lava_repositories` are built on
Jessie (using sbuild) using the
`lava-buildd scripts <https://git.linaro.org/lava/lava-buildd.git>`_.

.. _pep440: https://www.python.org/dev/peps/pep-0440/
.. _python-setuptools: http://tracker.debian.org/pkg/python-setuptools

Example
=======

The helper supports ``lava-server`` and ``lava-dispatcher``::

 $ sudo apt-get install lava-dev
 $ git clone http://git.linaro.org/git/lava/lava-server.git
 $ cd lava-server
 $ /usr/share/lava-server/debian-dev-build.sh -p lava-server

 $ git clone http://git.linaro.org/git/lava/lava-dispatcher.git
 $ cd lava-dispatcher
 $ /usr/share/lava-server/debian-dev-build.sh -p lava-dispatcher

``lava-dispatcher`` has architecture-dependent dependencies. By
default, the package is built for the native architecture and can
only be installed on that architecture. To build for a different
architecture, e.g. armhf, use::

 $ /usr/share/lava-server/debian-dev-build.sh -p lava-dispatcher -a armhf

This does a *binary build*, so the source is not included, which allows
these builds to be included in a local repository, e.g. using ``reprepro``.

Helpers for other distributions may be added in due course. Patches
welcome.

.. _developer_build_version:

Developer build versions
========================

LAVA uses git tags and the developer build adds a suffix to the tag
for each local build - the suffix is formed from the ``git rev-list --count``
(to get a sequential, unique, identifier) and the ``git rev-parse --short``
hash to identify the latest git commit in the branch upon which this
build is based. The git short hash can be looked up on the ``git.linaro.org``
site, irrespective of which release tag is the current. For example,
build version ``2015.07.5333.1521ddb-1`` relates directly to
``http://git.linaro.org/lava/lava-server.git/1521ddb``

From August 2015, LAVA uses git tags without a leading zero on the month
number, in accordance with PEP440, so the git tag will be ``2015.8``
instead of ``2015.07`` used for the previous release tag.

.. _quick_fixes:

Quick fixes and testing
***********************

The paths to execute LAVA python scripts have changed and developing
LAVA based on packages has a different workflow.

Modified files can be copied to the equivalent python path. The current
LAVA packages use python2.7, so the path is beneath
``/usr/lib/python2.7/dist-packages/`` with sudo::

 $ sudo cp <git-path> /usr/lib/python2.7/dist-packages/<git-path>

.. tip:: This path has recently changed - there are no files in
         ``/usr/share/pyshared/`` after change in python2.7.
         However, this does simplify changes which involve new
         files.

Viewing changes
***************

Different actions are needed for local changes to take effect,
depending on the type of file(s) updated:

==================== ==============================================
templates/\*/\*.html     next browser refresh (F5/Ctrl-R)
\*_app/\*.py             ``$ sudo apache2ctl restart``
\*_daemon/\*.py          ``$ sudo service lava-server restart``
==================== ==============================================

Migrating postgresql versions
*****************************

LAVA installs the ``postgresql`` package which installs the current
default version of postgresql. When this default changes in Debian,
a second package will be added to your system which will start with
no actual data.

Debian gives a notice similar to this when a new version of postgres
is installed::

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

  apt-get install postgresql-8.3

 Then drop the default 8.3 cluster:

  pg_dropcluster 8.3 main --stop

 And then upgrade the 8.2 cluster to 8.3:

  pg_upgradecluster 8.2 main

See also
http://askubuntu.com/questions/66194/how-do-i-migrate-my-postgres-data-from-8-4-to-9-1

Check your existing clusters::

 $ sudo pg_lsclusters

Stop postgresql (stops both versions)::

 $ sudo service postgresql stop

Drop the **main** cluster of the **NEW** postgres as this is empty::

 $ sudo pg_dropcluster 9.4 main --stop

Postgresql knows which version is the current default, so just tell
postgresql which is the old version to migrate the data into the (empty)
new one::

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

Check that the instance is still running. Note that the port of the
new postgresql server will have been upgraded to the port used for the
old postgresql server automatically. Check that this is the case::

 $ grep port /etc/postgresql/9.4/main/postgresql.conf
 port = 5432

Drop the old cluster::

 $ sudo pg_dropcluster 9.3 main

Now the old database package can be removed::

 $ sudo apt-get remove postgresql-9.3

.. index:: javascript

Javascript handling
*******************

Javascript has particular issues in distributions, often the version of
a Javascript file is out of step with the version available in the
distribution or not packaged at all. ``lava-server`` embeds javascript
files in the ``static/js`` directories and maintains a list of files
which are replaced with symlinks during a Debian package build. The
list is in :file:`share/javascript.yaml` and the replacement of matching
files is done using :file:`share/javascript.py`. Other distribution
builds are invited to use the same script or provide patches if the
paths within the script need modification.

After 2015.12 release, all of the .min.js files in the package are removed from
VCS and minified files are created at build time. Templates in the system use
only minified versions of the javascript files so after the release package
rebuild will be mandatory.

.. _javascript_security:

Javascript and security
=======================

The primary concern is security fixes. Distributions release with a
particular release of LAVA and may need to fix security problems in that
release. If the file is replaced by a symlink to an external package
in the distribution, then the security problem and fix migrate to that package.
LAVA tracks these files in :file:`share/javascript.yaml`. Files which
only exist in LAVA or exist at a different version to the one available
in the distribution, need to be patched within LAVA. Javascript files
created by LAVA are packaged as editable source code and patches to these
files will take effect in LAVA after a simple restart of apache and a
clearing of any browser cache. Problems arise when the javascript
files in the LAVA source code have been minified_, resulting in a
:file:`.min.js` file which is **not** suitable for editing or patching.

The source code for the minified JS used in LAVA is provided in the
LAVA source code, alongside the minified version. **However**, there
is a lack of suitable tools to convert changes to the source file into
a comparable minified file. If these files need changes, the correct
fix would be to patch the unminified javascript and copy the modified
file over the top of the minified version. This loses the advantages of
minification but gains the benefit of a known security fix.

.. _javascript_maintenance:

Javascript maintenance
======================

Work is ongoing upstream to resolve the remaining minified javascript
files:

#. **Identify** the upstream location of all javascript not listed in
   :file:`share/javascript.yaml` and not written by LAVA, specify
   this location in a :file:`README` in the relevant :file:`js/` directory
   along with details, if any, of how a modified file can be
   minified or whether a modified file should simply replace the
   minified file.
#. **Replace** the use of the remaining minified JS where the change to
   unminified has a negligible or acceptable performance change. If
   no upstream can be identified, LAVA will need to take over
   maintenance of the javascript itself, at which point minified files
   will be dropped until other LAVA javascript can also be minified.
#. **Monitor** availability of packages for all javascript files not written
   by LAVA and add to the listing in :file:`share/javascript.yaml` when
   packages become available.
#. **Maintain** - only minify javascript written by LAVA **if** a
   suitable minify tool is available to be used during the build of the
   packages and to add such support to :file:`share/javascript.py` so
   that minification happens at the same point as replacement of embedded
   javascript with symlinks to externally provided files.

.. _minified: https://en.wikipedia.org/wiki/Minification_(programming)

.. _testing_packaging:

Packaging changes
=================

From time to time, there can be packaging changes required to handle
changes in the LAVA upstream codebase. If you have write access to
the packaging repository, changes to the packaging can be tested by
pushing to a public branch and passing the ``-b`` option to
:file:`debian-dev-build-sh`::

 $ /usr/share/lava-server/debian-dev-build.sh -p lava-server -b docs

or for installation on jessie::

 $ /usr/share/lava-server/debian-dev-build.sh -p lava-server -b backports

.. _architecture_builds:

Building for other architectures
================================

``lava-server`` is the same for all architectures but ``lava-dispatcher``
has a different set of dependencies depending on the build architecture.
To build an ``armhf`` package of lava-dispatcher using the developer
scripts, use::

 $ /usr/share/lava-server/debian-dev-build.sh -p lava-dispatcher -a armhf

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
   Use `JSONLINT <http://www.jsonlint.com>`_

The toolbar can be disabled without disabling django debug but
django must be in debug mode for the toolbar to be loaded at all.

Restart the ``django`` related services to complete the installation of the toolbar::

 sudo service lava-server restart
 sudo apache2ctl restart

Installation can be checked using ``lava-server manage shell``::

 >>> from django.conf import settings
 >>> 'debug_toolbar' in settings.INSTALLED_APPS
 True

.. seealso:: :ref:`developer_access_to_django_shell`

In order to see the toolbar, you should also check the value of `INTERNAL_IPS
<https://docs.djangoproject.com/en/1.9/ref/settings/#internal-ips>`_.
Local addresses ``127.0.0.1`` and ``::1`` are enabled by default.

To add more addresses, set ``INTERNAL_IPS`` to a list of addresses in
``/etc/lava-server/settings.conf``, (JSON syntax) for example::

  "INTERNAL_IPS": ["192.168.0.5", "10.0.0.6"],

These value depends on your setup. But if you don't see the toolbar
that's the first think to look at.

Apache then needs access to django-debug-toolbar CSS and JS files::

  sudo su -
  cd /usr/share/lava-server/static/
  ln -s /usr/lib/python2.7/dist-packages/debug_toolbar/static/debug_toolbar .

In ``/etc/lava-server/settings.conf`` remove the reference to htdocs
in ``STATICFILES_DIRS``. Django-debug-toolbar does check that all
directories listed in ``STATICFILES_DIRS`` exists. While this is only
a leftover from previous versions of LAVA installer that is not
needed anymore.

Once the changes are complete, ensure the settings are loaded by restarting
both apache2 and django::

 sudo service lava-server restart
 sudo apache2ctl restart

Performance overhead
====================

Keep in mind that django-debug-toolbar has some overhead on the webpage
generation and should only be used while debugging.

Django-debug-toolbar can be disabled, while not debugging, by changing the value
of ``USE_DEBUG_TOOLBAR`` in ``/etc/lava-server/settings.conf`` to ``false``
or by changing the ``̀DEBUG`` level in ``/etc/lava-server/settings.conf`` to ``DEBUG: false``.

Ensure the settings are reloaded by restarting both apache2 and django::

 sudo service lava-server restart
 sudo apache2ctl restart
