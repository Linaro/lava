LAVA development
################

Pre-requisites to start with development
****************************************

LAVA is written in Python_, so you will need to know (or be willing to
learn) the language. Likewise, the web interface is a Django_ application so
you will need to use and debug Django if you need to modify the web
interface. All LAVA software is maintained in git_, as are many of the
support scripts, test definitions and job submissions. Some familiarity
with Debian_ is going to be useful, helper scripts are available when
preparing packages based on your modifications.

LAVA is complex and works to solve complex problems. This has implications
for how LAVA is developed, tested, deployed and used.

.. _Debian: https://www.debian.org/

Other elements involved in LAVA development
===========================================

The Django backend used with LAVA is PostgreSQL_ and some
`postgres-specific support <http://www.postgresql.org/docs/9.5/static/rules-materializedviews.html>`_
is used. The LAVA UI has some use of Javascript_ and CSS_. LAVA V1 also
uses XML-RPC_ and the LAVA documentation is written with RST_.

In addition, test jobs and device support can involve use of U-Boot_,
ADB_, QEMU_, Grub_, SSH_ and a variety of other systems and tools to
access devices and debug test jobs.

.. _Python: http://www.python.org/
.. _Django: https://www.djangoproject.com/
.. _git: http://www.git-scm.org/
.. _PostgreSQL: http://www.postgresql.org/
.. _Debian: https://www.debian.org/
.. _Javascript: https://www.javascript.com/
.. _CSS: https://www.w3.org/Style/CSS/Overview.en.html
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
   for ``install``. Some dependencies of LAVA are not available with
   pypi, for example ``python-guestfs``.

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

Naming conventions and LAVA V1 architecture
===========================================

Certain terms used in LAVA V1 have specific meanings, please be
consistent in the use of the following terms:

**board**
  The physical hardware sitting in a rack or on a desk.

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
  in git and in Debian. The dispatcher software for LAVA V1 must be installed
  alongside the server with extra configuration and a machine like this
  is also called a *dispatcher* or a remote worker.

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

**test job**
  A database object which is created for each submission and retains the
  logs and pipeline information generated when the test job executed on
  the device.

Updating online documentation
*****************************

LAVA online documentation is written with RST_ format. You can use the command
below to generate html format files.::

 $ cd lava-server/
 $ make -C doc/v1 html
 $ iceweasel doc/v1/_build/html/index.html
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

.. _register:

Register with Linaro as a Community contributor
-----------------------------------------------

If you, or anyone on your team, would like to register with Linaro directly,
this will allow you to file an upstream bug, submit code for review by
the LAVA team, etc. Register at the following url:

https://register.linaro.org/

If you are considering large changes, it is best to register and also
to subscribe to the `lava_devel` mailing list and talk
to us on IRC::

 irc.freenode.net
 #linaro-lava

Contributing via GitHub
-----------------------

You can use GitHub to fork the LAVA packages and make pull requests.

https://github.com/Linaro

It is worth sending an email to the `lava_devel` mailing list, so
that someone can migrate the pull request to a review.

Patch Submissions and workflow
==============================

This is a short guide on how to send your patches to LAVA. The LAVA team
uses the gerrit_ code review system to review changes.

.. _gerrit: http://review.linaro.org/

If you do not already have a Linaro account, you will first need to
:ref:`register`.

So the first step will be logging in to gerrit_ and uploading you SSH
public key there.

Obtaining the repository
------------------------

There are two main components to LAVA, ``lava-server`` and
``lava-dispatcher``.

::

    git clone http://git.linaro.org/git/lava/lava-server.git
    cd lava-server

    git clone http://git.linaro.org/git/lava/lava-dispatcher.git
    cd lava-dispatcher

There is also ``lava-tool`` which is gaining more support for
operations involving the V2 design::

    git clone http://git.linaro.org/git/lava/lava-tool.git
    cd lava-tool

Setting up git-review
---------------------

::

    git review -s

Create a topic branch
---------------------

We recommend never working off the master branch (unless you are a git
expert and really know what you are doing). You should create a topic
branch for each logically distinct change you work on.

Before you start, make sure your master branch is up to date::

    git checkout master
    git pull

Now create your topic branch off master::

    git checkout -b my-change master

Run the unit tests
------------------

Extra dependencies are required to run the tests. On Debian based distributions,
you can install ``lava-dev``. (If you only need to run the ``lava-dispatcher``
unit tests, you can just install ``pep8`` and ``python-testscenarios``.)

To run the tests, use the ``ci-run`` script::

 $ ./ci-run

Functional testing
------------------

Unit tests cannot replicate all tests required on LAVA code, some tests will need
to be run with real devices under test. On Debian based distributions,
see :ref:`dev_builds`. See :ref:`writing_tests` for information on writing
LAVA test jobs to test particular device functionality.

Make your changes
-----------------

* Follow PEP8 style for Python code.
* Make one commit per logical change.
* Use one topic branch for each logical change.
* Include unit tests in the commit of the change being tested.
* Write good commit messages. Useful reads on that topic:

 * `A note about git commit messages`_
 * `5 useful tips for a better commit message`_


