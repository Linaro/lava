.. index:: developing LAVA

.. _lava_development:

LAVA development
################

Before you start, ensure you've read the
:ref:`development_pre_requisites` and :ref:`criteria`.

.. seealso:: :ref:`contribute_upstream`

.. _development_workflow:

Patch Submissions and workflow
******************************

This is a short guide on how to send your patches to LAVA. The LAVA
team uses the gerrit_ code review system to review changes.

.. _gerrit: https://review.linaro.org/

If you do not already have a Linaro account, you will first need to
:ref:`register`.

So the first step will be logging in to gerrit_ and uploading you SSH
public key there.

Obtaining the repository
========================

There is a single LAVA codebase, including the code available as
``lava-server`` and ``lava-dispatcher`` binary packages.

::

    git clone https://git.linaro.org/git/lava/lava.git
    cd lava

There is also ``lavacli`` which is gaining more support for operations
involving the :ref:`dispatcher_design`::

    git clone https://git.linaro.org/git/lava/lavacli.git
    cd lavacli

Setting up git-review
=====================

If you have not done so already, ``git review`` needs to be setup for
each clone of each source::

    git review -s

.. _developer_topic_branches:

Create a topic branch
=====================

We recommend **never** working off the master branch (unless you are a
git expert and really know what you are doing). You should create a
topic branch for each logically distinct change you work on.

.. note:: Unless your change **directly** depends on changes made in an
   earlier commit on a branch, this means making a fresh branch for
   each change with **one commit** per branch.

.. seealso:: :ref:`developer_submitting_new_version` and
   :ref:`developer_submitting_new_version`

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

..seealso:: :ref:`testing_pipeline_code` and
  :ref:`developer_preparations`

Static code analysis
====================

It is essential to run ``pep8 --ignore E501`` routinely on your local
changes as ``./ci-run`` will fail on any PEP8 errors. All automated
tests occur using Debian Stretch.

It is important to run tools like :ref:`pylint3 <pylint_tool>`,
particularly when adding new files, to check for missing or unused
imports. Other analysis tools should also be used, for example from
within your IDE.

Functional testing
==================

Unit tests cannot replicate all tests required on LAVA code, some tests
will need to be run with real devices under test. On Debian based
distributions, see :ref:`dev_builds`. See :ref:`writing_tests` for
information on writing LAVA test jobs to test particular device
functionality.

Make your changes
=================

* Follow PEP8 style for Python code.
* Make one commit (and hence one review) per logical change.
* Use one topic branch for each logical change.
* Include unit tests in the commit of the change being tested.
* Write good commit messages. There are a number of useful guides:

  * `A note about git commit messages`_
  * `5 useful tips for a better commit message`_

  * Avoid putting documentation into the commit message. Keep the
    commit message to a reasonable length (about 10 to 12 lines at
    most).

  * Usage examples need to go into the documentation, not the commit
    message. Everything which is intended to help users to add this
    support to their own test jobs must be in the documentation.

  * Avoid duplicating or summarising the documentation in the commit
    message, reviewers will be reading the documentation as well.

  * Use comments in the code in preference to detailed commit messages.

  * Avoid putting updates into the commit message for each patch set.
    The review comments are the correct place for details of what
    changed at which patch set.

.. _`A note about git commit messages`:
   http://tbaggery.com/2008/04/19/a-note-about-git-commit-messages.html

.. _`5 useful tips for a better commit message`:
   https://robots.thoughtbot.com/post/48933156625/5-useful-tips-for-a-better-commit-message

.. index:: developer: adding unit tests

.. _developer_adding_unit_tests:

Add some unit tests
===================

Some changes will **always** need additional unit tests and reviews
will not be merged without this support. The purpose is to ensure that
future changes in the codebase have some assurance that existing
support has not been affected. The intent is that as much as possible
of the test job and device configuration is covered by at least one
unit test. Some examples include:

# Changes to an existing jinja2 device-type template which change the
  output YAML of the device configuration need a unit test to show that
  the change is being included.

