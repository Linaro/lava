.. index:: development process

Developer guides
################

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
#linaro-lava on irc.freenode.net.

Release process
^^^^^^^^^^^^^^^

LAVA is developed on a monthly release schedule.

Release tarballs follow a YYYY.MM (year, month) pattern. Should we
need to release an upgrade to any existing release (such as for a
critical bug fix), we append a dash and a sequential number
(YYYY.MM-NN).


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

Patches, fixes and code
^^^^^^^^^^^^^^^^^^^^^^^

If you'd like to offer a patch (whether it is a bug fix, documentation
update, new feature or even a simple typo fix) it is best to follow
this simple check-list:

1. Clone the master of the correct project.
2. Add your code, change any existing files as needed.
3. Create a patch from your changes.
4. Send the patch to the `Linaro Code Review <https://review.linaro.org>`_ system.
