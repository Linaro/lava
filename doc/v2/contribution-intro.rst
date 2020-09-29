.. index:: contribution guide - for first timers

.. _contribution_guide_intro:

LAVA Software Project Contribution - Introduction
#################################################

There are clear benefits to contributing to open-source projects like
the LAVA Software Community Project. You may solve your own problems
more quickly than working alone, and you may also have a positive
effect on your favorite projects.

LAVA is complex and it can be hard to get started as a contributor. If
this is your first time contributing to open source, there may be
easier projects to choose. If you have contributed to a project
before, the temptation might be to immediately start thinking about
adding a new device to LAVA. Beware: device integration is **the most
difficult way to contribute** to the LAVA Software Community
Project. Our recommendation is to start slowly, get familiar with
devices like QEMU or LXC first and learn how to design a Test Plan
which suits your needs.

Before you start
****************

Read up on LAVA:

* :ref:`lava_overview` - especially :ref:`overview_preparation`.

You don't have to install LAVA to contribute to the LAVA Software
Community Project, depending on how you choose to contribute.

Read up on contributing to open source:

* https://opensource.guide/how-to-contribute/

Ways to contribute
******************

Some may believe that the only way to contribute to an open-source
project is by writing code - fixing bugs or contributing new features.
In reality, there are more ways to contribute.

Documentation
=============

As you learn to use LAVA, keep track of where you notice gaps in the
documentation. Most of the documentation is written by experienced
LAVA maintainers and there are plenty of hidden assumptions. One great
way to start contributing is to provide new documentation to fill in
the gaps or help to reorganize some of the existing documentation to
make it easier for new users to follow. If you experienced and
overcame a challenge because the documentation was lacking, please get
involved and improve the documentation!

LAVA documentation lives in the same repository as the code, in the
``doc/v2`` directory. It is written using reStructuredText.

.. seealso:: Read the `reStructuredText Primer
   <http://www.sphinx-doc.org/en/master/usage/restructuredtext/basics.html>`_
   for more information on reStructuredText. It is used by many Python
   projects.

Issue Tracker
=============

Get involved by using the LAVA Software Community Project issue
tracker at https://git.lavasoftware.org/lava/lava/issues. To begin
with, you might only create bug reports for issues you encounter. As
you become more comfortable, consider triaging other bug reports.

Start by picking an existing issue and try to reproduce the problem in
another system to which you have access. If you can reproduce it,
outline the steps as a comment on the issue. This will save time for
maintainers when they come to fix the bug later. If you cannot
reproduce the issue, ask the reporter for more information. Triaging
issues has a side-effect of helping you learn more about the project.
This will come in handy as you contribute documentation and/or code in
the future.

Bug Fixes and New Features
==========================

If you can write code, consider contributing bug fixes and,
eventually, new features. There is a good chance that you have
encountered a bug or two in the course of using LAVA. Contribute a fix
for one of these bugs first; it's very rewarding when you solve one of
your own problems and see the change accepted.

Not all bug fixes involve :ref:`new devices <adding_new_device_types>`,
:ref:`Jinja2 templates <jinja_templating>` or changes to the
``lava_dispatcher`` code. :ref:`XMLRPC <xml_rpc>` calls, general user
interface issues, rendering issues in the Django_ templates and
usability of the :term:`Query <query>` and :term:`Charts <chart>`
functionality would all benefit from more developer attention.

.. _Django: https://www.djangoproject.com/

Contributing to the functional testing
======================================

The LAVA Software Community Project uses LAVA to test changes to the
LAVA codebase as part of our internal :ref:`continuous_integration` by
running unchanging reference LAVA test jobs against the evolving LAVA
codebase, using as many different :term:`device types <device type>`
as possible. As a long term project, it is important to get wide
coverage of devices yet also to minimize changes outside the LAVA
codebase.

Historically, this testing was done using Linaro's staging test lab
(https://staging.validation.linaro.org/scheduler/), a small lab
isolated from the other Linaro LAVA instances. In order to broaden the
range of devices which are available for functional testing, labs with
device-types not currently available on staging.validation.linaro.org
would be particularly beneficial.

To contribute, you need to already have a local LAVA lab with suitably
configured, stable, devices and enough capacity to run extra LAVA test
jobs for a few hours at a time. Test jobs would be run via a docker
device on your master, using your devices with a docker worker using
the latest LAVA code. This is a new area of LAVA development, and work
is ongoing. If you are interested, please :ref:`talk to us
<mailing_lists>`.

.. FIXME: Needs more content here on lavafed.

Mailing lists and IRC
=====================

Helping other people on the mailing lists or on IRC is another very
important role within the LAVA Software Community Project.

* Users need help across all time zones and the LAVA maintainers might
  not be around to answer, especially at weekends.

* New users can particularly appreciate help from other new users. The
  LAVA maintainers can respond later to clarify any misunderstandings
  or fill in more details. Ask questions in the same way as on the
  issue tracker:

  * identify if the problem being described can be reproduced
  * is the problem already covered in the documentation?

    * if it is, is there a need to update the documentation to make the
      answer easier to find?