.. _`A note about git commit messages`: http://tbaggery.com/2008/04/19/a-note-about-git-commit-messages.html

.. _`5 useful tips for a better commit message`: http://robots.thoughtbot.com/post/48933156625/5-useful-tips-for-a-better-commit-message

Re-run the unit tests
---------------------

Make sure that your changes do not cause any failures in the unit tests::

 $ ./ci-run

Wherever possible, always add new unit tests for new code.

Send your commits for review
----------------------------

From each topic branch, just run::

    git review

If you have multiple commits in that topic branch, git review will warn
you. It's OK to send multiple commits from the same branch, but note
that 1) commits are review and approved individually and 2) later
commits  will depend on earlier commits, so if a later commit is
approved and the one before it is not, the later commit will not be
merged until the earlier one is approved.

Submitting a new version of a change
------------------------------------

When reviewers make comments on your change, you should amend the
original commit to address the comments, and **not** submit a new change
addressing the comments while leaving the original one untouched.

Locally, you can make a separate commit addressing the reviewer
comments, it's not a problem. But before you resubmit your branch for
review, you have to rebase your changes against master to end up with a
single, enhanced commit. For example::

    $ git branch
      master
    * my-feature
    $ git show-branch master my-feature
    ! [master] Last commit on master
     ! [my-feature] address revier comments
    --
     + [my-feature] address reviewer comments
     + [my-feature^] New feature or bug fix
    -- [master] Last commit on master
    $ git rebase -i master


``git rebase -i`` will open your ``$EDITOR`` and present you with something
like this::

    pick xxxxxxx New feature or bug fix
    pick yyyyyyy address reviewer comments

You want the last commit to be combined with the first and keep the
first commit message, so you change ``pick`` to ``fixup`` ending up with
somehting like this::

    pick xxxxxxx New feature or bug fix
    fixup yyyyyyy address reviewer comments

If you also want to edit the commit message of the first commit to
mention something else, change ``pick`` to ``reword`` and you will have the
chance to do that. Just remember to keep the ``Change-Id`` unchanged.

**NOTE**: if you want to abort the rebase, just delete everything, save
the file as empty and exit the ``$EDITOR``.

Now save the file and exit your ``$EDITOR``.

In the end, your original commit will be updated with the changes::

    $ git show-branch master my-feature
    ! [master] Last commit on master
     ! [my-feature] New feature or bug fix
    --
     + [my-feature] New feature or bug fix
    -- [master] Last commit on master


Note that the "New feature or bug fix" commit is now not the same as
before since it was modified, so it will have a new hash (``zzzzzzz``
instead of the original ``xxxxxxx``). But as long as the commit message
still contains the same ``Change-Id``, gerrit will know it is a new version
of a previously submitted change.

Handling your local branches
----------------------------

After placing a few reviews, there will be a number of local branches.
To keep the list of local branches under control, the local branches can
be easily deleted after the merge. Note: git will warn if the branch has
not already been merged when used with the lower case ``-d`` option.
This is a useful check that you are deleting a merged branch and not an
unmerged one, so work with git to help your workflow.

::

    $ git checkout bugfix
    $ git rebase master
    $ git checkout master
    $ git branch -d bugfix


If the final command fails, check the status of the review of the
branch. If you are completely sure the branch should still be deleted or
if the review of this branch was abandoned, use the `-D` option
instead of `-d` and repeat the command.

Reviewing changes in clean branches
-----------------------------------

If you haven't got a clone handy on the instance to be used for the
review, prepare a clone as usual.

Gerrit provides a number of ways to apply the changes to be reviewed, so
set up a test branch as usual - always ensuring that the master branch
of the clone is up to date before creating the review branch.

::

    $ git checkout master
    $ git pull
    $ git checkout -b review-111

To pull in the changes in the review already marked for commit in your
local branch, use the ``pull`` link in the patch set of the review you
want to run.

Alternatively, to pull in the changes as plain patches, use the
``patch``` link and pipe that to ``patch -p1``. In this full example,
the second patch set of review 159 is applied to the ``review-159``
branch as a patch set.

::

    $ git checkout master
    $ git pull
    $ git checkout -b review-159
    $ git fetch https://review.linaro.org/lava/lava-server refs/changes/59/159/2 && git format-patch -1 --stdout FETCH_HEAD | patch -p1
    $ git status

Handle the local branch as normal. If the reviewed change needs
modification and a new patch set is added, revert the local change and
apply the new patch set.

Other considerations
====================

All developers are encouraged to write code with futuristic changes in
mind, so that it is easy to do a technology upgrade, which includes
watching for errors and warnings generated by dependency packages as
well as upgrading and migrating to newer APIs as a normal part of
development.

.. _database_migrations:

Database migrations
-------------------

LAVA recommends Debian Jessie but also supports Ubuntu Trusty which has
an older version of `python-django <https://tracker.debian.org/pkg/python-django>`_.

Database migrations on Debian Jessie and later are managed within
django. Support for
`python-django-south <https://tracker.debian.org/pkg/python-django-south>`_
has been **dropped**. **Only django** migration types should be included
in any reviews which involve a database migration.

