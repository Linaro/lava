LAVA developer guide
####################

Pre-requisites to start with development
****************************************

LAVA is written in Python_, so you will need to know (or be willing to
learn) the language. Likewise, the web interface is a Django_ application so
you will need to use and debug Django if you need to modify the web
interface. The pipeline model uses YAML_ (so you'll need the
`YAML Parser <http://yaml-online-parser.appspot.com/?yaml=&type=json>`_)
and Jinja2_. All LAVA software is maintained in git_, as are many of the
support scripts, test definitions and job submissions. Some familiarity
with Debian_ is going to be useful, helper scripts are available when
preparing packages based on your modifications.

LAVA is complex and works to solve complex problems. This has implications
for how LAVA is developed, tested, deployed and used.

Other elements involved in LAVA development
===========================================

The Django backend used with LAVA is PostgreSQL_ and some
`postgres-specific support <http://www.postgresql.org/docs/9.5/static/rules-materializedviews.html>`_
is used. The LAVA UI has some use of Javascript_ and CSS_. LAVA also
uses ZMQ_ and XML-RPC_ and the LAVA documentation is written with RST_.

In addition, test jobs and device support can involve use of U-Boot_,
ADB_, QEMU_, Grub_, SSH_ and a variety of other systems and tools to
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
.. _ZMQ: http://zeromq.org/
.. _XML-RPC: http://xmlrpc.scripting.com/
.. _ADB: http://developer.android.com/tools/help/adb.html
.. _QEMU: http://wiki.qemu.org/Main_Page
.. _Grub: https://www.gnu.org/software/grub/
.. _U-Boot: http://www.denx.de/wiki/U-Boot
.. _SSH: http://www.openssh.com/
.. _POSIX: http://www.opengroup.org/austin/papers/posix_faq.html

.. _developer_workflow:

Developer workflows
===================

.. note:: LAVA is developed using Debian packaging to ensure that
   daemons and system-wide configuration is correctly updated with
   changes in the codebase. There is **no support for pypi or
   python virtual environments or installing directly from a git
   directory**. ``python-setuptools`` is used but only  with ``sdist``
   to create the tarballs to be used for the Debian packaging, not
   for ``install``.

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
waste your development time. Be very careful when copying files and when
using symlinks. If in doubt, remove ``/usr/local/lib/python*`` **and**
``~/.local/lib/python*`` then build a :ref:`local developer package <dev_builds>`
and install it.

If your change introduces a dependency on a new python module, always
ensure that this module is available in Debian by
`searching the Debian package lists <https://www.debian.org/distrib/packages#search_packages>`_.
If the module exists but is not in the current stable release of Debian,
it can be *backported* but be aware that this will delay testing and
acceptance of your change. It is expressly **not acceptable** to add
a dependency on a python module which is only available using pypi or
``pip install``. Introducing such a module to Debian can involve a large
amount of work - :ref:`talk to us <mailing_lists>` before spending time
on code which relies on such modules or which relies on newer versions
of the modules than are currently available in Debian testing.

.. seealso:: :ref:`quick_fixes` and :ref:`testing_refactoring_code`

.. _naming_conventions:

Naming conventions and LAVA V2 architecture
===========================================

Certain terms used in LAVA V2 have specific meanings, please be
consistent in the use of the following terms:

**board**
  The physical hardware sitting in a rack or on a desk.

**connection**
  A means of communicating with a device, often using a serial port
  but can also be SSH_ or another way of obtaining a shell-type
  interactive interface. Connections will typically require a POSIX_
  type shell.

**device**
  A database object in LAVA which stores configuration, information and
  status relating to a single board. The device information can be represented
  in export formats like YAML for use when the database is not accessible.

**device-type**
  A database object which collates similar devices into a group for
  purposes of scheduling. Devices of a single type are often the same
  vendor model but not all boards of the same model will necessarily be
  of the same device-type.

  .. seealso:: :ref:`device_types`

**dispatcher**
  The dispatcher software relates to the ``lava-dispatcher`` source package
  in git and in Debian. The dispatcher software for LAVA V2 can be installed
  without the server or the scheduler and a machine configured in this way
  is also called a *dispatcher*.

**dispatcher-master** or simply **master**
  A singleton process which starts and monitors test jobs running on
  one or more dispatchers by communicating with the slave using ZMQ.

**pipeline**
  The name for the design of LAVA V2, based on how the actions to be
  executed by the dispatcher are arranged in a unidirectional pipe.
  The contents of the pipe are validated before the job starts and
  the description of all elements in the pipe is retained for later
  reference.

  .. seealso:: :ref:`pipeline_construction`

**protocol**
  An API used by the python code inside ``lava-dispatcher`` to interact
  with external systems and daemons when a shell like environment is
  not supported. Protocols need to be supported within the python
  codebase and currently include multinode, LXC and vland.

**scheduler**
  A singleton process which is solely responsible for assigning a device
  to a test job. The scheduler is common to LAVA V1 and LAVA V2 and
  performs checks on submission restrictions, device availability,
  device tags and schema compliance.

  .. seealso:: :term:`device tag`

**server**
  The server software relates to the ``lava-server`` source package in
  git and in Debian. It includes components from LAVA V1 and LAVA V2
  covering the UI and the scheduler daemon.

**slave**
  A daemon running on each dispatcher machine which communicates with
  the dispatcher-master using ZMQ. The slave in LAVA V2 uses whatever
  device configuration the dispatcher-master provides.

**test job**
  A database object which is created for each submission and retains the
  logs and pipeline information generated when the test job executed on
  the device.

Updating online documentation
*****************************

LAVA online documentation is written with RST_ format. You can use the command
below to generate html format files for LAVA V2::

 $ cd lava-server/
 $ make -C doc/v2 html
 $ iceweasel doc/v2/_build/html/index.html
 (or whatever browser you prefer)

We welcome contributions to improve the documentation. If you are considering
adding new features to LAVA or changing current behaviour, ensure that the
changes include updates for the documentation.

.. _RST: http://sphinx-doc.org/rest.html

.. _contribute_upstream:

Contributing Upstream
*********************

The best way to protect your investment on LAVA is to contribute your
changes back. This way you don't have to maintain the changes you need
by yourself, and you don't run the risk of LAVA changed in a way that is
incompatible with your changes.

Upstream uses Debian_, see :ref:`lava_on_debian` for more information.

Community contributions
=======================

Contributing via your distribution
----------------------------------

You are welcome to use the bug tracker of your chosen distribution.
The maintainer for the packages in that distribution should :ref:`register`
with Linaro (or already be part of Linaro) to be able to
forward bug reports and patches into the upstream LAVA systems.

.. seealso:: https://www.debian.org/Bugs/Reporting

.. _register:

Register with Linaro as a Community contributor
-----------------------------------------------

If you, or anyone on your team, would like to register with Linaro directly,
this will allow you to file an upstream bug, submit code for review by
the LAVA team, etc. Register at the following url:

https://register.linaro.org/

If you are considering large changes, it is best to register and also
to subscribe to the :ref:`lava_devel` mailing list and talk
to us on IRC::

 irc.freenode.net
 #linaro-lava

Contributing via GitHub
-----------------------

You can use GitHub to fork the LAVA packages and make pull requests.

https://github.com/Linaro

It is worth sending an email to the :ref:`lava_devel` mailing list, so
that someone can migrate the pull request to a review.