# Adding a new deployment or boot method needs unit tests (including
  sample test jobs) which check that all ``validate()`` functions work
  correctly and particular tests checking for the specific details of
  the new method.

# Adding a change to an existing deployment or boot method which
  changes the construction of the pipeline based on test job or device
  configuration. Unit tests will be required to show that the change is
  being made.

Reviewers may ask for unit test support for any change, so :ref:`talk
to us <getting_support>` during development. You can also use an
``RFC`` prefix in your git commit to indicate that the change is not
ready for merging but is ready for comments.

lava_dispatcher
---------------

Whenever new functionality is added to ``lava_dispatcher``, especially
a new :ref:`Strategy class <using_strategy_classes>`, there **must** be
some new unit tests added to allow some assurance that the new classes
continue to operate as expected as the rest of the codebase continues
to develop. There are a lot of examples in the current unit tests.

#. Start with a sample test job which is known to work. Copy that into
   ``lava_dispatcher/tests/sample_jobs``. The URLs in that sample job
   will need to be valid URLs but do not need to be working files.
   (This sample_job is not being submitted to run on a device, it is
   only being used to check that the construction of the pipeline is
   valid.) If you need files which other sample jobs do not use then
   :ref:`we can help with that <getting_support>` by putting files onto
   images.validation.linaro.org.

#. Use the updated ``Factory`` support to generate the device
   configuration directly from the ``lava_scheduler_app`` templates.

   If a suitable device dictionary does not already exist in
   ``lava_scheduler_app/tests/devices``, a new one can be added to
   support the unit tests.

#. Add a function to a suitable Factory class to use the device config
   file to create a device and use the parser to create a Job instance
   by following the examples in the existing unit tests

#. Create the pipeline ref by following the ``readme.txt`` in the
   ``pipeline_ref`` directory. The simplest way to create a single new
   pipeline reference file is to add one line to the new unit test
   function:

   .. code-block:: python

    self.update_ref = True

   Run the unit test and the pipeline reference will be created. Remove
   the line before committing for review or the ``./ci-run`` check will
   fail.

   This file acts as a description of the classes involved in the
   pipeline which has been constructed from the supplied test job and
   device configuration. Validating it in the unit tests ensures that
   later development does not invalidate the new code by accidentally
   removing or adding unexpected actions.

#. In the new function, use the ``pipeline_refs`` README to add a check
   that the pipeline reference continues to reflect the pipeline which
   has been constructed by the parser.

.. note:: unit tests do not typically check any of the ``run`` function
   code. Do as much checking as is practical in the ``validate``
   functions of all the new classes. For example, if ``run`` relies on
   a parameter being set, check for that parameter in ``validate`` and
   check that the value of that parameter is correct based on the
   sample job and the supplied device configuration.

lava_scheduler_app
------------------

Some parts of lava_scheduler_app are easier to test than others. New
device-type templates need to have specific unit tests added to
``lava_scheduler_app/tests/test_templates`` or one of the relevant
specialist template unit test files. Follow the examples and make sure
that if the new template adds new items then those items are checked
for existence and validity in the new function which tests the new
template.

.. code-block:: shell

 $ python3 -m unittest -vcf lava_scheduler_app.tests.test_fastboot_templates

 $ python3 -m unittest -vcf lava_scheduler_app.tests.test_qemu_templates

 $ python3 -m unittest -vcf lava_scheduler_app.tests.test_uboot_templates

If you are adding or modifying documentation in ``lava-server``, make sure that
the documentation builds cleanly:

.. code-block:: none

 $ make -C doc/v2 clean
 $ make -C doc/v2 html

For other parts of ``lava-server``, follow the examples of the existing unit
tests and :ref:`talk to us <getting_support>`.

Re-run the unit tests
=====================

Make sure that your changes do not cause any failures in the unit tests::

 $ ./ci-run

Wherever possible, always add new unit tests for new code.

Testing local changes
=====================

For any sufficiently large change, :ref:`building <dev_builds>` and
installing a new package on a local instance is recommended. Ensure
that the test instance is already running the most recent production
release.

