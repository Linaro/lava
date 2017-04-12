.. index:: developing LAVA

.. _lava_development:

LAVA development
################

Before you start, ensure you've read the :ref:`development_pre_requisites`.

.. seealso:: :ref:`contribute_upstream`

.. _development_workflow:

Patch Submissions and workflow
******************************

This is a short guide on how to send your patches to LAVA. The LAVA team uses
the gerrit_ code review system to review changes.

.. _gerrit: https://review.linaro.org/

If you do not already have a Linaro account, you will first need to
:ref:`register`.

So the first step will be logging in to gerrit_ and uploading you SSH public
key there.

Obtaining the repository
========================

There are two main components to LAVA, ``lava-server`` and
``lava-dispatcher``.

::

    git clone https://git.linaro.org/git/lava/lava-server.git
    cd lava-server

    git clone https://git.linaro.org/git/lava/lava-dispatcher.git
    cd lava-dispatcher

There is also ``lava-tool`` which is gaining more support for operations
involving the :ref:`dispatcher_design`::

    git clone https://git.linaro.org/git/lava/lava-tool.git
    cd lava-tool

Setting up git-review
=====================

If you have not done so already, ``git review`` needs to be setup for each
clone of each source::

    git review -s

.. _developer_topic_branches:

Create a topic branch
=====================

We recommend **never** working off the master branch (unless you are a git
expert and really know what you are doing). You should create a topic branch
for each logically distinct change you work on.

.. note:: Unless your change **directly** depends on changes made in an earlier
   commit on a branch, this means making a fresh branch for each change with
   **one commit** per branch.

   .. seealso:: :ref:`developer_submitting_new_version` and :ref:`developer_submitting_new_version`

Before you start, make sure your master branch is up to date::

    git checkout master
    git pull

Now create your topic branch off master::

    git checkout -b my-change master

.. _running_all_unit_tests:

Run the unit tests
==================

Extra dependencies are required to run the tests. On Debian based
distributions, you can install ``lava-dev``.

To run the tests, use the ``ci-run`` script::

 $ ./ci-run

See also :ref:`testing_pipeline_code` and :ref:`developer_preparations`

Functional testing
==================

Unit tests cannot replicate all tests required on LAVA code, some tests will
need to be run with real devices under test. On Debian based distributions, see
:ref:`dev_builds`. See :ref:`writing_tests` for information on writing LAVA
test jobs to test particular device functionality.

Make your changes
=================

* Follow PEP8 style for Python code.
* Make one commit (and hence one review) per logical change.
* Use one topic branch for each logical change.
* Include unit tests in the commit of the change being tested.
* Write good commit messages. There are a number of useful guides:

  * `A note about git commit messages`_
  * `5 useful tips for a better commit message`_


.. _`A note about git commit messages`: http://tbaggery.com/2008/04/19/a-note-about-git-commit-messages.html

.. _`5 useful tips for a better commit message`: https://robots.thoughtbot.com/post/48933156625/5-useful-tips-for-a-better-commit-message

Re-run the unit tests
=====================

Make sure that your changes do not cause any failures in the unit tests::

 $ ./ci-run

Wherever possible, always add new unit tests for new code.

Testing local changes
=====================

For any sufficiently large change, :ref:`building <dev_builds>` and installing
a new package on a local instance is recommended. Ensure that the test instance
is already running the most recent production release.

If the test instance has a separate worker, ensure that the master and the
worker always have precisely the same code applied. For some changes, it may be
necessary to have a test instance which is a clone of a production instance,
complete with devices. **Never** make live changes to a production instance.
(This is why integrating new device types into LAVA requires multiple devices.)

Once your change is working successfully:

#. Ensure that your local branch is clean - check for left over debug code.

#. Ensure that your local branch has been rebased against current ``master``

#. Build and install a package from the ``master`` branch. If you have added
   any new files in your local change, make sure these have been removed.
   Reproduce the original bug or problem.

#. Build and install a package from your local branch and repeat the tests.

lava-dispatcher
---------------

Changes to most files in ``lava-dispatcher`` can be symlinked or copied into
the packaged locations. e.g.::

 PYTHONDIR=/usr/lib/python2.7/dist-packages/
 sudo cp <path_to_file> $PYTHONDIR/<path_to_file>

