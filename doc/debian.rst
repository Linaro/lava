.. _lava_on_debian:

Developing LAVA on Debian or Ubuntu
***********************************

Packages for LAVA are available for:

======================== =============================
Debian                    Ubuntu
Debian Jessie (testing)   Ubuntu Trusty Tahr 10.04LTS
Debian Sid (unstable)     Ubuntu Utopic Unicorn
======================== =============================

When using the packages to develop LAVA, there is a change to
the workflow compared to the old lava-deployment-tool buildouts.

.. _dev_builds:

Developer package build
#######################

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

.. _quick_fixes:

Quick fixes and testing
#######################

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
===============

Different actions are needed for local changes to take effect,
depending on the type of file(s) updated:

==================== ==============================================
templates/\*/\*.html     next browser refresh (F5/Ctrl-R)
\*_app/\*.py             ``$ sudo apache2ctl restart``
\*_daemon/\*.py          ``$ sudo service lava-server restart``
==================== ==============================================