If the test instance has a separate worker, ensure that the master and
the worker always have precisely the same code applied. For some
changes, it may be necessary to have a test instance which is a clone
of a production instance, complete with devices. **Never** make live
changes to a production instance. (This is why integrating new device
types into LAVA requires multiple devices.)

Once your change is working successfully:

#. Ensure that your local branch is clean - check for left over debug
   code.

#. Ensure that your local branch has been rebased against current
   ``master``

#. Build and install a package from the ``master`` branch. If you have
   added any new files in your local change, make sure these have been
   removed. Reproduce the original bug or problem.

#. Build and install a package from your local branch and repeat the tests.

lava_dispatcher
---------------

Changes to most files in ``lava_dispatcher`` can be symlinked or copied
into the packaged locations. e.g.::

 PYTHONDIR=/usr/lib/python3/dist-packages/
 sudo cp <path_to_file> $PYTHONDIR/<path_to_file>

.. note:: The path used for ``PYTHONDIR`` has changed with the LAVA
   runtime support moving to Python3 in 2018.4.

There is no need to copy files used solely by the unit tests.

Changes to files in ``./etc/`` will require restarting the relevant
service.

Changes to files in ``./lava/dispatcher/`` will need the ``lava-slave``
service to be restarted.

* When adding or modifying ``run``, ``validate``, ``populate`` or
  ``cleanup`` functions, **always** ensure that ``super`` is called
  appropriately, for example:

  .. code-block:: python

    super().validate()

    connection = super().run(connection, max_end_time)

* When adding or modifying ``run`` functions in subclasses of
  ``Action``, **always** ensure that each return point out of the
  ``run`` function returns the ``connection`` object:

  .. code-block:: python

    return connection

* When adding new classes, use **hyphens**, ``-``, as separators in
  ``self.name``, *not underscores*,  ``_``. The function will fail if
  underscore or whitespace is used. Action names need to all be
  lowercase and describe something about what the action does at
  runtime. More information then needs to be added to the
  ``self.summary`` and an extended sentence in ``self.description``.

  .. code-block:: python

    self.name = 'do-something-at-runtime'

  .. seealso:: :ref:`developing_new_classes`

* Use **namespaces** for all dynamic data. Parameters of actions are
  immutable. Use the namespace functions when an action needs to store
  dynamic data, for example the location of files which have been
  downloaded to temporary directories, Do not access ``self.data``
  directly (except for use in iterators). Use the get and set
  primitives, for example:

  .. code-block:: python

   set_namespace_data(action='boot', label='shared', key='boot-result', value=res)

   image_arg = self.get_namespace_data(action='download-action', label=label, key='image_arg')

lava-server
-----------

Changes to device-type templates and device dictionaries take effect
immediately, so simply submitting a test job will pick up the latest
version of the code in
``/etc/lava-server/dispatcher-config/device-types/``. Make changes to
the templates in ``lava_scheduler_app/tests/device-types/``. Check them
using the ``test_all_templates`` test, and only then copy the updates
into ``/etc/lava-server/dispatcher-config/device-types/`` when the
tests pass.

.. seealso:: :ref:`testing_new_devicetype_templates`

Changes to django templates can be applied immediately by copying the
template into the packaged path, e.g. html files in
``lava_scheduler_app/templates/lava_scheduler_app/`` can be copied or
symlinked to
``/usr/lib/python3/dist-packages/lava_scheduler_app/templates/lava_scheduler_app/``

.. note:: The path changed when the LAVA runtime support moved to
   Python3 with the 2018.4 release.

Changes to python code generally require copying the files and
restarting the ``lava-server-gunicorn`` service before the changes will
be applied::

 sudo service lava-server-gunicorn restart

Changes to ``lava_scheduler_app/models.py``,
``lava_scheduler_app/db_utils.py`` or ``lava_results_app/dbutils`` will
require restarting the ``lava-master`` service::

 sudo service lava-master restart

Changes to files in ``./etc/`` will require restarting the relevant
service. If multiple services are affected, it is normally best to
build and install a new package.

:ref:`database_migrations` are a complex area - read up on the django
documentation for migrations. Instead of ``python ./manage.py``, use
``sudo lava-server manage``.

