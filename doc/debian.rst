.. _lava_on_debian:

Developing LAVA on Debian or Ubuntu
###################################

Packages for LAVA are available for:

======================== =============================
Debian                    Ubuntu
Debian Jessie (testing)   Ubuntu Trusty Tahr 14.04LTS
Debian Sid (unstable)     Ubuntu Utopic Unicorn
======================== =============================

To install on Ubuntu, ensure the universe_ repository is enabled.

.. _universe: https://help.ubuntu.com/community/Repositories/CommandLine#Adding_the_Universe_and_Multiverse_Repositories

When using the packages to develop LAVA, there is a change to
the workflow compared to the old lava-deployment-tool buildouts.

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

 $ /usr/share/lava-server/debian-dev-build.sh lava-server

The packages will be built in a temporary directory using a version string
based on the current git tag and the time of the build. The helper
outputs the location of all the built packages at the end of a successful
build, ready for use with ``$ sudo dpkg -i``.

.. note:: the helper does **not** install the packages for you, neither
          do the packages restart apache, although the ``lava-server``
          service will be restarted each time ``lava-server`` is
          installed or updated.

The helper supports ``lava-server`` and ``lava-dispatcher``::

 $ sudo apt-get install lava-dev
 $ git clone http://git.linaro.org/git/lava/lava-server.git
 $ cd lava-server
 $ /usr/share/lava-server/debian-dev-build.sh lava-server

 $ git clone http://git.linaro.org/git/lava/lava-dispatcher.git
 $ cd lava-dispatcher
 $ /usr/share/lava-server/debian-dev-build.sh lava-dispatcher

``lava-dispatcher`` has architecture-dependent dependencies. By
default, the package is built for the native architecture and can
only be installed on that architecture. To build for a different
architecture, e.g. armhf, use::

 $ /usr/share/lava-server/debian-dev-build.sh lava-dispatcher armhf

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
