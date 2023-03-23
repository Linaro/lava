.. index:: development process

.. _development_process:

Development process
===================

The LAVA development process is based on git. The various source code
repositories are hosted on `the lavasoftware GitLab instance
<https://git.lavasoftware.org/>`_.

The LAVA team is spread geographically around the world, with members
in multiple countries. We can often be found talking on our IRC
channel ``#lavasoftware`` on ``irc.libera.chat``.

The LAVA codebase is all Free and Open Source Software, and we welcome
third party contributions and new team members. Developers are
recommended to join us on the :ref:`lava_devel` mailing list to
discuss development ideas and issues.

.. seealso:: :ref:`getting_support`

.. index:: lava design meeting

.. _lava_design_meeting:

Design meeting
^^^^^^^^^^^^^^

The LAVA design meeting is where the team gets together to work out
deep technical issues, and to agree on future development goals and
ideas. We set priorities for core LAVA development here, and agree on
what will go into upcoming releases.

We hold this meeting weekly every Wednesday at 13:00 to 14:00 UTC as a
video conference using Google Hangouts Meet:
https://meet.google.com/usu-aatj-fht. Summaries of the discussions
are posted to the :ref:`lava_devel` mailing list afterwards for the
benefit of those unable to attend.

If you wish to attend to discuss an issue, it is worth mentioning it
in advance on the mailing list first so that your topic is expected
and can be added to the agenda.

.. _lava_release_process:

Release process
^^^^^^^^^^^^^^^

LAVA is developed on an approximately monthly release schedule. Some months do
not include a release, this can be due to conference attendance or other
reasons. Subscribe to the :ref:`lava_announce` mailing list for updates.

Releases are based on git tags named to follow a YYYY.MM (year, month) pattern.
Should we need to release an upgrade to any existing release (such as for a
critical bug fix), we use the ``post`` suffix and sequential number
(YYYY.MM.postN).

.. note:: There can be a delay between the upload of the next release to
   Debian and the :ref:`lava_repositories` (production repo) and the deployment
   of that same release onto ``validation.linaro.org``. The actual version
   installed can be seen in the header of the each page of the documentation.

The process itself consists of testing the master branch deployments on
``staging.validation.linaro.org``, merging the master branch into the staging
branch to create a *release candidate*, followed by merging the release
candidate into the release branch and creating the git tags.

During the testing of the release candidate, changes can continue to be merged
into master. Changes which are intended to go into the release candidate are
*cherry picked* using Gerrit into the staging branch.

Releases
^^^^^^^^

Releases are made to Debian and announced on the :ref:`lava_announce` mailing
list. A lot of information is directly accessible from the Debian Tracker pages
for each project:

``lava-server`` tracker: https://tracker.debian.org/pkg/lava-server

``lava-dispatcher`` tracker: https://tracker.debian.org/pkg/lava-dispatcher

Reporting Bugs
^^^^^^^^^^^^^^

New bugs should be reported via the `LAVA Users mailing list
<https://lists.lavasoftware.org/mailman3/lists/lava-users.lists.lavasoftware.org/>`_. You will need
to subscribe to the list to be able to post.

Please describe the problem clearly:

* Give the version of LAVA software you are using, as reported by ``dpkg -l
  lava-server lava-dispatcher``

* Attach all relevant configuration and log portions. If you are using LAVA
  with your own device, provide the full Jinja2 template, device dictionary
  and test job submission as well as the complete test job output.

If you were using our public LAVA instance, the one used by Linaro for daily
activities (https://validation.linaro.org), try to include a link to a page
that manifests the problem. That will make debugging easier.