lava-server-doc
---------------

Documentation files in ``doc/v2`` can be built locally in the git
checkout using ``make``::

 make -C doc/v2 clean
 make -C doc/v2 html

Files can then be checked in a web browser using the ``file://`` url
scheme and the ``_build/html/`` subdirectory. For example:
``file:///home/neil/code/lava/lava-server/doc/v2/_build/html/first_steps.html``

Some documentation changes can add images, example test jobs, test
definitions and other files. Depending on the type of file, it may be
necessary to make changes to the packaging, so :ref:`talk to us
<getting_support>` before making such changes.

Documentation is written in RST, so the `RST Primer
<http://www.sphinx-doc.org/en/stable/rest.html>`_ is essential reading
when modifying the documentation.

#. Keep all documentation paragraphs wrapped to 80 columns.

#. Use ``en_GB`` unless referring to elements of code which use
   ``en_US``.

#. Use syntax highlighting for code and check the rendered page. For
   example, ``code-block:: shell`` relates to the contents of shell
   scripts, not the output of commands or scripts in a shell (those
   should use ``code-block:: none``)

#. Wherever possible, pull in code samples from working example files
   so that these can be checked for accuracy on `staging
   <https://staging.validation.linaro.org/>`_ before future releases.

.. _developer_commit_for_review:

Send your commits for review
============================

From each topic branch, just run::

    git review

If you have multiple commits in that topic branch, git review will warn
you. It's OK to send multiple commits from the same branch, but note
that:

#. commits are review and approved individually and

#. later commits  will depend on earlier commits, so if a later commit
   is approved and the one before it is not, the later commit will not
   be merged until the earlier one is approved.

#. you are responsible for **rebasing** your branch(es) against updates
   on master and this can become **much** more difficult when there are
   multiple commits on one local branch. It can become a **lot** of
   work to make the correct changes in the correct commit on a single
   branch.

#. Fixes from comments or unit test failures in one review are **not**
   acceptable as separate reviews, so don't be tempted to make another
   commit at the top of the branch.

#. It is common for reviews to go through repeated cycles of comments
   and updates. This is not a reflection on the usefulness of the
   change or on any particular contributors, it is a natural evolution
   of the code. Comments may reflect changes being made in other
   parallel reviews or reviews merged whilst this change was being
   reviewed. Contributors may be added to other reviews where the team
   consider this to be useful for feedback or where the documentation
   is being updated in areas which relate to your change. The number of
   comments per review is no indication of the quality of that review
   and does not affect when the review would be merged.

#. It is common for changes to develop merge conflicts during the
   review process as other reviews are merged. Unfortunately, gerrit
   does **not** email reviewers when a review gains a merge conflict.
   The team will usually *ping* the review if it looks like the
   reviewer has not noticed a merge conflict when the review is
   considered ready to be merged.

#. If a review has been given ``-1`` by ``lava-bot``, a reviewer or the
   author, the team will generally ignore that review unless it relates
   to parallel work on a bug fix or other feature.

Therefore the recommendations are:

#. **Always** use a separate local branch per commit

#. Think carefully about whether to base one local branch on another
   local branch. This is recommended when one change logically extends
   an earlier change and makes it a lot easier than having multiple
   commits on a single branch.

#. Keep all your branches up to date with master **regularly**. It is
   much better to resolve merge conflicts one change at a time instead
   of having multiple merge commits all in the one rebase operation.

#. Check gerrit intermittently and ensure that you address **all**
   comments on the review. LAVA software releases tend to be within the
   first week of the month. Towards the end of each month, pay
   particular attention to comments made in gerrit and check if your
   review has gained a merge conflict. Resolving these problems will
   make it easier to get your change into the next LAVA release.

.. _developer_adding_reviewers:

Adding reviewers
================

Reviews submitted for ``lava`` and ``lavacli`` will **automatically**
have the LAVA software team added as reviewers when the review is first
submitted.