Once modified, the updated ``models.py`` file needs to be copied into
the system location for the relevant extension, e.g. ``lava_scheduler_app``.
This is a step which needs to be done by the developer - developer packages
**cannot** be installed cleanly and **unit tests will likely fail** until
the migration has been created and applied.

On Debian Jessie and later::

 $ sudo lava-server manage makemigrations lava_scheduler_app

The migration file will be created in
``/usr/lib/python2.7/dist-packages/lava_scheduler_app/migrations/`` (which
is why ``sudo`` is required) and will need to be copied into your git
working copy and added to the review.

The migration is applied using::

 $ sudo lava-server manage migrate lava_scheduler_app

See `django docs <https://docs.djangoproject.com/en/1.8/topics/migrations/>`_
for more information.

Python 3.x
----------

There is no pressure or expectation on delivering python 3.x code.
LAVA is a long way from being able to use python 3.x support,
particularly in lava-server, due to the lack of python 3.x migrations
in dependencies. However it is good to take python 3.x support into
account, when writing new code, so that it makes it easy during
the move anytime in the future.

Developers can run unit tests against python 3.x for all LAVA
components from time to time and keep a check on how we can support
python 3.x without breaking compatibility with python 2.x

Pylint
------

`Pylint`_ is a tool that checks for errors in Python code, tries to
enforce a coding standard and looks for bad code smells. We encourage
developers to run LAVA code through pylint and fix warnings or errors
shown by pylint to maintain a good score. For more information about
code smells, refer to Martin Fowler's `refactoring book`_. LAVA
developers stick on to `PEP 008`_ (aka `Guido's style guide`_) across
all the LAVA component code.

To simplify the pylint output, some warnings are recommended to be
disabled::

 $ pylint -d line-too-long -d missing-docstring

**NOTE**: Docstrings should still be added wherever a docstring would
be useful.

In order to check for `PEP 008`_ compliance the following command is
recommended::

  $ pep8 --ignore E501

`pep8` can be installed in debian based systems as follows::

  $ apt-get install pep8

Unit-tests
----------
LAVA has set of unit tests which the developers can run on a regular
basis for each change they make in order to check for regressions if
any. Most of the LAVA components such as ``lava-server``,
``lava-dispatcher``, :ref:`lava-tool <lava_tool>` have unit tests.

Extra dependencies are required to run the tests. On Debian based
distributions, you can install lava-dev. (If you only need to run the
``lava-dispatcher`` unit tests, you can just install `pep8` and
`python-testscenarios`.)

To run the tests, use the ci-run / ci-build scripts::

  $ ./ci-run

.. _`Pylint`: http://www.pylint.org/
.. _`refactoring book`: http://www.refactoring.com/
.. _`PEP 008`: http://www.python.org/dev/peps/pep-0008/
.. _`Guido's style guide`: http://www.python.org/doc/essays/styleguide.html

LAVA database model visualization
---------------------------------
LAVA database models can be visualized with the help of
`django_extensions`_ along with tools such as `pydot`_. In debian
based systems install the following packages to get the visualization
of LAVA database models::

  $ apt-get install python-django-extensions python-pydot

Once the above packages are installed successfully, use the following
command to get the visualization of ``lava-server`` models in PNG
format::

  $ sudo lava-server manage graph_models --pydot -a -g -o lava-server-model.png

More documentation about graph models is available in
http://django-extensions.readthedocs.org/en/latest/graph_models.html

Other useful features from `django_extensions`_ are as follows:

* `shell_plus`_ - similar to the built-in "shell" but autoloads all
   models

* `validate_templates`_ - check templates for rendering errors

    $ sudo lava-server manage validate_templates

* `runscript`_ - run arbitrary scripts inside ``lava-server``
  environment

    $ sudo lava-server manage runscript fix_user_names --script-args=all

.. _`django_extensions`: https://django-extensions.readthedocs.org/en/latest/
.. _`pydot`: https://pypi.python.org/pypi/pydot
.. _`shell_plus`: http://django-extensions.readthedocs.org/en/latest/shell_plus.html
.. _`validate_templates`: http://django-extensions.readthedocs.org/en/latest/validate_templates.html
.. _`runscript`: http://django-extensions.readthedocs.org/en/latest/runscript.html

.. _developer_access_to_django_shell:

Developer access to django shell
--------------------------------
Default configurations use a side-effect of the logging behaviour to restrict access to the
``lava-server manage`` operations which typical Django apps expose through the ``manage.py``
interface. This is because ``lava-server manage shell`` provides read-write access to the database,
so the command requires ``sudo``.

On developer machines, this can be unnecessary. Set the location of the django log to a new location
to allow easier access to the management commands to simplify debugging and to be able to run a Django
Python Console inside a development environment. In ``/etc/lava-server/settings.conf`` add::

 "DJANGO_LOGFILE": "/tmp/django.log"

.. note:: ``settings.conf`` is JSON syntax, so ensure that the previous line ends with a comma
   and that the resulting file validates as JSON. Use `JSONLINT <http://www.jsonlint.com>`_

The new location needs to be writable by the ``lavaserver`` user (for use by localhost) and by the
developer user (but would typically be writeable by anyone).
