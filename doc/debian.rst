Developing LAVA on Debian
*************************

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

The helper is likely to improve in time but currently needs to know the
name of the package to build::

 $ /usr/share/lava-server/debian-dev-build.sh lava-server

The packages will be built in a temporary directory using a version string
based on the current git tag and the time of the build. The helper
outputs the location of all the built packages at the end of a successful
build, ready for use with ``$ sudo dpkg -i``.

.. note:: the helper does **not** install the packages for you, neither
          do the packages restart apache, although the ``lava-server``
          service will be restarted each time ``lava-server`` is
          installed or updated. Also note that ``lava-server`` builds
          packages which may conflict with each other - select the
          packages you already have installed.

Currently, the helper only supports the public ``packaging`` branch of
``lava-server``::

 $ sudo apt-get install lava-dev
 $ git clone http://git.linaro.org/git/lava/lava-server.git
 $ cd lava-server
 $ git checkout packaging
 $ /usr/share/lava-server/debian-dev-build.sh lava-server

Helpers for other distributions may be added in due course. Patches
welcome.

Quick fixes and testing
#######################

The paths to execute LAVA python scripts have changed and developing
LAVA based on packages has a different workflow.

Modified files can be copied to the equivalent path beneath ``/usr/share/pyshared/``
with sudo::

 $ sudo cp <git-path> /usr/share/pyshared/<git-path>

New files will need to be copied directly into the python path for the
module - or added by doing a local :ref:`dev_builds`. e.g. for python2.7
the path would be: ``/usr/lib/python2.7/dist-packages/<git-path>``. When
the package is built to include the new files, the old files will be
replaced with symlinks to the packaged files in ``/usr/share/pyshared``.

Viewing changes
===============

Different actions are needed for local changes to take effect,
depending on the type of file(s) updated:

==================== ==============================================
templates/\*/\*.html     next browser refresh (F5/Ctrl-R)
\*_app/\*.py             ``$ sudo apache2ctl restart``
\*_daemon/\*.py          ``$ sudo service lava-server restart``
==================== ==============================================