Other reviewers can also be added to individual reviews. The Owner of
the review is always added. Reviewers will get email for all changes
relating to that review. All reviewers need to :ref:`register`, email
will go to the ``@linaro.org`` account of that reviewer.

If you know that there are still problems to fix in the review, please
use the Gerrit interface to reply to the review and give the review a
score of ``-1`` and summarize your concerns in the comment. This
indicates to the software team that this review should not be
considered for merging into master at this time. You may still get
comments.

Optionally, you can put ``[RFC]`` or similar at the start of your git
commit message and then amend the message when the review is ready to
merge.

.. _developer_submitting_new_version:

Submitting a new version of a change
====================================

When reviewers make comments on your change, you should amend the
original commit to address the comments, and **not** submit a new
change addressing the comments while leaving the original one
untouched.

Gerrit handles this by adding a ChangeId to your commit message. Keep
this Id unchanged when amending commit messages.

Locally, you can make a separate commit addressing the reviewer
comments, it's not a problem. But before you resubmit your branch for
review, you have to rebase your changes against master to end up with a
single, enhanced commit. For example::

    $ git branch
      master
    * my-feature
    $ git show-branch master my-feature
    ! [master] Last commit on master
     ! [my-feature] address reviewer comments
    --
     + [my-feature] address reviewer comments
     + [my-feature^] New feature or bug fix
    -- [master] Last commit on master
    $ git rebase -i master


``git rebase -i`` will open your ``$EDITOR`` and present you with
something like this::

    pick xxxxxxx New feature or bug fix
    pick yyyyyyy address reviewer comments

You want the last commit to be combined with the first and keep the
first commit message, so you change ``pick`` to ``fixup`` ending up
with something like this::

    pick xxxxxxx New feature or bug fix
    fixup yyyyyyy address reviewer comments

If you also want to edit the commit message of the first commit to
mention something else, change ``pick`` to ``reword`` and you will have
the chance to do that. Just remember to keep the ``Change-Id``
unchanged.

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
still contains the same ``Change-Id``, gerrit will know it is a new
version of a previously submitted change.

Handling your local branches
============================

After placing a few reviews, there will be a number of local branches.
To keep the list of local branches under control, the local branches
can be easily deleted after the merge. Note: git will warn if the
branch has not already been merged when used with the lower case ``-d``
option. This is a useful check that you are deleting a merged branch
and not an unmerged one, so work with git to help your workflow.

::

    $ git checkout bugfix
    $ git rebase master
    $ git checkout master
    $ git branch -d bugfix


If the final command fails, check the status of the review of the
branch. If you are completely sure the branch should still be deleted
or if the review of this branch was abandoned, use the `-D` option
instead of `-d` and repeat the command.

Reviewing changes in clean branches
===================================

If you haven't got a clone handy on the instance to be used for the
review, prepare a clone as usual.

Gerrit provides a number of ways to apply the changes to be reviewed,
so set up a test branch as usual - always ensuring that the master
branch of the clone is up to date before creating the review branch.

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

Future proofing
***************

All developers are encouraged to write code with futuristic changes in
mind, so that it is easy to do a technology upgrade, which includes
watching for errors and warnings generated by dependency packages as
well as upgrading and migrating to newer APIs as a normal part of
development.

This is particularly true for Django where the ``lava-server`` package
needs to retain support for multiple django versions as well as
monitoring for deprecation warnings in the newest django version. Where
necessary, write code for different versions and separate with:

.. code-block:: python

 import django
 if django.VERSION > (1, 8):
     pass  # newer code
 else:
     pass  # older compatibility code

.. _use_templates_in_dispatcher:

Use templates to generate device configuration
**********************************************

One of the technical reasons to merge the lava-dispatcher and
lava-server source trees into a single source is to allow
lava-dispatcher to use the output of the lava-server templates in
development. Further changes are being made in this area to provide a
common module but it is already possible to build a lava_dispatcher
unit test which pulls device configuration directly from the templates
in lava_scheduler_app. This removes the problem of static YAML files in
``lava_dispatcher/devices`` getting out of date compared to the actual
YAML created by changes in the templates.

