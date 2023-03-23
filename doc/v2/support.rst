.. index:: support

.. _getting_support:

Getting support
###############

LAVA is free software and is provided "as is" without warranty of any
kind. Support is offered using the methods below and we will try to
help resolve queries.

Whenever you look for support for LAVA, there are some guidelines
to follow:

.. seealso:: :ref:`code_of_conduct`

.. index:: support guidelines

.. _guidelines:

Guidelines
**********

* Make sure you read the :ref:`code_of_conduct` which relates to all
  communication in the LAVA Software Community Project.

* If you are having problems, it may be helpful to check the mailing
  list archives **first** - somebody else may have already seen and
  solved a similar problem. Also check the list of outstanding issues
  in GitLab to see if someone else has the same problem.
  https://git.lavasoftware.org/lava/lava/issues

* Avoid putting LAVA job output directly into your email to a list or
  IRC channel. Mailing list posts can include a few lines but not IRC.
  Attach full logs to your email instead of including content inline.

* Always use a `pastebin`_ for log output, and include a link to the
  paste in your post.

* If you are integrating your own device into LAVA, always include the
  full jinja2 device-type template and device dictionary.

* Include the job definition you used, either in this paste or another
  paste.

* If you are administering your own instance, also include the device
  type template and an export of the device dictionary.

* Provide details of which server you are using (with a URL if it is
  publicly visible or a version string from the documentation pages if
  not) and details of the actual device(s) in use.

.. index:: mailing list

.. _mailing_lists:

Mailing lists
*************

The primary method for support for LAVA is our mailing lists.

A few guidelines apply to all such lists:

* Reply to the list, adding the submitter in CC where appropriate.

* If your job uses URLs which are not visible to the rest of the list,
  include a rough outline of how those were built and what versions of
  tools were used.

* Avoid `top posting
  <https://en.wikipedia.org/wiki/Posting_style#Top-posting>`_.

* Always provide as much context as you can when phrasing your question
  to the list.

.. seealso:: The LAVA team workflow announcement:
   https://lists.lavasoftware.org/archives/list/lava-announce@lists.lavasoftware.org/thread/UD2YW35SRJELBUGWEYR6SSE6JCC3ZOOS/
   and https://docs.gitlab.com/ee/workflow/gitlab_flow.html

.. index:: lava-users support

.. _lava_users:

lava-users
==========

The `lava-users
<https://lists.lavasoftware.org/mailman3/lists/lava-users.lists.lavasoftware.org/>`_ mailing list
concentrates on support for setting up LAVA, using current LAVA tests.
Subscribers include test writers, and individual admins. Users are
encouraged to contribute to answer queries from other users. Replies to
the :ref:`lava_announce` list are directed here.

.. index:: lava-devel support

.. _lava_devel:

lava-devel
==========

Subscribing to the `lava-devel
<https://lists.lavasoftware.org/mailman3/lists/lava-devel.lists.lavasoftware.org/>`_ list is
recommended for developers of LAVA. ``lava-devel`` is aimed at
supporting code contributors, device integration engineers and instance
admins who are working with the LAVA codebase. Discussions about
planning and new LAVA features also take place here.

.. index:: lava-announce list, release notes

.. _lava_announce:

lava-announce
=============

Subscribing to the `lava-announce
<https://lists.lavasoftware.org/mailman3/lists/lava-announce.lists.lavasoftware.org/>`_ list is
recommended for **everyone** using LAVA, whether writing tests or
viewing reports or administering a LAVA instance.


Replies to this list are sent to the :ref:`lava_users` list - if you
are not subscribed to ``lava-users``, please ask other users to CC you
on replies.

The release notes for each production release are sent to the
``lava-announce`` mailing list and the `archives
<https://lists.lavasoftware.org/archives/list/lava-announce@lists.lavasoftware.org/latest>`_ contain the
release-notes for previous releases.

.. index:: irc

.. _support_irc:

IRC
***

`IRC <https://en.wikipedia.org/wiki/Internet_Relay_Chat>`_ is a common
support method for developers. Our team is spread geographically around
the world, with members in Europe, America and Asia.

The LAVA Software Community Project has an IRC channel,
``#lavasoftware`` on ``irc.libera.chat``. We can also be found on a
IRC channel used for topics relating to the Linaro Lab in Cambridge,
UK: ``#linaro-lava`` on ``irc.libera.chat``.

:ref:`guidelines` apply to IRC as well:

* Use a proxy or other service which keeps you connected to IRC.
  Developers are based in multiple timezones and not everyone can
  answer all queries. Therefore, you may have to wait several hours
  until the relevant person or people are awake. Check back for replies
  on the channel intermittently. If you disconnect, you will **not**
  see any replies sent whilst you were disconnected from the channel.

* Ask your question, do not wait to see people joining or talking.
  Don't ask if you may ask a question!

* It is even more important with IRC that you **always** use a
  pastebin, even more so than with mailing lists. See
  :ref:`guidelines`.

* Do not assume that the person someone else spoke to last is also able
  to answer your question. Avoid highlighting someone's name out of
  habit - someone else could easily be able to help you but may feel
  that you do not want their input.

* Do not assume that the person you spoke to last is also able to
  answer your other question(s). Different developers and maintainers
  have different strengths across the codebase.

* Reply directly to a person by putting their IRC nickname at the start
  of your message to the channel. In a busy channel, it can be hard to
  spot replies not made to you.

* Developers are busy - IRC is part of our development process, so
  please be considerate of the amount of time involved, there is code
  to write and there are bug fixes to make for other users as well.

* Avoid personal messages unless there is a clear privacy issue
  involved or you know the person well.

* You may well find that one of the :ref:`mailing_lists` actually
  provides a faster answer to your question, especially if you are new
  to LAVA.

.. index:: pastebin

.. _pastebin:

Pastebins
*********

Pastebin services are provided online by multiple people. Some are open to
anyone, such as `pastebin.com <https://pastebin.com/>`_ and `paste.debian.net
<https://paste.debian.net/>`_. Others (like the internal Linaro pastebin) are
restricted and will require users to register. Pastes will typically expire
automatically, depending on the options selected by the user creating the
paste.

Wikipedia has `more information
<https://en.wikipedia.org/wiki/Pastebin>`_
