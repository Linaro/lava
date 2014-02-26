LAVA development
################

.. Resource: Various places in the wiki

Understanding the LAVA architecture
***********************************

The first step for LAVA development is understanding its architecture.
The major LAVA components are depicted below::

                  +-------------+
                  |web interface|
                  +-------------+
                         |
                         v
                     +--------+
               +---->|database|
               |     +--------+
               |
   +-----------+------[worker]-------------+
   |           |                           |
   |  +----------------+     +----------+  |
   |  |scheduler daemon|---→ |dispatcher|  |
   |  +----------------+     +----------+  |
   |                              |        |
   +------------------------------+--------+
                                  |
                                  V
                        +-------------------+
                        | device under test |
                        +-------------------+

* The *web interface* is responsible for user interaction, including
  presenting test jobs results, navigating devices, and receiving job
  submissions through it's XMLRPC API. It stores all data, including
  submitted jobs, into the *RDBMS*.
* The *scheduler daemon* is responsible for allocating jobs that were
  submitted. It works by polling the database, reserving devices to run
  those jobs, and triggering the dispatcher to actually run the tests.
* The *dispatcher* is responsible for actually running the job. It will
  manage the serial connection to the :term:`DUT`, image downloads and
  collecting results etc. When doing local tests or developing new
  testing features, the dispatcher can usually be run standalone without
  any of the other components.

On single-server deployments, both the web interface and the worker
components (scheduler daemon + dispatcher) run on a same server. You can
also install one or more separated worked nodes, that will only run
scheduler daemon + dispatcher. Learn more about that on
:ref:`lava-deployment-tool`.

Pre-requisites to start with development
****************************************

LAVA is written in Python_, so you will need to know (or be willing to
learn) Python_. Likewise, the web interface is a Django_ application so
you will need to Django if you need to modify the web interface.

.. _Python: http://www.python.org/
.. _Django: https://www.djangoproject.com/

Also, you will need git_.

.. _git: http://www.git-scm.org/


Setting up a development environment
************************************

LAVA is tested on Ubuntu 12.04, so that's the recommended deployment
environment. Likewise, when developing LAVA you should test against
Ubuntu 12.04.

The best way to create a development environment is to install a LAVA
instance in development mode::

    $ lava-deployment-tool --developer-mode development

In the above example our development instance is conveniently callled
"development".

The next step is to install a local repository into the instance. Let's
exemplify that with lava-server here, but you can do the same for
lava-dispatcher as well.

The first step is to clone the repository locally::

    $ git clone http://git.linaro.org/git-ro/lava/lava-server.git

Then install your local repository into the instance with::

    $ /srv/lava/instances/development/bin/lava-develop-local /path/to/lava-server

With the above command, your LAVA instance will use your local
lava-server copy at `/path/to/lava-server` as the source for the
corresponding component.

Example: making a change to lava-server
***************************************

*TODO*

Contributing Upstream
*********************

The best way to protect your investment on LAVA is to contribute your
changes back. This way you don't have to maintain the changes you need
by yourself, and you don't run the risk of LAVA changed in a way that is
incompatible with your changes.

Patch Submissions and workflow
==============================

This is a short guide on how to send your patches to LAVA. The LAVA team
uses the gerrit_ code review system to review changes.

.. _gerrit: http://review.linaro.org/

So the first step will be logging in to gerrit_ and uploading you SSH
public key there.

Obtaining the repository
^^^^^^^^^^^^^^^^^^^^^^^^

Let's say you want to contribute to ``lava-server``.

::

    git clone http://git.linaro.org/git-ro/lava/lava-server.git
    cd lava-server


Setting git-review up
^^^^^^^^^^^^^^^^^^^^^

::

    git review -s

Create a topic branch
^^^^^^^^^^^^^^^^^^^^^

We recommend never working off the master branch (unless you are a git
expert and really know what you are doing). You should create a topic
branch for each logically distinct change you work on.

Before you start, make sure your master branch is up to date::


    git checkout master
    git pull

Now create your topic branch off master::

    git checkout -b my-change master

Make your changes
^^^^^^^^^^^^^^^^^

* Follow PEP8 style for Python code.
* Make one commit per logical change.
* Write good commit messages. Useful reads on that topic:

 * `A note about git commit messages`_
 * `5 useful tips for a better commit message`_


.. _`A note about git commit messages`: http://tbaggery.com/2008/04/19/a-note-about-git-commit-messages.html

.. _`5 useful tips for a better commit message`: http://robots.thoughtbot.com/post/48933156625/5-useful-tips-for-a-better-commit-message

Send your commits for review
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

From your topic branch, just run::

    git review

If you have multiple commits in that topic branch, git review will warn
you. It's OK to send multiple commits from the same branch, but note
that 1) commits are review and approved individually and 2) later
commits  will depend on earlier commits, so if a later commit is
approved and the one before it is not, the later commit will not be
merged until the earlier one is approved.

Submitting a new version of a change
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

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
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

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
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

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


Adding support for new devices
******************************

.. TODO

to LAVA - Board addition howto?
Requirements for a device in LAVA

What do I need to create atest image for LAVA?
What do I need to create a master image for LAVA?
* 8GB SD Card

Writing LAVA extensions
***********************

*TODO*


API Docs
********

*Coming soon*.

..
  TODO determine with classes (and from which components) we want to document
  TODO figure out how to actually make the modules available in the l-d-t tree (or in the path)