The YAML device configuration is generated from a device dictionary in
``lava_scheduler_app`` which extends a template in
``lava_scheduler_app`` - the same template which is used at runtime on
LAVA instances. Any change to the template or device dictionary is
immediately reflected in the YAML sent to the ``lava_dispatcher`` unit
test.

.. code-block:: python

    import unittest
    from lava_dispatcher.test.test_basic import Factory, StdoutTestCase
    from lava_dispatcher.test.utils import infrastructure_error_multi_paths

    class TestFastbootDeploy(StdoutTestCase):  # pylint: disable=too-many-public-methods

        def setUp(self):
            super().setUp()
            self.factory = Factory()

        @unittest.skipIf(infrastructure_error_multi_paths(
            ['lxc-info', 'img2simg', 'simg2img']),
            "lxc or img2simg or simg2img not installed")
        def test_lxc_api(self):
            job = self.factory.create_job('d02-01.jinja2', 'sample_jobs/grub-ramdisk.yaml')


.. _database_migrations:

Database migrations
*******************

The LAVA team recommend using Debian stable but also support testing
and unstable which have a newer version of `python-django
<https://tracker.debian.org/pkg/python-django>`_.

Database migrations on Debian Jessie and later are managed within
django. Support for `python-django-south
<https://tracker.debian.org/pkg/python-django-south>`_ has been
**dropped**. **Only django** migration types should be included in any
reviews which involve a database migration.

Once modified, the updated ``models.py`` file needs to be copied into
the system location for the relevant extension, e.g.
``lava_scheduler_app``. This is a step which needs to be done by the
developer - developer packages **cannot** be installed cleanly and
**unit tests will likely fail** until the migration has been created
and applied.

On Debian Jessie and later::

 $ sudo lava-server manage makemigrations lava_scheduler_app

The migration file will be created in
``/usr/lib/python3/dist-packages/lava_scheduler_app/migrations/``
(which is why ``sudo`` is required) and will need to be copied into
your git working copy and added to the review.

The migration is applied using::

 $ sudo lava-server manage migrate lava_scheduler_app

See `django docs
<https://docs.djangoproject.com/en/1.8/topics/migrations/>`_ for more
information.

Python 3.x
**********

Python3 support in LAVA is related to a number of factors:

* Forthcoming LTS releases of django which will remove support for
  python2.7

* Debian Jessie is now unsupported and development has moved to
  Stretch.

* Transition within Debian to full python3 support.

https://lists.linaro.org/pipermail/lava-announce/2017-June/000032.html

https://lists.linaro.org/pipermail/lava-announce/2018-January/000046.html

lava-dispatcher and lava-server now fully support python3, runtime and
testing. Code changes to either codebase **must** be Python3
compatible.

All reviews run the ``lava-dispatcher`` and ``lava-server`` unit tests
against python 3.x and changes must pass all unit tests.

The ``./ci-run`` script for ``lava-dispatcher`` and ``lava-server`` can
run the unit tests using Python3::

 ./ci-run -a

Some additional Python3 dependencies will be required. In particular,
``python3-django-auth-ldap`` and ``python3-django-testscenarios`` will
need to be installed from ``stretch-backports``.

.. warning:: Django wil be dropping python2.7 support with the 2.2LTS
   release, *frozen* instances of LAVA will not be able to use django
   updates after that point.

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

#. Catch exceptions for all errors, ``SubmissionException``,
   ``DoesNotExist`` and others, then re-raise as
   ``xmlrpc.client.Fault``.

#. Move as much of the work into the relevant app as possible, either
   in ``models.py`` or in ``dbutils.py``. Wherever possible, re-use
   existing functions with wrappers for error handling in the API code.

.. _lava_instance_settings:

Instance settings
*****************

``/etc/lava-server/instance.conf`` is principally for V1 configuration.
V2 uses this file only for the database connection settings on the
master, instance name and the ``lavaserver`` user.

Most settings for the instance are handled inside django using
``/etc/lava-server/settings.conf``. (For historical reasons, this file
uses **JSON** syntax.)