There is no need to copy files used solely by the unit tests.

Changes to files in ``./etc/`` will require restarting the relevant service.

Changes to files in ``./lava/dispatcher/`` will need the ``lava-slave``
service to be restarted.

lava-server
-----------

Changes to device-type templates and device dictionaries take effect
immediately, so simply submitting a test job will pick up the latest
version of the code in
``/etc/lava-server/dispatcher-config/device-types/``. Make changes to
the templates in ``lava_scheduler_app/tests/device-types/``. Check
them using the ``test_all_templates`` test, and only then copy the
updates into ``/etc/lava-server/dispatcher-config/device-types/`` when
the tests pass.

.. seealso:: :ref:`testing_new_devicetype_templates`

Changes to django templates can be applied immediately by copying the template
into the packaged path, e.g. html files in
``lava_scheduler_app/templates/lava_scheduler_app/`` can be copied or symlinked
to
``/usr/lib/python2.7/dist-packages/lava_scheduler_app/templates/lava_scheduler_app/``

Changes to python code generally require copying the files and restarting the
``lava-server-gunicorn`` service before the changes will be applied::

 sudo service lava-server-gunicorn restart

Changes to ``lava_scheduler_app/models.py``, ``lava_scheduler_app/db_utils.py``
or ``lava_results_app/dbutils`` will require restarting the ``lava-master``
service::

 sudo service lava-master restart

Changes to files in ``./etc/`` will require restarting the relevant service. If
multiple services are affected, it is normally best to build and install a new
package.

:ref:`database_migrations` are a complex area - read up on the django
documentation for migrations. Instead of ``python ./manage.py``, use
``sudo lava-server manage``.

lava-server-doc
---------------

Documentation files in ``doc/v2`` can be built locally in the git checkout
using ``make``::

 make -C doc/v2 clean
 make -C doc/v2 html

Files can then be checked in a web browser using the ``file://`` url scheme and
the ``_build/html/`` subdirectory. For example:
``file:///home/neil/code/lava/lava-server/doc/v2/_build/html/first_steps.html``

Some documentation changes can add images, example test jobs, test definitions
and other files. Depending on the type of file, it may be necessary to make
changes to the packaging, so :ref:`talk to us <getting_support>` before making such
changes.

Documentation is written in RST, so the `RST Primer
<http://www.sphinx-doc.org/en/stable/rest.html>`_ is essential reading when
modifying the documentation.

#. Keep all documentation paragraphs wrapped to 80 lines.

#. Use ``en_GB`` unless referring to elements of code which use ``en_US``.

#. Use syntax highlighting for code and check the rendered page. For example,
   ``code-block:: shell`` relates to the contents of shell scripts, not the
   output of commands or scripts in a shell (those should use ``code-block::
   none``)

#. Wherever possible, pull in code samples from working example files so that
   these can be checked for accuracy on `staging
   <https://staging.validation.linaro.org/>`_ before future releases.

.. _developer_commit_for_review:

Send your commits for review
============================

From each topic branch, just run::

    git review

If you have multiple commits in that topic branch, git review will warn you.
It's OK to send multiple commits from the same branch, but note that:

#. commits are review and approved individually and

#. later commits  will depend on earlier commits, so if a later commit is
   approved and the one before it is not, the later commit will not be merged
   until the earlier one is approved.

#. you are responsible for **rebasing** your branch(es) against updates on
   master and this can become **much** more difficult when there are multiple
   commits on one local branch. It can become a **lot** of work to make the
   correct changes in the correct commit on a single branch.

#. Fixes from comments or unit test failures in one review are **not**
   acceptable as separate reviews, so don't be tempted to make another commit
   at the top of the branch.

Therefore the recommentations are:

#. **Always** use a separate local branch per commit

#. Think carefully about whether to base one local branch on another local
   branch. This is recommended when one change logically extends an earlier
   change and makes it a lot easier than having multiple commits on a single
   branch.

#. Keep all your branches up to date with master **regularly**. It is much
   better to resolve merge conflicts one change at a time instead of having
   multiple merge commits all in the one rebase operation.

.. _developer_adding_reviewers:

Adding reviewers
================

