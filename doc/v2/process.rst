.. index:: development process

.. _development_process:

Development process
===================

The LAVA development process is based on git. The various source code
repositories are hosted on `Linaro's git server
<https://git.linaro.org/?a=project_list;pf=lava>`_.

Most of the LAVA development work is done by the members of the Linaro
Validation Team. The code is all Free and Open Source Software, and we
welcome third party contributions and new team members.

Our team is spread geographically around the world, with members in
multiple countries. We are usually talking on our IRC channel
``#linaro-lava`` on ``irc.freenode.net``.

.. seealso:: :ref:`getting_support`

.. _lava_release_process:

Release process
^^^^^^^^^^^^^^^

LAVA is developed on an approximately monthly release schedule. Some
months do not include a release, this can be due to conference attendance
or other reasons. Subscribe to the :ref:`lava_announce` mailing list for
updates.

Releases are based on git tags named to follow a YYYY.MM (year, month) pattern.
Should we need to release an upgrade to any existing release (such as for a
critical bug fix), we use the ``post`` suffix and sequential number
(YYYY.MM.postN).

.. note:: There can be a delay between the upload of the next release to
   Debian and the :ref:`lava_repositories` (production repo) and the
   deployment of that same release onto ``validation.linaro.org``.
   The actual version installed can be seen in the header of the
   each page of the documentation.

The process itself consists of testing the master branch deployments
on ``staging.validation.linaro.org``, merging the master branch into
the staging branch to create a *release candidate*, followed by merging
the release candidate into the release branch and creating the git tags.

During the testing of the release candidate, changes can continue to be
merged into master. Changes which are intended to go into the release
candidate are *cherry picked* using Gerrit into the staging branch.

Releases
^^^^^^^^

Releases are made to Debian and announced on the :ref:`lava_announce`
mailing list. A lot of information is directly accessible from the
Debian Tracker pages for each project:

``lava-server`` tracker: https://tracker.debian.org/pkg/lava-server

``lava-dispatcher`` tracker: https://tracker.debian.org/pkg/lava-dispatcher

Reporting Bugs
^^^^^^^^^^^^^^

New bugs should be reported in `Linaro Bugzilla
<https://bugs.linaro.org/enter_bug.cgi?product=LAVA%20Framework>`_. If
you need an account to log in, please register here: `Linaro
Registration <https://register.linaro.org/>`_.

If you are not sure which component is affected by your bug, simply
report it against any of the LAVA sub-projects and let us handle the
rest. As with any bug report, please describe the problem clearly and
give the version of LAVA software you are using.

If you were using our public LAVA instance, the one used by Linaro for
daily activities (https://validation.linaro.org), try to include a
link to a page that manifests the problem. That will make debugging
easier.
