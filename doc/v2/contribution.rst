.. index:: contribution guide, jinja2 - development, developer, developer guide, develop

.. _contribution_guide:

LAVA Software Community Project Contribution Guide
##################################################

.. seealso:: :ref:`code_of_conduct`

.. index:: contribution guidelines

.. _contribution_guidelines:

About the Contribution Guidelines
*********************************

We want to make it as easy as possible for LAVA Software users to
become LAVA Software Community Project contributors, so we have created
this guide to help you get started.

The LAVA Software Community Project has published this Contribution
Guide, and all contributors will be expected to adhere to these
guidelines when submitting issues or merge requests. They are designed
to clarify the requirements for contributions, to make contributing
more efficient for all involved.

Following the guidelines is a great way to prevent your contributions
from being rejected or delayed. Most maintainers won't intend to
discredit your work or be tough on contributors. However, many are busy
and some may be working on LAVA in their free time. Well-formed
contributions are much easier to review and work with.

Conflicting priorities
======================

Sometimes a request will be turned down because of conflicting
priorities. It is important to talk about the reasons on the
:ref:`mailing list <mailing_lists>`. Whether you're requesting a new
feature, or providing a fix, remember that the maintainer has to weigh
up your contribution. They are the people who may have to support the
new code in the future, and resources are often scarce. Additionally,
it's important to understand whether a feature will be helpful to the
wider user community. Try not to be discouraged if your feature request
or merge request is turned down. Be open-minded and, if necessary,
propose an alternative idea on the mailing list after hearing their
concerns. It might not be clear why your change is helpful, so be ready
to discuss it and maybe re-design it to make it fit better.

.. _development_pre_requisites:

Pre-requisites to start with development
****************************************

* LAVA is written in Python_, so you will need to know (or be willing to
  learn) the language.

* Likewise, the web interface is a Django_ application so you will need
  to use and debug Django if you need to modify the web interface.

* LAVA uses YAML_ heavily internally, so you'll likely need to
  understand the `YAML Parser
  <http://yaml-online-parser.appspot.com/?yaml=&type=json>`_

* LAVA also uses Jinja2_.

* All LAVA software is maintained in git_, as are many of the support
  scripts, test definitions and job submissions.

* Some familiarity with Debian_ is going to be useful; helper scripts
  are available when preparing updated .deb packages based on your
  modifications.

LAVA is complex and designed to solve complex problems. This has
implications for how LAVA is developed, tested, deployed and used.

Other elements involved in LAVA development
===========================================

* The Django backend used with LAVA is PostgreSQL_ and some
  `postgres-specific support
  <https://www.postgresql.org/docs/9.5/static/rules-materializedviews.html>`_
  is used.

* The LAVA UI includes Javascript_ and CSS_.

* LAVA also uses ZMQ_ and XML-RPC_ and the LAVA documentation is
  written in reStructuredText (RST_).

In addition, test jobs and device support can involve use of:

* U-Boot_
* GuestFS_
* ADB_
* QEMU_
* Grub_
* SSH_
* LXC_
* Docker_

A very wide variety of other systems and tools are used to access
devices and debug test jobs.

.. _Python: http://www.python.org/
.. _Django: https://www.djangoproject.com/
.. _YAML: https://yaml.org/
.. _RST: http://sphinx-doc.org/rest.html
.. _Jinja2: http://jinja.pocoo.org/docs/dev/
.. _git: https://www.git-scm.org/
.. _PostgreSQL: https://www.postgresql.org/
.. _Debian: https://www.debian.org/
.. _Javascript: https://www.javascript.com/
.. _CSS: https://www.w3.org/Style/CSS/Overview.en.html
.. _GuestFS: http://libguestfs.org/
.. _ZMQ: http://zeromq.org/
.. _XML-RPC: http://xmlrpc.scripting.com/
.. _ADB: https://developer.android.com/studio/command-line/adb
.. _QEMU: http://wiki.qemu.org/Main_Page
.. _Grub: https://www.gnu.org/software/grub/
.. _U-Boot: http://www.denx.de/wiki/U-Boot
.. _SSH: http://www.openssh.com/
.. _POSIX: http://www.opengroup.org/austin/papers/posix_faq.html
.. _LXC: https://linuxcontainers.org/
.. _Docker: https://www.docker.com/

.. seealso:: :ref:`naming_conventions`

Updating online documentation
*****************************

LAVA documentation is written in reStructuredText, and then converted
into other formats using Sphinx. You can use the command below to
generate html format files for LAVA V2::

 $ make -C doc/v2 clean
 $ make -C doc/v2 html
 $ firefox doc/v2/_build/html/index.html
 (or whatever browser you prefer)

We welcome contributions to improve our documentation. If you are
considering adding new features to LAVA or changing current behavior,
also please ensure that the changes include matching updates for the
documentation. Great new features may go unused (or unmerged!) without
documentation to help people use them.