.. seealso:: :ref:`branding`, :ref:`django_debug_toolbar` and
   :ref:`developer_access_to_django_shell`

.. _pylint_tool:

Pylint3
*******

`Pylint`_ is a tool that checks for errors in Python code, tries to
enforce a coding standard and looks for bad code smells. We encourage
developers to run LAVA code through pylint and fix warnings or errors
shown by pylint to maintain a good score. For more information about
code smells, refer to Martin Fowler's `refactoring book`_. LAVA
developers stick on to `PEP 008`_ (aka `Guido's style guide`_) across
all the LAVA component code.

``pylint3`` does need to be used with some caution, the messages
produced should not be followed blindly. It can be very useful for
spotting unused imports, unused variables and other issues. To simplify
the pylint output, some warnings are recommended to be disabled::

 $ pylint3 -d line-too-long -d missing-docstring

.. note:: Docstrings should still be added wherever a docstring would
   be useful.

Many developers use a ``~/.pylintrc`` file which already includes a
sample list of warnings to disable. Other warnings frequently disabled
in ``~/.pylintrc`` include:

.. code-block:: none

        too-many-locals,
        too-many-ancestors,
        too-many-arguments,
        too-many-instance-attributes,
        too-many-nested-blocks,
        too-many-return-statements,
        too-many-branches,
        too-many-statements,
        too-few-public-methods,
        wrong-import-order,
        ungrouped-imports,

``pylint`` also supports local disabling of warnings and there are many
examples of:

.. code-block:: python

 variable = func_call()  # pylint: disable=

There is a ``pylint-django`` plugin available in unstable and testing
and whilst it improves the pylint output for the ``lava-server``
codebase, it still has a high level of false indications, particularly
when extending an existing model.

pep8
****

In order to check for `PEP 008`_ compliance the following command is
recommended::

  $ pep8 --ignore E501

`pep8` can be installed in Debian based systems as follows::

  $ apt install pep8

.. index:: unit tests

.. _unit_tests:

Unit-tests
**********

LAVA has set of unit tests which the developers can run on a regular
basis for each change they make in order to check for regressions if
any. Most of the LAVA components such as ``lava-server``,
``lava-dispatcher``, :ref:`lava-tool <lava_tool>` have unit tests.

Extra dependencies are required to run the tests. On Debian based
distributions, you need to install ``lava-dev`` and
``python3-django-testscenarios``.

.. seealso:: :ref:`unit_test_dependencies`

To run the tests, use the ci-run / ci-build scripts::

  $ ./ci-run

.. _`Pylint`: https://www.pylint.org/
.. _`refactoring book`: http://www.refactoring.com/
.. _`PEP 008`: https://www.python.org/dev/peps/pep-0008/
.. _`Guido's style guide`: https://www.python.org/doc/essays/styleguide.html

.. seealso:: :ref:`developer_preparations`,
   :ref:`unit_test_dependencies` and :ref:`testing_pipeline_code` for
   examples of how to run individual unit tests or all unit tests
   within a class or module.

LAVA database model visualization
*********************************

LAVA database models can be visualized with the help of
`django_extensions`_ along with tools such as `pydot`_. In Debian based
systems install the following packages to get the visualization of LAVA
database models:

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

Default configurations use a side-effect of the logging behaviour to
restrict access to the ``lava-server manage`` operations which typical
Django apps expose through the ``manage.py`` interface. This is because
``lava-server manage shell`` provides read-write access to the
database, so the command requires ``sudo``.

On developer machines, this can be unnecessary. Set the location of the
django log to a new location to allow easier access to the management
commands to simplify debugging and to be able to run a Django Python
Console inside a development environment. In
``/etc/lava-server/settings.conf`` add::

 "DJANGO_LOGFILE": "/tmp/django.log"

.. note:: ``settings.conf`` is JSON syntax, so ensure that the previous
   line ends with a comma and that the resulting file validates as
   JSON. Use `JSONLINT <http://www.jsonlint.com>`_

The new location needs to be writable by the ``lavaserver`` user (for
use by localhost) and by the developer user (but would typically be
writeable by anyone).