Reviews submitted for ``lava-server``, ``lava-dispatcher`` and ``lava-tool``
will **automatically** have the LAVA software team added as reviewers when the
review is first submitted.

Other reviewers can also be added to individual reviews. The Owner of the
review is always added. Reviewers will get email for all changes relating to
that review. All reviewers need to :ref:`register`, email will go to the
``@linaro.org`` account of that reviewer.

If you know that there are still problems to fix in the review, please use the
Gerrit interface to reply to the review and give the review a score of ``-1``
and sumamrise your concerns in the comment. This indicates to the software team
that this review should not be considered for merging into master at this time.
You may still get comments.

Optionally, you can put ``[RFC]`` or similar at the start of your git commit
message and then amend the message when the review is ready to merge.

.. _developer_submitting_new_version:

Submitting a new version of a change
====================================

When reviewers make comments on your change, you should amend the original
commit to address the comments, and **not** submit a new change addressing the
comments while leaving the original one untouched.

Gerrit handles this by adding a ChangeId to your commit message. Keep this Id
unchanged when amending commit messages.

Locally, you can make a separate commit addressing the reviewer comments, it's
not a problem. But before you resubmit your branch for review, you have to
rebase your changes against master to end up with a single, enhanced commit.
For example::

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

You want the last commit to be combined with the first and keep the first
commit message, so you change ``pick`` to ``fixup`` ending up with somehting
like this::

    pick xxxxxxx New feature or bug fix
    fixup yyyyyyy address reviewer comments

If you also want to edit the commit message of the first commit to mention
something else, change ``pick`` to ``reword`` and you will have the chance to
do that. Just remember to keep the ``Change-Id`` unchanged.

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


Note that the "New feature or bug fix" commit is now not the same as before
since it was modified, so it will have a new hash (``zzzzzzz`` instead of the
original ``xxxxxxx``). But as long as the commit message still contains the
same ``Change-Id``, gerrit will know it is a new version of a previously
submitted change.

Handling your local branches
============================

After placing a few reviews, there will be a number of local branches. To keep
the list of local branches under control, the local branches can be easily
deleted after the merge. Note: git will warn if the branch has not already been
merged when used with the lower case ``-d`` option. This is a useful check that
you are deleting a merged branch and not an unmerged one, so work with git to
help your workflow.

::

    $ git checkout bugfix
    $ git rebase master
    $ git checkout master
    $ git branch -d bugfix


If the final command fails, check the status of the review of the branch. If
you are completely sure the branch should still be deleted or if the review of
this branch was abandoned, use the `-D` option instead of `-d` and repeat the
command.

Reviewing changes in clean branches
===================================

If you haven't got a clone handy on the instance to be used for the review,
prepare a clone as usual.

Gerrit provides a number of ways to apply the changes to be reviewed, so set up
a test branch as usual - always ensuring that the master branch of the clone is
up to date before creating the review branch.

::

    $ git checkout master
    $ git pull
    $ git checkout -b review-111

To pull in the changes in the review already marked for commit in your local
branch, use the ``pull`` link in the patch set of the review you want to run.

Alternatively, to pull in the changes as plain patches, use the ``patch``` link
and pipe that to ``patch -p1``. In this full example, the second patch set of
review 159 is applied to the ``review-159`` branch as a patch set.

::

    $ git checkout master
    $ git pull
    $ git checkout -b review-159
    $ git fetch https://review.linaro.org/lava/lava-server refs/changes/59/159/2 && git format-patch -1 --stdout FETCH_HEAD | patch -p1
    $ git status

Handle the local branch as normal. If the reviewed change needs modification
and a new patch set is added, revert the local change and apply the new patch
set.

Future proofing
***************

All developers are encouraged to write code with futuristic changes in mind, so
that it is easy to do a technology upgrade, which includes watching for errors
and warnings generated by dependency packages as well as upgrading and
migrating to newer APIs as a normal part of development.

This is particularly true for Django where the ``lava-server`` package needs to
retain support for multiple django versions as well as monitoring for
deprecation warnings in the newest django version. Where necessary, write code
for different versions and separate with:

.. code-block:: python

 import django
 if django.VERSION > (1, 8):
     pass  # newer code
 else:
     pass  # older compatibility code

.. _database_migrations:

Database migrations
*******************

LAVA recommends Debian Jessie but also supports testing and unstable which have
a newer version of `python-django
<https://tracker.debian.org/pkg/python-django>`_.