Wherever possible, all new sections of documentation should come with
worked examples.

* Add a testjob submission YAML file to ``doc/v2/examples/test-jobs``

* If the change relates to or includes particular test definitions to
  demonstrate the new support, add a test definition YAML file to
  ``doc/v2/examples/test-definitions``

* Use the `include options
  <http://docutils.sourceforge.net/docs/ref/rst/directives.html#include>`_
  supported in RST to quote snippets of the test job or test definition
  YAML, following the examples of the existing examples.

* Use comments **liberally** in the examples and link to existing terms
  and sections - make it easy for other people to understand how to use
  your new feature.

* Read the comments in the ``doc/v2/index.rst`` file if you are adding
  new pages or altering section headings.

.. _RST: http://sphinx-doc.org/rest.html

.. index:: contribution process

.. _lava_contribution_process:

The LAVA contribution process
*****************************

To contribute changes to LAVA, there is a simple process:

* :ref:`creating_gitlab_account`
* :ref:`request_gitlab_fork_permissions`
* :ref:`Fork the current code <fork_the_code>`
* :ref:`create_development_branch`
* :ref:`develop_your_changes`
* :ref:`dind_access`
* :ref:`push_development_branch`
* :ref:`submit_merge_request`
* :ref:`review_and_fix_mr`
* :ref:`developer_merging_changes`

.. note:: It is worth checking if someone already has a merge request
   which relates to your proposed changes. Check for open merge
   requests at https://git.lavasoftware.org/lava/lava/merge_requests

.. index:: gitlab account

.. _creating_gitlab_account:

Creating a GitLab Account
=========================

To be able to work with the LAVA Software Community Project, start by
creating an account on https://git.lavasoftware.org/lava/ . Fill in
details in your profile, and make sure you add a public SSH key to your
account. You will need that to be able to push code changes.

.. index:: gitlab fork permissions

.. _request_gitlab_fork_permissions:

Request GitLab Fork Permissions
===============================

Next, you will need to be given permissions to create forks of our
repositories on the LAVA GitLab instance
(https://git.lavasoftware.org/lava/). This is an unfortunate step that
has only become necessary recently - spammers and trolls are
everywhere on the Internet and will apparently abuse any resources
that are not locked down. :-(

To counter the spam problem, all new accounts are tagged as
``external`` by default, which means that they do not have permissions
to fork projects or create their own new projects. If you are
genuinely looking to work on LAVA, please `file an issue
<https://git.lavasoftware.org/lava/lava/issues/new>`_ to ask for
access once you have created your account. The GitLab admins should
respond quickly and give you access.

.. note:: To be able to later push changes and trigger CI, you will
	  also need to :ref:`request access <dind_access>` to the
	  ``DinD`` ("Docker in Docker") based CI
	  runners. Unfortunately, you can only do that once you have
	  created repositories within your account (e.g. by forking).

.. index:: forking the code

.. _fork_the_code:

Fork the code
=============

Fork the lava project in the GitLab web interface. This will set up a
copy of the lava project in your own personal namespace. From here, you
can create new branches as you like, ready for making changes.

.. index:: dind access, CI runner access

.. _dind_access:

Access to the CI runners
========================

If you want to contribute to LAVA projects, you will also need to ask
the GitLab admins to grant access to our ``DinD`` (Docker in Docker)
CI runners. Due to the way that permissions for CI runners is handled
within GitLab, this can **only** be done on a per-project basis rather
than by user account. It's therefore worth asking for this DinD access
straight away once you have made your first fork of each
repository. Please `file an issue
<https://git.lavasoftware.org/lava/lava/issues/new>`_ to ask for
access once you have forked. The GitLab admins should respond quickly
and give you access.

.. index:: development branch, git branch

.. _create_development_branch:

Create a development branch
===========================

Clone your fork of the lava software repository::

 $ git clone git@git.lavasoftware.org:yourname/lava.git

We recommend always making a new local branch for your changes::

 $ cd lava
 $ git switch -c my_branch

.. seealso:: https://docs.gitlab.com/ee/gitlab-basics/create-branch.html

.. index:: develop changes

.. _develop_your_changes:

Make, test and commit your changes
==================================

Make and test the changes you need. The details here are down to you!

When preparing changes, you will need to think about the LAVA design
and :ref:`criteria` which will be applied during the code review.

.. seealso:: :ref:`lava_development`

Use the normal git process to stage and commit the changes. Make sure
that your commit messages are suitable. They need to be clear and they
should describe *what* you've changed, and *why*:

https://chris.beams.io/posts/git-commit/

When you commit, use the ``--signoff`` or ``-s`` option to ``git
commit`` to acknowledge that you have the rights to submit this change
under the terms of the licenses applicable to the LAVA Software. This
is commonly known as the "Developer's Certificate of Origin" (DCO_),
and is used in a wide variety of other Open Source projects like the
Linux kernel.

.. _DCO: https://developercertificate.org/

::

 $ git commit -s

::

 $ git commit --amend -s

GitLab supports including multiple commits in a single merge request,
so at this stage feel free to collect your changes in as many logical
changesets as you like. Don't include unrelated changes - use a
separate branch (and therefore a separate merge request) instead.

.. seealso:: :ref:`Making changes in git <making_git_changes>`

.. index:: push development branch

.. _push_development_branch:

Push your changes to your development branch
============================================

Use ``git push`` to publish the changes on your branch back to your own
fork. This will share the code with other developers. In this example,
replace ``my_username`` with the username of the fork and ``my_branch``
with the name of the local branch which will be pushed to that fork::

 $ git push --set-upstream my_username my_branch
 Enumerating objects: 9, done.
 Counting objects: 100% (9/9), done.
 Delta compression using up to 4 threads
 Compressing objects: 100% (4/4), done.
 Writing objects: 100% (5/5), 430 bytes | 430.00 KiB/s, done.
 Total 5 (delta 3), reused 0 (delta 0)
 remote:
 remote: To create a merge request for my_branch, visit:
 remote:   https://git.lavasoftware.org/my_username/lava/merge_requests/new?merge_request%5Bsource_branch%5D=my_branch
 remote:
 To git.lavasoftware.org:my_username/lava.git
 * [new branch]          my_branch -> my_branch
 Branch 'my_branch' set up to track remote branch 'my_branch' from 'my_username'.

You can push here as many times as you like, as you make more changes.

Pushing to your fork will trigger the CI process - your changes will
now be automatically tested and the results will be displayed for the
MR. You will also receive email to tell you how things went.

.. index:: submit merge request

.. _submit_merge_request:

Submit a Merge Request (MR)
===========================

When your code is clean and ready to be reviewed, create a merge
request against the *master* branch of the original lava project.
GitLab will track all the changes that you have pushed to your
development branch, and present them together for review in one
patchset. To create the MR, use the link that gitlab gave you when you
pushed your branch or visit the "Merge Requests" area in the web UI.

It is useful to select both these options in GitLab when creating or
editing a merge request:

* Remove source branch when merge request is accepted.

* Allow commits from members who can merge to the target branch.

By allowing commits, reviewers can make small changes themselves, to
correct typos etc., without needing to start a new discussion.

Changes will only be merged after a merge request is created and
the CI process for that MR has passed.

https://docs.gitlab.com/ee/gitlab-basics/add-merge-request.html

There are six headlines that we expect in each merge request, so that
we have all the information we need to understand the purpose of the
proposed change.

.. note:: Not all of these headlines need to appear in a git commit
   message. Screenshots and points for checking need to go into the
   comments on the merge request itself.

In the git commit message:

#. What does this change do?

#. Why was this change needed?

#. What are the relevant issue numbers?

In the merge request, as comments:

4. Are there points in the code the reviewer needs to double check?

#. Screenshots or test job log files as links or attachments (if
   relevant)

#. If helpful, links to external resources like gold standard images to
   demonstrate how to use and/or test a new feature.

Once you are familiar with creating merge requests, you can also set
labels to help reviewers identify the type of change to be reviewed.

.. index:: developer: reviewing merge requests

.. _review_and_fix_mr:

MRs are reviewed (and rebased and reworked as needed)
=====================================================

If your MR failed its tests, you will receive a detailed email
explaining where the failures occurred. It is up to you to make any
fixes required.

.. seealso:: :ref:`developer_commit_for_review`

If you are not sure how to fix things here, please ask for help!

Fixes for test failures should be pushed to the same GitLab branch.
Each time you push, GitLab will automatically update your related merge
request and re-run the CI loop. As and when the code is functional,
maintainers will comment on your changes and if all is well they will
approve the merge. They may also ask you to make more changes - this is
an iterative process.

.. index:: developer - merging_changes

.. _developer_merging_changes:

How changes get merged
======================

As the final step in merging a change, we will want the list of commits
in the merge request to be squashed. The objective here is to ensure
that each commit on the master branch is clean and intact, while also
keeping logical changes in separate commits. You can use ``git rebase
-i HEAD~5`` or equivalent support for squashing git commits.

* Ensure that commits to fix unit test failures, CI failures or other
  breakage are squashed into the parent commit.

* Ensure that separate logical changes remain as separate commits. It
  is often easier to use separate branches for this reason.

* Ensure that your commits are all rebased onto the current master
  branch

Pushing the squashed branch will need you to use ``git push --force``
to replace the existing commits in your merge request. The merge
request will get one final code review and if a Maintainer approves of
the final state, the change will be merged when the CI completes
successfully.

.. caution:: This is the **only** time that ``git push --force`` is
   ever recommended. Forcing a push makes it hard for other
   contributors to work on the changes by triggering lots of merge
   conflicts.