Database migrations on Debian Jessie and later are managed within django.
Support for `python-django-south
<https://tracker.debian.org/pkg/python-django-south>`_ has been **dropped**.
**Only django** migration types should be included in any reviews which involve
a database migration.

Once modified, the updated ``models.py`` file needs to be copied into the
system location for the relevant extension, e.g. ``lava_scheduler_app``. This
is a step which needs to be done by the developer - developer packages
**cannot** be installed cleanly and **unit tests will likely fail** until the
migration has been created and applied.

On Debian Jessie and later::

 $ sudo lava-server manage makemigrations lava_scheduler_app

The migration file will be created in
``/usr/lib/python2.7/dist-packages/lava_scheduler_app/migrations/`` (which is
why ``sudo`` is required) and will need to be copied into your git working copy
and added to the review.

The migration is applied using::

 $ sudo lava-server manage migrate lava_scheduler_app

See `django docs <https://docs.djangoproject.com/en/1.8/topics/migrations/>`_
for more information.

Python 3.x
**********

LAVA dispatcher now supports python3 testing but **only** for the pipeline unit
tests. Code changes to the V2 dispatcher code (i.e. in the
``lava_dispatcher/pipeline`` tree) **must** be sufficiently aware of Python3 to
not break the unit tests when run using python3.

LAVA is not yet ready to use python 3.x support at runtime, particularly in
lava-server, due to the lack of python 3.x migrations in dependencies. However
it is good to take python 3.x support into account in ``lava-server``, when
writing new code for LAVA v2, so that it makes it easy during the move anytime
in the future.

All reviews run the ``lava-dispatcher.pipelnie`` V2 unit tests against python
3.x and changes must pass without breaking compatibility with python 2.x

The ``./ci-run`` script for ``lava-dispatcher`` shows how to run the python3
unit tests::

 # to run python3 unit tests, you can use
 # python3 -m unittest discover -v lava_dispatcher.pipeline
 # but the python3 dependencies are not automatically installed.

The list of python3 dependencies needed for the pipeline unit tests is
maintained as part of the functional tests:

https://git.linaro.org/lava-team/refactoring.git/tree/functional/dispatcher-pipeline-python3.yaml

From time to time, reviews may add more python dependencies - check on the
:ref:`mailing_lists` if your tests start to fail after rebasing on current
master or if you want to help with more python3 support in LAVA V2.

Avoid making changes to LAVA V1 code for python3 - only LAVA V2 is going to
support python3.

XML-RPC changes
***************

Each of the installed django apps in ``lava-server`` are able to expose
functionality using :ref:`XML-RPC <xml_rpc>`.

.. code-block:: python

 from linaro_django_xmlrpc.models import ExposedAPI

 class SomeAPI(ExposedAPI):

#. The ``docstring`` **must** include the full user-facing documentation of
   each function exposed through the API.

#. Authentication should be supported using the base class support:

   .. code-block:: python

    self._authenticate()

#. Catch exceptions for all errors, ``SubmissionException``, ``DoesNotExist``
   and others, then re-raise as ``xmlrpclib.Fault``.

#. Move as much of the work into the relevant app as possible, either in
   ``models.py`` or in ``dbutils.py``. Wherever possible, re-use existing
   functions with wrappers for error handling in the API code.

.. _lava_instance_settings:

Instance settings
*****************

``/etc/lava-server/instance.conf`` is principally for V1 configuration. V2 uses
this file only for the database connection settings on the master, instance
name and the ``lavaserver`` user.

Most settings for the instance are handled inside django using
``/etc/lava-server/settings.conf``. (For historical reasons, this file uses
**JSON** syntax.)

.. seealso:: :ref:`branding`, :ref:`django_debug_toolbar` and
   :ref:`developer_access_to_django_shell`

.. _pylint_tool:

Pylint
******

`Pylint`_ is a tool that checks for errors in Python code, tries to enforce a
coding standard and looks for bad code smells. We encourage developers to run
LAVA code through pylint and fix warnings or errors shown by pylint to maintain
a good score. For more information about code smells, refer to Martin Fowler's
`refactoring book`_. LAVA developers stick on to `PEP 008`_ (aka `Guido's style
guide`_) across all the LAVA component code.

``pylint`` does need to be used with some caution, the messages produced should
not be followed blindly. It can be very useful for spotting unused imports,
unused variables and other issues. To simplify the pylint output, some warnings
are recommended to be disabled::

 $ pylint -d line-too-long -d missing-docstring

.. note:: Docstrings should still be added wherever a docstring would
   be useful.

``pylint`` also supports local disabling of warnings and there are many
examples of:

.. code-block:: python

 variable = func_call()  # pylint: disable=

There is a ``pylint-django`` plugin available in unstable and testing and
whilst it improves the pylint output for the ``lava-server`` codebase, it still
has a high level of false indications.

pep8
****

In order to check for `PEP 008`_ compliance the following command is
recommended::

  $ pep8 --ignore E501

`pep8` can be installed in debian based systems as follows::

  $ apt install pep8

.. _unit_tests:

Unit-tests
**********

LAVA has set of unit tests which the developers can run on a regular basis for
each change they make in order to check for regressions if any. Most of the
LAVA components such as ``lava-server``, ``lava-dispatcher``, :ref:`lava-tool
<lava_tool>` have unit tests.

Extra dependencies are required to run the tests. On Debian based
distributions, you can install lava-dev.

To run the tests, use the ci-run / ci-build scripts::

  $ ./ci-run

.. _`Pylint`: https://www.pylint.org/
.. _`refactoring book`: http://www.refactoring.com/
.. _`PEP 008`: https://www.python.org/dev/peps/pep-0008/
.. _`Guido's style guide`: https://www.python.org/doc/essays/styleguide.html

.. seealso:: :ref:`developer_preparations` and :ref:`testing_pipeline_code` for
   examples of how to run individual unit tests or all unit tests within a
   class or module.

LAVA database model visualization
*********************************

LAVA database models can be visualized with the help of `django_extensions`_
along with tools such as `pydot`_. In debian based systems install the
following packages to get the visualization of LAVA database models:

.. code-block:: shell

 $ apt install python-django-extensions python-pydot

Once the above packages are installed successfully, use the following command
to get the visualization of ``lava-server`` models in PNG format:

.. code-block:: shell

 $ sudo lava-server manage graph_models --pydot -a -g -o lava-server-model.png

More documentation about graph models is available in
https://django-extensions.readthedocs.org/en/latest/graph_models.html

Other useful features from `django_extensions`_ are as follows:

* `shell_plus`_ - similar to the built-in "shell" but autoloads all models

* `validate_templates`_ - check templates for rendering errors:

  .. code-block:: shell

   $ sudo lava-server manage validate_templates

* `runscript`_ - run arbitrary scripts inside ``lava-server``
  environment:

  .. code-block:: shell

   $ sudo lava-server manage runscript fix_user_names --script-args=all

.. _`django_extensions`: https://django-extensions.readthedocs.org/en/latest/
.. _`pydot`: https://pypi.python.org/pypi/pydot
.. _`shell_plus`: https://django-extensions.readthedocs.org/en/latest/shell_plus.html
.. _`validate_templates`: https://django-extensions.readthedocs.org/en/latest/validate_templates.html
.. _`runscript`: https://django-extensions.readthedocs.org/en/latest/runscript.html

.. _developer_access_to_django_shell:

Developer access to django shell
********************************

Default configurations use a side-effect of the logging behaviour to restrict
access to the ``lava-server manage`` operations which typical Django apps
expose through the ``manage.py`` interface. This is because ``lava-server
manage shell`` provides read-write access to the database, so the command
requires ``sudo``.

On developer machines, this can be unnecessary. Set the location of the django
log to a new location to allow easier access to the management commands to
simplify debugging and to be able to run a Django Python Console inside a
development environment. In ``/etc/lava-server/settings.conf`` add::

 "DJANGO_LOGFILE": "/tmp/django.log"

.. note:: ``settings.conf`` is JSON syntax, so ensure that the previous line
   ends with a comma and that the resulting file validates as JSON. Use
   `JSONLINT <http://www.jsonlint.com>`_

The new location needs to be writable by the ``lavaserver`` user (for use by
localhost) and by the developer user (but would typically be writeable by
anyone).
